import json
import time
import shutil
import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.dependencies import job_manager, neo4j_manager, state
from backend.config import (
    VISION_MODEL,
    LLM_MODEL,
    EMBEDDING_MODEL,
    LLM_ENGINE,
    HIDDEN_TYPES_FILE,
    CONV_FILE,
    PROFILE_FILE,
    WORKSPACES_FILE,
    WORKING_DIR,
    UPLOAD_DIR,
    OUTPUT_DIR,
    COMPLETED_LOG,
)

router = APIRouter(tags=["System & Stats"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "vision_model": VISION_MODEL or "not configured",
        "llm_model": LLM_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "llm_engine": LLM_ENGINE,
        "rag_ready": state.rag is not None,
    }


@router.get("/stats")
async def get_stats():
    jobs = [
        job_manager.jobs[jid]
        for jid in job_manager.jobs_order
        if jid in job_manager.jobs
    ]
    failed = [j for j in jobs if j.status == "error"]
    active = [j for j in jobs if j.status in ("parsing", "processing")]

    total_nodes, total_relations = await neo4j_manager.get_stats()
    completed = job_manager.load_completed()
    processed_count = len(completed)

    total_queries = 0
    if CONV_FILE.exists():
        try:
            with open(CONV_FILE, "r", encoding="utf-8") as f:
                convs = json.load(f)
                for c in convs:
                    total_queries += len([m for m in c.get("messages", []) if m.get("role") == "user"])
        except Exception:
            pass

    return {
        "total_docs": processed_count,
        "processed": processed_count,
        "failed": len(failed),
        "active": len(active),
        "queued": len(job_manager.processing_queue),
        "total_nodes": total_nodes,
        "total_relations": total_relations,
        "total_queries": total_queries,
        "queue_paused": job_manager.queue_paused,
        "current_job": job_manager.current_job.to_dict()
        if job_manager.current_job
        else None,
    }


@router.get("/hidden-types")
async def get_hidden_types():
    if HIDDEN_TYPES_FILE.exists():
        try:
            with open(HIDDEN_TYPES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return ["discarded", "unknown"]


@router.post("/hidden-types")
async def save_hidden_types(types: list[str]):
    HIDDEN_TYPES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HIDDEN_TYPES_FILE, "w", encoding="utf-8") as f:
        json.dump(types, f, ensure_ascii=False, indent=2)
    return {"status": "ok"}


@router.get("/processed-filenames")
def processed_filenames():
    return list(job_manager.load_completed().keys())


@router.get("/jobs")
def list_jobs():
    return job_manager.get_all_jobs_dict()


# ---------------------------------------------------------------------------
# User Profile Endpoints
# ---------------------------------------------------------------------------
DEFAULT_PROFILE = {
    "full_name": "Mandeep Kumar",
    "username": "mandeep6207",
    "display_name": "Mandeep Kumar",
    "email": "mandeep@scigraph.ai",
    "initials": "MK",
    "role": "Lead Researcher & Workspace Owner",
    "title": "Principal AI Research Scientist",
    "institution": "SciGraph Scientific Intelligence Labs",
    "department": "Neural Knowledge Discovery & Graph AI",
    "bio": "Researching topological multimodal knowledge graphs, neural entity-relationship extraction, and low-latency grounded reasoning with generative AI.",
    "research_interests": ["Multimodal RAG", "Knowledge Graphs", "Latent Space Synthesis", "Diffusion Architectures", "Attention Models"],
    "skills": ["FastAPI", "LightRAG", "PyTorch", "NetworkX", "Ollama", "Grok API"],
    "avatar_url": "",
    "theme_preference": "dark",
    "created_at": "2026-01-01",
}


@router.get("/profile")
def get_profile():
    if PROFILE_FILE.exists():
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                merged = {**DEFAULT_PROFILE, **saved}
                return merged
        except Exception:
            pass
    return DEFAULT_PROFILE


@router.post("/profile")
async def save_profile(request: Request):
    try:
        data = await request.json()
        current = get_profile()
        for k in (
            "display_name",
            "full_name",
            "email",
            "title",
            "role",
            "institution",
            "department",
            "bio",
            "research_interests",
            "skills",
            "avatar_url",
            "theme_preference",
        ):
            if k in data and data[k] is not None:
                current[k] = data[k]

        name_parts = current.get("display_name", "Mandeep Kumar").split()
        if len(name_parts) >= 2:
            current["initials"] = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
        elif name_parts:
            current["initials"] = name_parts[0][:2].upper()
        else:
            current["initials"] = "MK"

        PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "profile": current}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save profile: {e}")


