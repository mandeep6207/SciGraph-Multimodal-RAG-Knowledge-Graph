import re
import json
import time
import shutil
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Query
from fastapi.responses import StreamingResponse

from backend.dependencies import job_manager, state
from backend.config import UPLOAD_DIR, OUTPUT_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, COMPLETED_LOG

router = APIRouter(tags=["Documents & Queue"])


@router.get("/uploads")
def list_uploads():
    upload_path = Path(UPLOAD_DIR)
    if not upload_path.exists():
        return []

    completed = job_manager.load_completed()
    files = []
    for f in upload_path.iterdir():
        if f.is_file():
            meta = completed.get(f.name, {})
            files.append(
                {
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                    "status": "completed" if f.name in completed else "uploaded",
                    "chunks": meta.get("chunks", 0),
                    "nodes": meta.get("nodes", 0),
                    "relations": meta.get("relations", 0),
                    "finished_at": meta.get("finished_at", 0),
                    "timings": meta.get("timings", {}),
                }
            )
    return sorted(files, key=lambda x: x["modified"], reverse=True)


def _delete_document_data(filename: str) -> dict:
    safe_name = Path(filename).name
    deleted_upload = False
    deleted_output = False
    removed_log = False

    # 1. Delete upload file
    upload_file = Path(UPLOAD_DIR) / safe_name
    if upload_file.exists():
        upload_file.unlink()
        deleted_upload = True

    # 2. Delete parsed outputs
    stem = Path(safe_name).stem
    out_path = Path(OUTPUT_DIR)
    if out_path.exists():
        for d in out_path.glob(f"{stem}*"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
                deleted_output = True
            elif d.is_file():
                d.unlink(missing_ok=True)
                deleted_output = True

    # 3. Remove from completed_docs.json
    completed = job_manager.load_completed()
    if safe_name in completed:
        del completed[safe_name]
        try:
            COMPLETED_LOG.write_text(json.dumps(completed, indent=2), encoding="utf-8")
            removed_log = True
        except Exception:
            pass

    return {
        "deleted": safe_name,
        "upload_file_deleted": deleted_upload,
        "output_dir_deleted": deleted_output,
        "completed_log_removed": removed_log,
    }


@router.delete("/uploads/{filename}")
def delete_upload(filename: str):
    result = _delete_document_data(filename)
    if not result["upload_file_deleted"] and not result["output_dir_deleted"] and not result["completed_log_removed"]:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.delete("/documents/{filename}")
def delete_document(filename: str):
    result = _delete_document_data(filename)
    if not result["upload_file_deleted"] and not result["output_dir_deleted"] and not result["completed_log_removed"]:
        raise HTTPException(status_code=404, detail="File not found")
    return result


# ------------------------------------------------------------------------------
# Queue Controls (Pause, Resume, Cancel, Retry, Remove, Status)
# ------------------------------------------------------------------------------
@router.post("/queue/pause")
def pause_queue():
    job_manager.queue_paused = True
    return {"paused": True, "message": "Ingestion queue paused"}


@router.post("/queue/resume")
def resume_queue():
    job_manager.queue_paused = False
    return {"paused": False, "message": "Ingestion queue resumed"}


@router.get("/queue/status")
def get_queue_status():
    return job_manager.get_queue_status()


@router.post("/queue/cancel/{job_id}")
def cancel_job(job_id: str):
    success = job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"cancelled": True, "job_id": job_id}


@router.post("/queue/retry/{job_id}")
def retry_job(job_id: str):
    success = job_manager.retry_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot retry job (not found or original file missing)")
    return {"retried": True, "job_id": job_id}


@router.post("/queue/remove/{job_id}")
def remove_job(job_id: str):
    success = job_manager.remove_job(job_id)
    return {"removed": success, "job_id": job_id}


@router.delete("/queue/completed")
def clear_completed_jobs():
    count = job_manager.clear_completed()
    return {"cleared": count}


