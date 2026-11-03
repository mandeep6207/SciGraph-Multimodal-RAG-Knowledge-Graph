"""
Comprehensive Test Suite for SciGraph — Scientific Intelligence Workspace
Tests every API endpoint, router, background job system, graph manager, reranker, and providers.

Run with:
    .venv\Scripts\python.exe test_suite.py
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

# --- MUST be set BEFORE importing app ---
os.environ["TESTING"] = "1"
os.environ["GRAPH_STORAGE"] = "NetworkXStorage"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient

# Import app and backend modules AFTER setting env vars
import app as main_app
from backend.dependencies import job_manager, neo4j_manager, document_reranker, state
from backend.jobs import Job, JobManager
from backend.reranker import DocumentReranker
from backend.neo4j_utils import Neo4jManager
from backend.llm_providers import OllamaProvider, OpenAIProvider
from backend.config import UPLOAD_DIR, WORKING_DIR


# ---------------------------------------------------------------------------
# Mock RAG classes (used instead of real LightRAG/RAGAnything in tests)
# ---------------------------------------------------------------------------
class MockLightRAG:
    def __init__(self):
        import networkx as nx
        self._nx = nx.Graph()
        self._nx.add_node("Artificial Intelligence", entity_type="concept", description="Field of study")
        self._nx.add_node("Machine Learning", entity_type="method", description="Subset of AI")
        self._nx.add_edge("Artificial Intelligence", "Machine Learning", description="includes", weight=1.5)

        mock_storage = MagicMock()
        mock_storage._graph = self._nx
        self.chunk_entity_relation_graph = mock_storage


class MockRAGAnything:
    def __init__(self):
        self.lightrag = MockLightRAG()

    async def aquery(self, query: str, mode: str = "mix", **kwargs):
        return f"Mock answer for '{query}' using mode '{mode}'."

    async def process_document_complete(self, *args, **kwargs):
        return True


# ---------------------------------------------------------------------------
# Test runner helpers
# ---------------------------------------------------------------------------
passed = 0
failed = 0
errors = []


def assert_test(name: str, condition: bool, extra: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name} {extra}")
    else:
        failed += 1
        errors.append(name)
        print(f"  [FAIL] {name} {extra}")


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------
def run_tests():
    global passed, failed

    print("=" * 70)
    print("RUNNING COMPREHENSIVE AUDIT & TEST SUITE FOR SCIGRAPH")
    print("=" * 70)

    # Set mock RAG BEFORE creating TestClient (lifespan skips in TESTING mode,
    # but routers still check state.rag is not None)
    state.rag = MockRAGAnything()

    # Also give neo4j_manager a no-op state so /stats doesn't hang
    neo4j_manager.driver = None

    client = TestClient(main_app.app, raise_server_exceptions=False)

    # =========================================================================
    # 1. Root & Static UI
    # =========================================================================
    print("\n--- 1. Testing Root & Frontend Static Files ---")
    resp = client.get("/")
    assert_test(
        "GET / (Root HTML)",
        resp.status_code == 200 and "SCIGRAPH" in resp.text.upper(),
        f"-> status={resp.status_code}",
    )

    resp = client.get("/ui/index.html")
    assert_test(
        "GET /ui/index.html",
        resp.status_code == 200,
        f"-> status={resp.status_code}",
    )

    # =========================================================================
    # 2. System & Health Endpoints
    # =========================================================================
    print("\n--- 2. Testing System & Health Endpoints ---")
    resp = client.get("/health")
    data = resp.json()
    assert_test(
        "GET /health",
        resp.status_code == 200 and data.get("status") == "ok" and "llm_model" in data,
        f"-> {data}",
    )

    resp = client.get("/stats")
    stats = resp.json()
    assert_test(
        "GET /stats",
        resp.status_code == 200 and "total_docs" in stats and "total_nodes" in stats,
        f"-> docs={stats.get('total_docs')}, nodes={stats.get('total_nodes')}",
    )

    resp = client.get("/hidden-types")
    assert_test(
        "GET /hidden-types",
        resp.status_code == 200 and isinstance(resp.json(), list),
    )

    resp = client.post("/hidden-types", json=["discarded", "unknown", "temporary"])
    assert_test(
        "POST /hidden-types",
        resp.status_code == 200 and resp.json().get("status") == "ok",
    )

    resp = client.get("/hidden-types")
    assert_test(
        "GET /hidden-types (verify persistence)",
        "temporary" in resp.json(),
    )

    resp = client.get("/processed-filenames")
    assert_test(
        "GET /processed-filenames",
        resp.status_code == 200 and isinstance(resp.json(), list),
    )

    resp = client.get("/conversations")
    assert_test(
        "GET /conversations",
        resp.status_code == 200 and isinstance(resp.json(), list),
    )

    sample_conv = [{"id": "test_conv_1", "title": "Test Chat", "messages": [{"role": "user", "text": "Hello"}]}]
    resp = client.post("/conversations", json=sample_conv)
    assert_test(
        "POST /conversations",
        resp.status_code == 200 and resp.json().get("status") == "ok",
    )

    resp = client.get("/conversations")
    saved = resp.json()
    assert_test(
        "GET /conversations (verify saved)",
        isinstance(saved, list) and len(saved) > 0 and saved[0].get("id") == "test_conv_1",
    )

    # =========================================================================
    # 3. Queue & Documents Endpoints
    # =========================================================================
    print("\n--- 3. Testing Queue & Document Upload Endpoints ---")
    resp = client.post("/queue/pause")
    assert_test(
        "POST /queue/pause",
        resp.status_code == 200 and resp.json().get("paused") is True,
    )

    resp = client.post("/queue/resume")
    assert_test(
        "POST /queue/resume",
        resp.status_code == 200 and resp.json().get("paused") is False,
    )

    resp = client.get("/uploads")
    assert_test(
        "GET /uploads",
        resp.status_code == 200 and isinstance(resp.json(), list),
    )

    # Valid PDF upload
    dummy_pdf = b"%PDF-1.4 header dummy content for unit test %%EOF"
    files = {"file": ("unit_test_doc.pdf", dummy_pdf, "application/pdf")}
    resp = client.post("/upload", files=files)
    upload_data = resp.json()
    job_id = upload_data.get("job_id")
    assert_test(
        "POST /upload (Valid PDF)",
        resp.status_code == 200 and job_id is not None and "filename" in upload_data,
        f"-> job_id={job_id}",
    )

    # Unsupported extension
    bad_files = {"file": ("malicious.exe", b"binary", "application/octet-stream")}
    resp = client.post("/upload", files=bad_files)
    assert_test(
        "POST /upload (Reject unsupported file)",
        resp.status_code == 400,
        f"-> status={resp.status_code}",
    )

    # Jobs listing
    resp = client.get("/jobs")
    jobs_list = resp.json()
    assert_test(
        "GET /jobs",
        resp.status_code == 200 and isinstance(jobs_list, list)
        and any(j.get("id") == job_id for j in jobs_list),
        f"-> {len(jobs_list)} jobs",
    )

    # Progress SSE stream for created job
    with client.stream("GET", f"/progress/{job_id}") as stream_resp:
        first_line = ""
        for line in stream_resp.iter_lines():
            if line:
                first_line = line
                break
    assert_test(
        "GET /progress/{job_id} (SSE stream)",
        stream_resp.status_code == 200 and "data:" in first_line,
        f"-> first_line={first_line[:60]}",
    )

    # Progress 404 for unknown job
    resp = client.get("/progress/unknown-uuid-000")
    assert_test(
        "GET /progress/{unknown} -> 404",
        resp.status_code == 404,
    )

    # Delete uploaded file
    resp = client.delete("/uploads/unit_test_doc.pdf")
    assert_test(
        "DELETE /uploads/unit_test_doc.pdf",
        resp.status_code == 200,
        f"-> status={resp.status_code}",
    )

    resp = client.delete("/uploads/non_existent_file.pdf")
    assert_test(
        "DELETE /uploads/non_existent_file.pdf -> 404",
        resp.status_code == 404,
    )

    # =========================================================================
    # 4. Graph & Query Endpoints
    # =========================================================================
    print("\n--- 4. Testing Graph & Query Endpoints ---")
    resp = client.get("/graph")
    graph_data = resp.json()
    assert_test(
        "GET /graph",
        resp.status_code == 200 and "nodes" in graph_data and "links" in graph_data,
        f"-> nodes={len(graph_data.get('nodes', []))}, links={len(graph_data.get('links', []))}",
    )

    resp = client.get("/graph?search=Intelligence")
    search_data = resp.json()
    assert_test(
        "GET /graph?search=Intelligence",
        resp.status_code == 200 and len(search_data.get("nodes", [])) > 0,
        f"-> matched nodes={len(search_data.get('nodes', []))}",
    )

    # POST /query with "question" key
    resp = client.post("/query", json={"question": "What is AI?", "mode": "mix", "return_nodes": True})
    qdata = resp.json()
    answer_preview = (qdata.get("answer") or "")[:60]
    assert_test(
        "POST /query (with 'question')",
        resp.status_code == 200 and "answer" in qdata and "response" in qdata,
        f"-> answer: {answer_preview}",
    )

    # POST /query with "query" key (upload_test.py compatibility)
    resp = client.post("/query", json={"query": "What is machine learning?", "mode": "hybrid"})
    qdata2 = resp.json()
    assert_test(
        "POST /query (with 'query' key compatibility)",
        resp.status_code == 200 and "answer" in qdata2,
    )

    # POST /query with only_need_context
    resp = client.post("/query", json={"question": "Context check", "only_need_context": True})
    ctx_data = resp.json()
    assert_test(
        "POST /query (only_need_context)",
        resp.status_code == 200 and "context" in ctx_data,
    )

    # POST /query with empty body -> 400
    resp = client.post("/query", json={})
    assert_test(
        "POST /query (Reject empty question) -> 400",
        resp.status_code == 400,
        f"-> status={resp.status_code}",
    )

    # =========================================================================
    # 5. DocumentReranker Unit Tests
    # =========================================================================
    print("\n--- 5. Testing DocumentReranker ---")
    reranker = DocumentReranker(model_name="BAAI/bge-reranker-v2-m3")

    # Empty documents
    res = asyncio.run(reranker.rerank("test query", []))
    assert_test(
        "DocumentReranker.rerank (empty doc list)",
        res == [],
    )

    # Local reranker ranking test (uses cached HF snapshot)
    docs = [
        "Artificial Intelligence and Deep Neural Networks",
        "Cooking recipes for Italian pizza and pasta",
        "Machine Learning algorithms and statistical models",
    ]
    print("  [INFO] Loading reranker from local cache (may take ~5-10s)...")
    res = asyncio.run(reranker.rerank("Machine learning and AI", docs, top_n=2))
    assert_test(
        "DocumentReranker.rerank (ranking accuracy)",
        len(res) == 2 and res[0]["index"] in (0, 2),
        f"-> top ranked indices: {[r['index'] for r in res]}",
    )

    # =========================================================================
    # 6. LLM Provider Unit Tests
    # =========================================================================
    print("\n--- 6. Testing LLM Providers ---")
    ollama = OllamaProvider(
        base_url="http://localhost:11434/",
        llm_model="qwen2.5:3b",
        vision_model="",
        embed_model="nomic-embed-text",
        num_ctx=4096,
        timeout=60,
    )
    assert_test(
        "OllamaProvider URL strip",
        ollama.base_url == "http://localhost:11434",
    )

    empty_embed = asyncio.run(ollama.embed([]))
    assert_test(
        "OllamaProvider.embed (empty texts)",
        len(empty_embed) == 0,
    )

    openai_prov = OpenAIProvider(
        api_key="test-key",
        base_url="http://localhost:8000/v1/",
        llm_model="test-llm",
        vision_model="",
        embed_model="test-embed",
        timeout=60,
    )
    assert_test(
        "OpenAIProvider URL strip",
        openai_prov.base_url == "http://localhost:8000/v1",
    )

    empty_embed_openai = asyncio.run(openai_prov.embed([]))
    assert_test(
        "OpenAIProvider.embed (empty texts)",
        len(empty_embed_openai) == 0,
    )

    # =========================================================================
    # 7. JobManager & LogHandler Unit Tests
    # =========================================================================
    print("\n--- 7. Testing JobManager & JobLogHandler ---")
    jm = JobManager(str(WORKING_DIR))
    job = jm.new_job("test_audit.pdf")
    job.push("chunk", "Chunk 1 of 10")
    job.push("node", "Entities extracted: 15", total=15)
    job.push("relation", "Relations extracted: 8", total=8)
    jdict = job.to_dict()
    assert_test(
        "Job.to_dict (includes both 'id' and 'job_id')",
        jdict.get("id") == job.id and jdict.get("job_id") == job.id and jdict.get("chunks") == 1,
        f"-> id={jdict.get('id')}, job_id={jdict.get('job_id')}, chunks={jdict.get('chunks')}",
    )

    jm.save_completed("test_audit.pdf", chunks=10, nodes=15, relations=8, finished_at=time.time())
    completed = jm.load_completed()
    assert_test(
        "JobManager persistence (save & load completed_docs.json)",
        "test_audit.pdf" in completed and completed["test_audit.pdf"]["nodes"] == 15,
        f"-> keys: {list(completed.keys())}",
    )

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed} PASSED, {failed} FAILED")
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  - {e}")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
