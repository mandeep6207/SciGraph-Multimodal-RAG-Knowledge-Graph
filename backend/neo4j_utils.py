import logging
from neo4j import AsyncGraphDatabase

_logger = logging.getLogger(__name__)


class Neo4jManager:
    def __init__(self, uri: str, username: str, password: str, database: str):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None

    def connect(self):
        """Initializes the Neo4j async driver."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                connection_timeout=2.0,
            )
            _logger.info("Neo4j driver initialized.")
        except Exception as e:
            _logger.warning("Failed to initialize Neo4j driver: %s", e)
            self.driver = None

    async def close(self):
        """Closes the driver connection safely."""
        if self.driver:
            try:
                await self.driver.close()
                _logger.info("Neo4j driver closed.")
            except Exception as e:
                _logger.warning("Error closing Neo4j driver: %s", e)
            finally:
                self.driver = None

    def _get_fallback_nx_graph(self):
        """Helper to get internal LightRAG NetworkX graph from memory or disk with caching."""
        # 1. Try from in-memory LightRAG state
        try:
            from backend.dependencies import state
            if state.rag:
                lightrag_inst = getattr(state.rag, "lightrag", None) or state.rag
                graph_storage = getattr(lightrag_inst, "chunk_entity_relation_graph", None)
                if graph_storage:
                    g = getattr(graph_storage, "_graph", None)
                    if g is not None and g.number_of_nodes() > 0:
                        return g
        except Exception:
            pass

        # 2. Try loading from persistent GraphML file on disk with mtime cache
        try:
            from pathlib import Path
            import networkx as nx
            from backend.config import WORKING_DIR
            graphml_path = Path(WORKING_DIR) / "graph_chunk_entity_relation.graphml"
            if graphml_path.exists():
                mtime = graphml_path.stat().st_mtime
                if hasattr(self, "_cached_nx_graph") and getattr(self, "_cached_nx_mtime", 0) == mtime:
                    return self._cached_nx_graph
                g = nx.read_graphml(graphml_path)
                self._cached_nx_graph = g
                self._cached_nx_mtime = mtime
                return g
        except Exception as e:
            _logger.debug(f"Failed to read fallback graphml: {e}")

        return None

    async def get_stats(self) -> tuple[int, int]:
        """Returns (total_nodes, total_relations)."""
        if self.driver:
            try:
                async with self.driver.session(database=self.database) as session:
                    r1 = await session.run("MATCH (n) RETURN count(n) AS c")
                    total_nodes = (await r1.single())["c"]
                    r2 = await session.run("MATCH ()-[r]->() RETURN count(r) AS c")
                    total_relations = (await r2.single())["c"]
                    if int(total_nodes) > 0:
                        return int(total_nodes), int(total_relations)
            except Exception as e:
                _logger.debug(f"Neo4j stats query failed: {e}")

        # Fallback to internal NetworkX graph
        nx_graph = self._get_fallback_nx_graph()
        if nx_graph is not None:
            return nx_graph.number_of_nodes(), nx_graph.number_of_edges()

        return 0, 0

    async def get_graph(self, limit: int = 300, search: str = "") -> dict:
        """Fetches nodes and links for the 3D graph visualization."""
        if self.driver:
            try:
                async with self.driver.session(database=self.database) as session:
                    if search.strip():
                        cypher = """
                            MATCH (n)
                            WHERE toLower(n.entity_id) CONTAINS toLower($search)
                               OR toLower(coalesce(n.description,'')) CONTAINS toLower($search)
                            WITH n LIMIT 5
                            MATCH path = (n)-[r*0..2]-(neighbor)
                            WITH collect(DISTINCT startNode(relationships(path)[0])) +
                                 collect(DISTINCT endNode(relationships(path)[0])) +
                                 collect(DISTINCT n) AS allNodes,
                                 collect(DISTINCT r) AS allRels
                            UNWIND allNodes AS node
                            WITH collect(DISTINCT node)[..200] AS topNodes
                            MATCH (a)-[r]->(b)
                            WHERE a IN topNodes AND b IN topNodes
                            RETURN
                              a.entity_id AS src, a.entity_type AS src_type,
                              coalesce(a.description,'') AS src_desc,
                              b.entity_id AS tgt, b.entity_type AS tgt_type,
                              coalesce(b.description,'') AS tgt_desc,
                              coalesce(r.description, type(r)) AS rel_label,
                              coalesce(r.weight, 1.0) AS weight
                            LIMIT 2000
                        """
                        result = await session.run(cypher, search=search.strip())
                    else:
                        cypher = """
                            MATCH (n)
                            WITH n, size([(n)--() | 1]) AS degree
                            ORDER BY degree DESC
                            LIMIT $limit
                            WITH collect(n) AS topNodes
                            MATCH (a)-[r]->(b)
                            WHERE a IN topNodes AND b IN topNodes
                            RETURN
                              a.entity_id AS src, a.entity_type AS src_type,
                              coalesce(a.description,'') AS src_desc,
                              b.entity_id AS tgt, b.entity_type AS tgt_type,
                              coalesce(b.description,'') AS tgt_desc,
                              coalesce(r.description, type(r)) AS rel_label,
                              coalesce(r.weight, 1.0) AS weight
                            LIMIT 3000
                        """
                        result = await session.run(cypher, limit=limit)

                    nodes: dict[str, dict] = {}
                    links: list[dict] = []

                    async for row in result:
                        src, tgt = row["src"], row["tgt"]
                        if not src or not tgt:
                            continue

                        if src not in nodes:
                            nodes[src] = {
                                "id": src,
                                "type": (row["src_type"] or "unknown").lower(),
                                "desc": row["src_desc"][:200] if row["src_desc"] else "",
                                "degree": 0,
                            }
                        if tgt not in nodes:
                            nodes[tgt] = {
                                "id": tgt,
                                "type": (row["tgt_type"] or "unknown").lower(),
                                "desc": row["tgt_desc"][:200] if row["tgt_desc"] else "",
                                "degree": 0,
                            }

                        nodes[src]["degree"] += 1
                        nodes[tgt]["degree"] += 1
                        links.append(
                            {
                                "source": src,
                                "target": tgt,
                                "label": (row["rel_label"] or "")[:80],
                                "weight": float(row["weight"] or 1.0),
                            }
                        )

                    node_list = list(nodes.values())
                    if node_list:
                        return {"nodes": node_list, "links": links, "edges": links}

            except Exception as e:
                _logger.warning("Neo4j graph query failed: %s. Using fallback if available.", e)

            except Exception as e:
                _logger.warning("Neo4j graph query failed: %s. Using fallback if available.", e)

        # Fallback to internal NetworkX graph
        nx_graph = self._get_fallback_nx_graph()
        if nx_graph is not None and nx_graph.number_of_nodes() > 0:
            degrees = dict(nx_graph.degree())
            search_term = search.strip().lower()

            if search_term:
                matched_nodes = [
                    n for n in nx_graph.nodes
                    if search_term in str(n).lower()
                    or search_term in str(nx_graph.nodes[n].get("description", "")).lower()
                ][:limit]
                candidate_nodes = set(matched_nodes)
                for n in matched_nodes:
                    candidate_nodes.update(nx_graph.neighbors(n))
                selected = list(candidate_nodes)[:limit]
            else:
                sorted_nodes = sorted(nx_graph.nodes, key=lambda n: degrees.get(n, 0), reverse=True)
                selected = sorted_nodes[:limit]

            selected_set = set(selected)
            node_list = []
            for nid in selected:
                ndata = nx_graph.nodes[nid]
                node_list.append({
                    "id": str(nid),
                    "type": str(ndata.get("entity_type") or "concept").lower(),
                    "desc": str(ndata.get("description") or "")[:200],
                    "degree": degrees.get(nid, 0),
                })

            links = []
            for u, v, edata in nx_graph.edges(data=True):
                if u in selected_set and v in selected_set:
                    links.append({
                        "source": str(u),
                        "target": str(v),
                        "label": str(edata.get("description") or edata.get("relation") or "")[:80],
                        "weight": float(edata.get("weight") or 1.0),
                    })

            return {"nodes": node_list, "links": links, "edges": links}

        return {"nodes": [], "links": [], "edges": []}

    async def resolve_node_ids(self, entity_names: list[str]) -> list[str]:
        """Look up entity_ids that match the captured entity names."""
        if not entity_names:
            return []

        if self.driver:
            try:
                async with self.driver.session(database=self.database) as session:
                    result = await session.run(
                        """
                        UNWIND $names AS name
                        MATCH (n)
                        WHERE toLower(n.entity_id) = toLower(name)
                           OR toLower(n.entity_id) CONTAINS toLower(name)
                        RETURN DISTINCT n.entity_id AS eid
                        LIMIT 60
                        """,
                        names=entity_names,
                    )
                    ids = []
                    async for row in result:
                        if row["eid"]:
                            ids.append(row["eid"])
                    if ids:
                        return ids
            except Exception as e:
                _logger.warning(f"Node ID resolution failed in Neo4j: {e}")

        # Fallback to internal NetworkX graph
        nx_graph = self._get_fallback_nx_graph()
        if nx_graph is not None:
            ids = []
            lowered_names = [n.lower() for n in entity_names if n]
            for node in nx_graph.nodes:
                str_node = str(node).lower()
                if any(n == str_node or n in str_node for n in lowered_names):
                    ids.append(str(node))
                    if len(ids) >= 60:
                        break
            return ids

        return []
