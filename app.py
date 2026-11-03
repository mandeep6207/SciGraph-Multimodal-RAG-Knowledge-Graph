import os
import time
import shutil
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure venv Scripts directory is in PATH so mineru CLI is discoverable by subprocess
_venv_scripts = str(Path(__file__).parent / ".venv" / "Scripts")
if _venv_scripts not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _venv_scripts + os.pathsep + os.environ.get("PATH", "")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# LightRAG & RAG-Anything
from lightrag import LightRAG
from lightrag.utils import EmbeddingFunc
from raganything import RAGAnything, RAGAnythingConfig

# Local backend modules
from backend.llm_providers import OllamaProvider, OpenAIProvider
from backend.dependencies import (
    job_manager,
    neo4j_manager,
    document_reranker,
    state,
    base_logger,
)
from backend.jobs import Job, JobLogHandler
from backend.config import *

# Import our new API routers
from backend.routers import documents, graph, system, assistant


# ---------------------------------------------------------------------------
# Universal Concurrent Ingestion Pipeline
# ---------------------------------------------------------------------------
from backend.ingestion_engine import ingestion_engine

async def _process_document(job: Job, file_path: str):
    """Delegates document ingestion to the universal multi-worker engine."""
    await ingestion_engine.process_document(job, file_path)

