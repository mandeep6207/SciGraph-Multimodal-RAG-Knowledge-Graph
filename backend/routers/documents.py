import re
import json
import time
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.dependencies import job_manager, state
from backend.config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES

router = APIRouter(tags=["Documents & Queue"])


@router.get("/uploads")
def list_uploads():
    upload_path = Path(UPLOAD_DIR)
    if not upload_path.exists():
        return []

    files = []
    for f in upload_path.iterdir():
        if f.is_file():
            files.append(
                {
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                }
            )
    return sorted(files, key=lambda x: x["modified"], reverse=True)


@router.delete("/uploads/{filename}")
def delete_upload(filename: str):
    safe = Path(UPLOAD_DIR) / Path(filename).name
    if not safe.exists():
        raise HTTPException(status_code=404, detail="File not found")
    safe.unlink()
    return {"deleted": filename}


@router.post("/queue/pause")
def pause_queue():
    job_manager.queue_paused = True
    return {"paused": True}


@router.post("/queue/resume")
def resume_queue():
    job_manager.queue_paused = False
    return {"paused": False}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
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

    job = job_manager.new_job(safe_filename)
    job.push("queued", f"File received: {safe_filename}")
    job_manager.processing_queue.append((job, str(dest)))

    return {
        "job_id": job.id,
        "id": job.id,
        "filename": safe_filename,
        "queue_position": len(job_manager.processing_queue),
    }


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
                yield f"data: {json.dumps({'index': sent, **events[sent]})}\n\n"
                sent += 1
                idle = 0

            if job.status in ("done", "error"):
                events = list(job.events)
                while sent < len(events):
                    yield f"data: {json.dumps({'index': sent, **events[sent]})}\n\n"
                    sent += 1
                break

            idle += 1
            if idle % 50 == 0:
                yield ": keepalive\n\n"

            await asyncio.sleep(0.3)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