@router.post("/profile/avatar")
async def upload_avatar(file: UploadFile = File(...)):
    try:
        raw_name = Path(file.filename or "avatar.png").name
        ext = Path(raw_name).suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
            raise HTTPException(status_code=400, detail="Invalid avatar format (must be image)")

        avatar_name = f"profile_avatar_{int(time.time())}{ext}"
        avatar_dir = Path(UPLOAD_DIR) / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        avatar_path = avatar_dir / avatar_name
        content = await file.read()
        avatar_path.write_bytes(content)

        avatar_url = f"/uploads/avatars/{avatar_name}"
        current = get_profile()
        current["avatar_url"] = avatar_url

        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

        return {"status": "ok", "avatar_url": avatar_url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Workspaces Endpoints
# ---------------------------------------------------------------------------
DEFAULT_WORKSPACES = [
    {
        "id": "ws-default",
        "name": "General Science Workspace",
        "description": "Primary workspace for multimodal scientific papers, cross-disciplinary graph analysis, and AI intelligence synthesis.",
        "created_at": 1704067200,
        "is_default": True,
        "documents": [],
        "tags": ["scientific-research", "multimodal", "general"],
        "storage_mode": "unified_global_graph",
    }
]


def _load_workspaces() -> list[dict]:
    if WORKSPACES_FILE.exists():
        try:
            with open(WORKSPACES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    return DEFAULT_WORKSPACES


def _save_workspaces(workspaces: list[dict]):
    WORKSPACES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WORKSPACES_FILE, "w", encoding="utf-8") as f:
        json.dump(workspaces, f, ensure_ascii=False, indent=2)


@router.get("/workspaces")
def list_workspaces():
    return _load_workspaces()


@router.post("/workspaces")
async def create_workspace(request: Request):
    try:
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Workspace name is required")

        workspaces = _load_workspaces()
        new_ws = {
            "id": f"ws-{int(time.time())}",
            "name": name,
            "description": (body.get("description") or "").strip(),
            "created_at": time.time(),
            "is_default": False,
            "documents": body.get("documents") or [],
            "tags": body.get("tags") or ["custom"],
            "storage_mode": "unified_global_graph",
        }
        workspaces.append(new_ws)
        _save_workspaces(workspaces)
        return {"status": "ok", "workspace": new_ws}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/workspaces/{ws_id}")
async def update_workspace(ws_id: str, request: Request):
    try:
        body = await request.json()
        workspaces = _load_workspaces()
        found = False
        for ws in workspaces:
            if ws["id"] == ws_id:
                if "name" in body and body["name"].strip():
                    ws["name"] = body["name"].strip()
                if "description" in body:
                    ws["description"] = body["description"].strip()
                if "documents" in body and isinstance(body["documents"], list):
                    ws["documents"] = body["documents"]
                if "tags" in body and isinstance(body["tags"], list):
                    ws["tags"] = body["tags"]
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail="Workspace not found")
        _save_workspaces(workspaces)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/workspaces/{ws_id}")
def delete_workspace(ws_id: str):
    workspaces = _load_workspaces()
    original_len = len(workspaces)
    # Don't delete the default workspace
    filtered = [w for w in workspaces if w["id"] != ws_id or w.get("is_default")]
    if len(filtered) == original_len:
        raise HTTPException(status_code=400, detail="Cannot delete default workspace or workspace not found")
    _save_workspaces(filtered)
    return {"status": "ok", "deleted": ws_id}


# ---------------------------------------------------------------------------
# Conversations Endpoints
# ---------------------------------------------------------------------------
@router.get("/conversations")
async def get_conversations():
    if CONV_FILE.exists():
        try:
            with open(CONV_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


@router.post("/conversations")
async def save_conversations(request: Request):
    try:
        convs = await request.json()
        CONV_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONV_FILE, "w", encoding="utf-8") as f:
            json.dump(convs, f, ensure_ascii=False, indent=2)
        return {"status": "ok"}
    except Exception as e:
        logging.getLogger("uvicorn.error").error(f"Failed to save conversations: {e}")
        return {"status": "error", "detail": str(e)}


@router.post("/conversations/clear")
def clear_conversations():
    CONV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONV_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    return {"status": "ok", "cleared": True}


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    if CONV_FILE.exists():
        try:
            with open(CONV_FILE, "r", encoding="utf-8") as f:
                convs = json.load(f)
            updated = [c for c in convs if c.get("id") != conv_id]
            with open(CONV_FILE, "w", encoding="utf-8") as f:
                json.dump(updated, f, ensure_ascii=False, indent=2)
            return {"status": "ok", "deleted": conv_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "deleted": conv_id}


# ---------------------------------------------------------------------------
# Data Deletion & Reset Controls (Critical Requirement)
# ---------------------------------------------------------------------------
class ResetConfirmation(BaseModel):
    confirmation: str


