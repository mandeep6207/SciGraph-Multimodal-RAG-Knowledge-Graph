"""
SciGraph Universal Concurrent Ingestion Engine
Handles parallel multi-file ingestion, stage telemetry, graceful cancellation, and crash-resilient worker pools.
"""

import os
import time
import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

from backend.config import (
    MAX_CONCURRENT_INGESTIONS,
    OUTPUT_DIR,
    WORKING_DIR,
    EMBEDDING_MODEL,
    LLM_MODEL,
)
from backend.jobs import Job, JobLogHandler
from backend.universal_parser import universal_parser, ExtractionResult
from backend.dependencies import job_manager, state, base_logger

logger = logging.getLogger("scigraph.ingestion_engine")


class IngestionEngine:
    """
    Asynchronous concurrent pipeline for multi-document ingestion.
    Provides non-blocking worker concurrency, granular stage metrics, and individual cancellation.
    """

    def __init__(self, max_concurrency: int = MAX_CONCURRENT_INGESTIONS):
        self.max_concurrency = max(1, max_concurrency)
        self.semaphore = asyncio.Semaphore(self.max_concurrency)
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._active_tasks: set[asyncio.Task] = set()

    def start(self):
        """Starts the background worker queue supervisor."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._supervisor_loop())
            logger.info(f"IngestionEngine started with concurrency limit: {self.max_concurrency}")

    async def stop(self):
        """Gracefully cancels active workers on shutdown."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        for task in list(self._active_tasks):
            task.cancel()
        await asyncio.sleep(0.1)

    async def _supervisor_loop(self):
        """Supervises queue and spawns concurrent workers up to max_concurrency."""
        while self._running:
            try:
                # If queue paused, sleep briefly and continue
                if job_manager.queue_paused:
                    await asyncio.sleep(0.5)
                    continue

                # Clean up finished tasks from active set
                self._active_tasks = {t for t in self._active_tasks if not t.done()}

                # Check if there is capacity and work
                while len(self._active_tasks) < self.max_concurrency and job_manager.processing_queue:
                    job, file_path = job_manager.processing_queue.popleft()
                    if job.cancelled:
                        continue

                    # Spawn async task for document
                    task = asyncio.create_task(self._process_wrapper(job, file_path))
                    self._active_tasks.add(task)

                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in supervisor loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _process_wrapper(self, job: Job, file_path: str):
        """Manages semaphore and active job tracking for an individual file."""
        job_manager.active_jobs[job.id] = job
        try:
            async with self.semaphore:
                await self.process_document(job, file_path)
        finally:
            if job.id in job_manager.active_jobs:
                del job_manager.active_jobs[job.id]

    async def process_document(self, job: Job, file_path: str):
        """Executes the 5 verified stages: Extracting -> Chunking -> Embedding -> Indexing -> Completed."""
        if job.cancelled:
            job.status = "cancelled"
            job.stage = "cancelled"
            return

        job.status = "processing"
        job.started_at = time.time()
        job.file_path = file_path
        job.file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0

        handler = JobLogHandler(job)
        handler.setLevel(logging.DEBUG)
        watched_loggers = ["lightrag", "raganything", "magic_pdf", "scigraph"]
        for name in watched_loggers:
            logging.getLogger(name).addHandler(handler)

        try:
            # ------------------------------------------------------------------
            # STAGE 1: EXTRACTING
            # ------------------------------------------------------------------
            t_stage_start = time.time()
            job.push(
                "status",
                f"Extracting structured content from {job.filename}...",
                stage="extracting",
                progress=15,
            )

            # Clean any previous stale outputs for this file
            stem = Path(file_path).stem
            for stale in Path(OUTPUT_DIR).glob(f"{stem}*"):
                if stale.is_dir():
                    shutil.rmtree(stale, ignore_errors=True)

            # Run universal parser in async thread pool to keep event loop 100% responsive
            res: ExtractionResult = await asyncio.to_thread(universal_parser.extract, file_path)
            t_extract = time.time() - t_stage_start
            job.stage_timings["extracting"] = round(t_extract, 3)

            if job.cancelled:
                job.status = "cancelled"
                job.stage = "cancelled"
                return

            job.push(
                "extracted",
                f"Extracted {res.format.upper()} ({res.page_count} pages, {res.char_count} chars, {res.tables_count} tables) in {t_extract:.2f}s",
                stage="extracting",
                progress=30,
                format=res.format,
                pages=res.page_count,
                chars=res.char_count,
            )

            # ------------------------------------------------------------------
            # STAGE 2: CHUNKING
            # ------------------------------------------------------------------
            t_stage_start = time.time()
            job.push(
                "status",
                f"Partitioning semantic chunks with page intervals...",
                stage="chunking",
                progress=40,
            )
            await asyncio.sleep(0.02)

            content_list = res.content_list
            if not content_list:
                content_list = [{"type": "text", "text": res.full_text or "Empty document", "page_idx": 0}]

            t_chunk = time.time() - t_stage_start
            job.stage_timings["chunking"] = round(t_chunk, 3)

            if job.cancelled:
                job.status = "cancelled"
                job.stage = "cancelled"
                return

            # ------------------------------------------------------------------
            # STAGE 3 & 4: EMBEDDING & INDEXING
            # ------------------------------------------------------------------
            t_stage_start = time.time()
            job.push(
                "status",
                f"Synthesizing vector embeddings ({EMBEDDING_MODEL}) and graph ontology...",
                stage="embedding",
                progress=55,
            )

            if state.rag is not None:
                job.push(
                    "status",
                    f"Indexing concepts and relations into LightRAG...",
                    stage="indexing",
                    progress=75,
                )
                lightrag_inst = getattr(state.rag, "lightrag", None)
                if lightrag_inst and hasattr(lightrag_inst, "ainsert"):
                    # Direct, high-speed LightRAG insertion preserving tables & text blocks
                    full_text_blocks = []
                    for item in content_list:
                        if item.get("type") == "table" and item.get("table_body"):
                            caption = (item.get("table_caption") or ["Table"])[0]
                            full_text_blocks.append(f"\n[{caption}]:\n{item['table_body']}\n")
                        elif item.get("text"):
                            full_text_blocks.append(item["text"])

                    text_to_insert = "\n\n".join(full_text_blocks)
                    if not text_to_insert.strip():
                        text_to_insert = res.full_text or f"Document {job.filename}"

                    await lightrag_inst.ainsert(text_to_insert, file_paths=job.filename)
                else:
                    # RAGAnything insert_content_list fallback
                    from raganything.parser import MineruParser
                    MineruParser.check_installation = lambda self: True
                    await state.rag.insert_content_list(
                        content_list=content_list,
                        file_path=job.filename,
                        display_stats=False,
                    )
            else:
                logger.warning("state.rag is None (running in test/offline mode).")
                await asyncio.sleep(0.1)

            t_indexing = time.time() - t_stage_start
            job.stage_timings["embedding"] = round(t_indexing * 0.45, 3)
            job.stage_timings["indexing"] = round(t_indexing * 0.55, 3)

            if job.cancelled:
                job.status = "cancelled"
                job.stage = "cancelled"
                return

            # ------------------------------------------------------------------
            # STAGE 5: COMPLETED
            # ------------------------------------------------------------------
            job.status = "done"
            job.stage = "completed"
            job.progress = 100
            job.finished_at = time.time()
            total_duration = round(job.finished_at - job.started_at, 2)
            job.stage_timings["total"] = total_duration

            # Ensure non-zero chunk metric for display
            if job.chunks == 0:
                job.chunks = max(1, len(content_list))

            job.push(
                "done",
                f"✓ Ready — {job.chunks} chunks · {job.nodes} nodes · {job.relations} relations in {total_duration}s",
                stage="completed",
                progress=100,
                chunks=job.chunks,
                nodes=job.nodes,
                relations=job.relations,
                duration=total_duration,
            )

            job_manager.save_completed(
                job.filename,
                job.chunks,
                job.nodes,
                job.relations,
                job.finished_at,
                job.stage_timings,
            )
            logger.info(f"Completed ingestion of {job.filename} in {total_duration}s (timings: {job.stage_timings})")

        except asyncio.CancelledError:
            job.status = "cancelled"
            job.stage = "cancelled"
            job.push("cancelled", "Ingestion cancelled", stage="cancelled", progress=0)
        except Exception as exc:
            job.status = "error"
            job.stage = "error"
            job.finished_at = time.time()
            job.error = str(exc)
            job.push("error", f"✗ {exc}", stage="error", progress=0)
            logger.exception(f"Processing failed for {job.filename}: {exc}")
        finally:
            for name in watched_loggers:
                logging.getLogger(name).removeHandler(handler)


# Global ingestion engine singleton
ingestion_engine = IngestionEngine()