# ------------------------------------------------------------------------------
# Upload & Batch Ingestion Endpoints
# ------------------------------------------------------------------------------
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    force: bool = Query(False, description="Force re-parsing if already completed")
):
    if state.rag is None:
        raise HTTPException(status_code=503, detail="RAGAnything not initialised yet")
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    raw_name = Path(file.filename).name
    ext = Path(raw_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not supported")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 500 MB)")

    safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(raw_name).stem)
    if not safe_stem:
        safe_stem = f"upload_{int(time.time())}"
    safe_filename = f"{safe_stem}{ext}"

    upload_path = Path(UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    dest = upload_path / safe_filename
    with dest.open("wb") as fh:
        fh.write(content)

    # Deduplication check: check if already completed
    completed = job_manager.load_completed()
    if safe_filename in completed and not force:
        cached = completed[safe_filename]
        job = job_manager.new_job(safe_filename, file_path=str(dest), file_size=len(content))
        job.status = "done"
        job.stage = "completed"
        job.progress = 100
        job.chunks = cached.get("chunks", 0)
        job.nodes = cached.get("nodes", 0)
        job.relations = cached.get("relations", 0)
        job.finished_at = cached.get("finished_at", time.time())
        job.stage_timings = cached.get("timings", {})
        job.push("cached", f"Document already indexed ({job.chunks} chunks, {job.nodes} nodes). Using existing index.", stage="completed", progress=100)
        job.push("done", f"✓ Ready — {job.chunks} chunks · {job.nodes} nodes", stage="completed", progress=100)
        return {
            "job_id": job.id,
            "id": job.id,
            "filename": safe_filename,
            "status": "done",
            "stage": "completed",
            "progress": 100,
            "cached": True,
            "chunks": job.chunks,
            "nodes": job.nodes,
            "relations": job.relations,
            "timings": job.stage_timings,
            "queue_position": 0,
        }

    job = job_manager.new_job(safe_filename, file_path=str(dest), file_size=len(content))
    job.push("queued", f"File received: {safe_filename}", stage="queued", progress=0)
    job_manager.processing_queue.append((job, str(dest)))

    return {
        "job_id": job.id,
        "id": job.id,
        "filename": safe_filename,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "cached": False,
        "queue_position": len(job_manager.processing_queue),
    }


@router.post("/upload/batch")
async def upload_documents_batch(
    files: list[UploadFile] = File(...),
    force: bool = Query(False, description="Force re-parsing if already completed")
):
    if state.rag is None:
        raise HTTPException(status_code=503, detail="RAGAnything not initialised yet")
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results = []
    completed = job_manager.load_completed()
    upload_path = Path(UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)

    for file in files:
        if not file.filename:
            results.append({
                "filename": "unknown",
                "status": "error",
                "error": "File missing filename",
            })
            continue

        raw_name = Path(file.filename).name
        ext = Path(raw_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            results.append({
                "filename": raw_name,
                "status": "error",
                "error": f"File type '{ext}' not supported. Supported: PDF, Office, CSV, LaTeX, Text, Web, Data, Images.",
            })
            continue

        try:
            content = await file.read()
            if len(content) > MAX_UPLOAD_BYTES:
                results.append({
                    "filename": raw_name,
                    "status": "error",
                    "error": "File exceeds maximum size limit (500 MB)",
                })
                continue

            safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(raw_name).stem)
            if not safe_stem:
                safe_stem = f"upload_{int(time.time())}_{len(results)}"
            safe_filename = f"{safe_stem}{ext}"

            dest = upload_path / safe_filename
            with dest.open("wb") as fh:
                fh.write(content)

            if safe_filename in completed and not force:
                cached = completed[safe_filename]
                job = job_manager.new_job(safe_filename, file_path=str(dest), file_size=len(content))
                job.status = "done"
                job.stage = "completed"
                job.progress = 100
                job.chunks = cached.get("chunks", 0)
                job.nodes = cached.get("nodes", 0)
                job.relations = cached.get("relations", 0)
                job.finished_at = cached.get("finished_at", time.time())
                job.stage_timings = cached.get("timings", {})
                job.push("cached", f"Document already indexed ({job.chunks} chunks).", stage="completed", progress=100)
                job.push("done", f"✓ Ready — {job.chunks} chunks", stage="completed", progress=100)
                results.append({
                    "filename": safe_filename,
                    "original_name": raw_name,
                    "job_id": job.id,
                    "id": job.id,
                    "status": "done",
                    "stage": "completed",
                    "progress": 100,
                    "cached": True,
                    "chunks": job.chunks,
                    "nodes": job.nodes,
                    "relations": job.relations,
                    "timings": job.stage_timings,
                    "queue_position": 0,
                })
            else:
                job = job_manager.new_job(safe_filename, file_path=str(dest), file_size=len(content))
                job.push("queued", f"File received: {safe_filename}", stage="queued", progress=0)
                job_manager.processing_queue.append((job, str(dest)))
                results.append({
                    "filename": safe_filename,
                    "original_name": raw_name,
                    "job_id": job.id,
                    "id": job.id,
                    "status": "queued",
                    "stage": "queued",
                    "progress": 0,
                    "cached": False,
                    "queue_position": len(job_manager.processing_queue),
                })
        except Exception as exc:
            results.append({
                "filename": raw_name,
                "status": "error",
                "error": str(exc),
            })

    successful_count = sum(1 for r in results if r["status"] in ("queued", "done"))
    return {
        "total": len(files),
        "successful": successful_count,
        "failed": len(files) - successful_count,
        "results": results,
    }


# ------------------------------------------------------------------------------
# Non-Blocking Real-Time SSE Progress Stream
# ------------------------------------------------------------------------------
@router.get("/progress/{job_id}")
async def progress_stream(job_id: str, request: Request, from_index: int = 0):
    if job_id not in job_manager.jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def generate() -> AsyncGenerator[str, None]:
        job = job_manager.jobs[job_id]
        sent = from_index
        idle = 0
        while True:
            if await request.is_disconnected():
                break

            events = list(job.events)
            while sent < len(events):
                ev = events[sent]
                payload = {
                    "index": sent,
                    "job_id": job.id,
                    "filename": job.filename,
                    "status": job.status,
                    "stage": job.stage,
                    "progress": job.progress,
                    "chunks": job.chunks,
                    "nodes": job.nodes,
                    "relations": job.relations,
                    "timings": job.stage_timings,
                    **ev,
                }
                yield f"data: {json.dumps(payload)}\n\n"
                sent += 1
                idle = 0

            if job.status in ("done", "error", "cancelled"):
                # Send remaining events if any
                events = list(job.events)
                while sent < len(events):
                    ev = events[sent]
                    payload = {
                        "index": sent,
                        "job_id": job.id,
                        "filename": job.filename,
                        "status": job.status,
                        "stage": job.stage,
                        "progress": job.progress,
                        "chunks": job.chunks,
                        "nodes": job.nodes,
                        "relations": job.relations,
                        "timings": job.stage_timings,
                        **ev,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    sent += 1
                break

            idle += 1
            if idle % 50 == 0:
                yield ": keepalive\n\n"

            await asyncio.sleep(0.15)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