@router.post("/data/clear-cache")
def clear_application_cache():
    """Clears parse cache and LLM response cache from storage without deleting documents."""
    cache_files = [
        Path(WORKING_DIR) / "kv_store_parse_cache.json",
        Path(WORKING_DIR) / "kv_store_llm_response_cache.json",
    ]
    cleared = []
    for cf in cache_files:
        if cf.exists():
            try:
                cf.unlink()
                cleared.append(cf.name)
            except Exception:
                pass
    return {"status": "ok", "cleared_caches": cleared}


@router.post("/data/reset-all")
async def reset_all_data(payload: ResetConfirmation):
    """
    CRITICAL: Deletes ALL user data permanently.
    Requires exact confirmation phrase 'DELETE ALL DATA'.
    Purges:
      1. Uploaded files
      2. Parsed output directories
      3. Completed document logs
      4. Conversations history
      5. Vector databases & KV stores (LightRAG)
      6. Knowledge graph (GraphML & Neo4j if connected)
      7. Active jobs and queues
    Preserves:
      Source code, configs, .env, environment variables.
    """
    if payload.confirmation.strip() != "DELETE ALL DATA":
        raise HTTPException(
            status_code=400,
            detail="Confirmation phrase mismatch. Must type 'DELETE ALL DATA' exactly."
        )

    deleted_summary = {
        "uploads_deleted": 0,
        "output_dirs_deleted": 0,
        "kv_stores_deleted": 0,
        "vector_stores_deleted": 0,
        "graph_records_deleted": 0,
        "neo4j_nodes_deleted": 0,
        "conversations_cleared": False,
        "jobs_cleared": True,
    }

    # 1. Clear Uploads
    u_dir = Path(UPLOAD_DIR)
    if u_dir.exists():
        for item in u_dir.iterdir():
            if item.is_file():
                try:
                    item.unlink()
                    deleted_summary["uploads_deleted"] += 1
                except Exception:
                    pass
            elif item.is_dir() and item.name != "avatars":
                try:
                    shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    pass

    # 2. Clear Parsed Outputs
    o_dir = Path(OUTPUT_DIR)
    if o_dir.exists():
        for item in o_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                deleted_summary["output_dirs_deleted"] += 1
            elif item.is_file():
                item.unlink(missing_ok=True)

    # 3. Clear KV Stores & VDB Files in WORKING_DIR
    w_dir = Path(WORKING_DIR)
    if w_dir.exists():
        for f in w_dir.glob("kv_store_*.json"):
            f.unlink(missing_ok=True)
            deleted_summary["kv_stores_deleted"] += 1
        for f in w_dir.glob("vdb_*.json"):
            f.unlink(missing_ok=True)
            deleted_summary["vector_stores_deleted"] += 1

        # Clear GraphML
        graphml_file = w_dir / "graph_chunk_entity_relation.graphml"
        if graphml_file.exists():
            graphml_file.unlink(missing_ok=True)
            deleted_summary["graph_records_deleted"] += 1

        # Clear completed docs
        comp_file = w_dir / "completed_docs.json"
        if comp_file.exists():
            comp_file.unlink(missing_ok=True)

        # Clear conversations
        if CONV_FILE.exists():
            CONV_FILE.write_text("[]", encoding="utf-8")
            deleted_summary["conversations_cleared"] = True

    # 4. Clear Neo4j if driver connected
    if neo4j_manager.driver:
        try:
            async with neo4j_manager.driver.session(database=neo4j_manager.database) as session:
                res = await session.run("MATCH (n) DETACH DELETE n")
                deleted_summary["neo4j_nodes_deleted"] = 1
        except Exception:
            pass

    # 5. Clear in-memory jobs & queues
    job_manager.jobs.clear()
    job_manager.jobs_order.clear()
    job_manager.processing_queue.clear()
    job_manager.current_job = None

    return {
        "status": "ok",
        "message": "All user data, knowledge graphs, vector indices, and documents have been completely reset.",
        "summary": deleted_summary,
    }


# --- REAL-TIME LOG STREAMING ---
live_log_clients = set()


class AsyncSSELogHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        level = record.levelname.lower()
        data = json.dumps({"level": level, "message": msg})
        try:
            loop = asyncio.get_running_loop()
            for q in list(live_log_clients):
                loop.call_soon_threadsafe(self._safe_put, q, data)
        except RuntimeError:
            pass

    @staticmethod
    def _safe_put(q, data):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


sse_handler = AsyncSSELogHandler()
sse_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(sse_handler)
logging.getLogger("lightrag").addHandler(sse_handler)
logging.getLogger("raganything").addHandler(sse_handler)


@router.get("/logs/live")
async def live_logs_stream(request: Request):
    q = asyncio.Queue(maxsize=200)
    live_log_clients.add(q)

    async def log_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        except Exception:
            pass
        finally:
            live_log_clients.discard(q)

    return StreamingResponse(log_generator(), media_type="text/event-stream")
