import time
import logging
import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.dependencies import neo4j_manager, state
from backend.config import (
    TOP_K,
    CHUNK_TOP_K,
    MAX_TOTAL_TOKENS,
    RERANKER_BASE_URL,
    ENABLE_LOCAL_RERANKER,
    RERANK_BY_DEFAULT,
)

# Create the router instance
router = APIRouter(tags=["Graph & Query"])


class QueryRequest(BaseModel):
    question: Optional[str] = None
    query: Optional[str] = None
    mode: str = "mix"
    only_need_context: bool = False
    return_nodes: bool = True

    def get_query_text(self) -> str:
        text = self.question or self.query or ""
        return text.strip()


class QueryLogCapture(logging.Handler):
    """Captures the 'Query nodes:' log line emitted by LightRAG during a query."""

    _QUERY_NODES_RE = re.compile(r"Query nodes?:\s*(.+?)(?:\s*\(top_k|$)")

    def __init__(self):
        super().__init__()
        self.entity_names: list[str] = []

    def emit(self, record: logging.LogRecord):
        msg = record.getMessage()
        m = self._QUERY_NODES_RE.search(msg)
        if m:
            raw = m.group(1)
            self.entity_names = [e.strip() for e in raw.split(",") if e.strip()]


@router.get("/graph")
async def get_graph(limit: int = 300, search: str = ""):
    try:
        return await neo4j_manager.get_graph(limit, search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query(req: QueryRequest):
    if state.rag is None:
        raise HTTPException(status_code=503, detail="RAGAnything not initialised yet")

    query_text = req.get_query_text()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query or question text is required")

    t0 = time.time()
    capture = QueryLogCapture() if req.return_nodes else None
    if capture:
        for name in ["lightrag", "raganything"]:
            logging.getLogger(name).addHandler(capture)

    try:
        query_kwargs = {
            "mode": req.mode,
            "vlm_enhanced": False,
            "top_k": TOP_K,
            "chunk_top_k": CHUNK_TOP_K,
            "max_total_tokens": MAX_TOTAL_TOKENS,
            "enable_rerank": bool(RERANKER_BASE_URL or ENABLE_LOCAL_RERANKER or RERANK_BY_DEFAULT),
        }
        if req.only_need_context:
            query_kwargs["only_need_context"] = True

        answer = await state.rag.aquery(query_text, **query_kwargs)
        # Handle async generator / stream if returned
        if hasattr(answer, "__aiter__"):
            chunks = []
            async for chunk in answer:
                chunks.append(str(chunk))
            answer = "".join(chunks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if capture:
            for name in ["lightrag", "raganything"]:
                logging.getLogger(name).removeHandler(capture)

    latency_ms = round((time.time() - t0) * 1000, 1)

    if req.only_need_context:
        ctx = str(answer) if answer else "No relevant information found."
        return {"context": ctx, "mode": req.mode, "latency_ms": latency_ms}

    ans_str = str(answer) if answer else "No results found."
    result: dict = {
        "answer": ans_str,
        "response": ans_str,
        "mode": req.mode,
        "latency_ms": latency_ms,
        "retrieved_nodes": capture.entity_names if capture else [],
    }

    if req.return_nodes and capture:
        result["highlighted_nodes"] = await neo4j_manager.resolve_node_ids(
            capture.entity_names
        )

    return result