async def _queue_worker():
    """Managed by concurrent IngestionEngine supervisor."""
    pass


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    logging.getLogger().setLevel(logging.INFO)

    # Short-circuit for test mode: tests set up state.rag themselves
    if os.getenv("TESTING") == "1":
        base_logger.info("TESTING mode: skipping full RAGAnything initialization.")
        yield
        return

    base_logger.info("Initialising RAGAnything …")

    for d in (WORKING_DIR, UPLOAD_DIR, OUTPUT_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)

    for k, v in [
        ("NEO4J_URI", NEO4J_URI),
        ("NEO4J_USERNAME", NEO4J_USERNAME),
        ("NEO4J_PASSWORD", NEO4J_PASSWORD),
        ("NEO4J_DATABASE", NEO4J_DATABASE),
    ]:
        os.environ.setdefault(k, v)

    os.environ["LLM_TIMEOUT"] = str(LLM_TIMEOUT)
    os.environ["EMBEDDING_TIMEOUT"] = str(EMBEDDING_TIMEOUT)

    config = RAGAnythingConfig(
        working_dir=WORKING_DIR,
        parser=PARSER,
        parse_method="auto",
        parser_output_dir=OUTPUT_DIR,
        enable_image_processing=bool(VISION_MODEL),
        enable_table_processing=bool(VISION_MODEL),
        enable_equation_processing=bool(VISION_MODEL),
    )

    # LLM engine routing
    common_kwargs = {
        "llm_model": LLM_MODEL,
        "vision_model": VISION_MODEL,
        "embed_model": EMBEDDING_MODEL,
        "timeout": LLM_TIMEOUT,
    }

    # Map engines to their specific Provider class and unique variables
    engine_registry = {
        "openai": {
            "class": OpenAIProvider,
            "kwargs": {"api_key": OPENAI_API_KEY, "base_url": OPENAI_BASE_URL},
        },
        "vllm": {
            "class": OpenAIProvider,
            "kwargs": {"api_key": OPENAI_API_KEY, "base_url": VLLM_BASE_URL},
        },
        "lmstudio": {
            "class": OpenAIProvider,
            "kwargs": {"api_key": OPENAI_API_KEY, "base_url": LM_STUDIO_BASE_URL},
        },
        "llamacpp": {
            "class": OpenAIProvider,
            "kwargs": {"api_key": OPENAI_API_KEY, "base_url": LLAMA_CPP_BASE_URL},
        },
        "ollama": {
            "class": OllamaProvider,
            "kwargs": {"base_url": OLLAMA_BASE_URL, "num_ctx": LLM_NUM_CTX},
        },
    }

    selected_engine = engine_registry.get(LLM_ENGINE, engine_registry["ollama"])
    ProviderClass = selected_engine["class"]
    specific_kwargs = selected_engine["kwargs"]

    provider = ProviderClass(**common_kwargs, **specific_kwargs)

    base_logger.info(
        f"Routing LLM using '{LLM_ENGINE}' engine via {ProviderClass.__name__} "
        f"at {specific_kwargs.get('base_url')}"
    )

    # Probe Neo4j connectivity if Neo4JStorage is requested
    effective_graph_storage = GRAPH_STORAGE
    if effective_graph_storage == "Neo4JStorage":
        neo4j_ready = False
        try:
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(NEO4J_URI)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 7687

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            conn_result = sock.connect_ex((host, port))
            sock.close()

            if conn_result == 0:
                neo4j_manager.connect()
                if neo4j_manager.driver:
                    async with neo4j_manager.driver.session(database=NEO4J_DATABASE) as session:
                        res = await session.run("RETURN 1")
                        await res.single()
                    neo4j_ready = True
                    base_logger.info("Connected to Neo4j successfully at %s", NEO4J_URI)
            else:
                base_logger.warning(
                    "Neo4j is not listening on %s:%s. Falling back to 'NetworkXStorage'.",
                    host,
                    port,
                )
        except Exception as e:
            base_logger.warning(
                "Neo4j is not reachable at %s (%s). Falling back to 'NetworkXStorage' for offline knowledge graph storage.",
                NEO4J_URI,
                e,
            )

        if not neo4j_ready:
            effective_graph_storage = "NetworkXStorage"

    effective_reranker = (
        document_reranker.rerank if (RERANKER_BASE_URL or ENABLE_LOCAL_RERANKER) else None
    )

    lightrag_instance = LightRAG(
        working_dir=WORKING_DIR,
        graph_storage=effective_graph_storage,
        llm_model_func=provider.llm,
        llm_model_max_async=LLM_MAX_ASYNC,
        chunk_token_size=CHUNK_SIZE,
        chunk_overlap_token_size=CHUNK_OVERLAP,
        entity_extract_max_gleaning=MAX_GLEANING,
        top_k=TOP_K,
        chunk_top_k=CHUNK_TOP_K,
        max_total_tokens=MAX_TOTAL_TOKENS,
        embedding_func=EmbeddingFunc(
            embedding_dim=EMBEDDING_DIM,
            max_token_size=MAX_EMBED_TOKENS,
            func=provider.embed,
        ),
        embedding_func_max_async=EMBEDDING_MAX_ASYNC,
        rerank_model_func=effective_reranker,
    )
    await lightrag_instance.initialize_storages()

    state.rag = RAGAnything(
        config=config,
        lightrag=lightrag_instance,
        llm_model_func=provider.llm,
        vision_model_func=provider.vision if VISION_MODEL else None,
        embedding_func=EmbeddingFunc(
            embedding_dim=EMBEDDING_DIM,
            max_token_size=MAX_EMBED_TOKENS,
            func=provider.embed,
        ),
    )

    if RERANKER_BASE_URL or ENABLE_LOCAL_RERANKER:
        base_logger.info("Preloading reranker in background thread...")
        asyncio.create_task(asyncio.to_thread(document_reranker.load))
    else:
        base_logger.info("High-speed vector cosine ranking enabled (local reranker bypassed for instant query responses).")
    base_logger.info("Starting Universal Concurrent Ingestion Engine (concurrency=%d)...", MAX_CONCURRENT_INGESTIONS)
    ingestion_engine.start()
    base_logger.info("RAGAnything ready with storage: %s", effective_graph_storage)
    yield
    await ingestion_engine.stop()
    await neo4j_manager.close()
    if hasattr(provider, "close"):
        await provider.close()


# ---------------------------------------------------------------------------
# FastAPI app setup
# ---------------------------------------------------------------------------
app = FastAPI(title=APP_FULL_TITLE, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Plug in the routers
app.include_router(documents.router)
app.include_router(graph.router)
app.include_router(system.router)
app.include_router(assistant.router)

# Mount Frontend
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount(
        "/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend"
    )

# Mount Uploads for file access & profile avatars
if Path(UPLOAD_DIR).exists():
    app.mount(
        "/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads"
    )


@app.get("/login", response_class=HTMLResponse)
def login_page():
    login_html = FRONTEND_DIR / "login.html"
    if login_html.exists():
        return HTMLResponse(login_html.read_text(encoding="utf-8"))
    return HTMLResponse("<meta http-equiv='refresh' content='0; url=/ui/login.html' />")


@app.get("/", response_class=HTMLResponse)
def root():
    landing = FRONTEND_DIR / "landing.html"
    if landing.exists():
        return HTMLResponse(landing.read_text(encoding="utf-8"))
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<p>Frontend not found. Place index.html in ./frontend/</p>")
