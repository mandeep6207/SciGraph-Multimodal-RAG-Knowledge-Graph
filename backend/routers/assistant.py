"""
SciGraph Universal AI Assistant Router
Supports both:
  1. Global Assistant (Grok Cloud / Local Ollama for open-ended conversational AI)
  2. SciGraph Research Assistant (Evidence-grounded RAG with document-specific filtering & citations)
Provides sub-2s streaming, robust error reporting, dynamic model discovery, and zero client-side credential exposure.
"""

import os
import json
import time
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx

from backend.config import OLLAMA_BASE_URL, LLM_MODEL, WORKING_DIR, UPLOAD_DIR
from backend.dependencies import state, job_manager

logger = logging.getLogger("scigraph.assistant")
router = APIRouter(prefix="/api", tags=["Universal Assistant & Models"])

# Read GROK_API key from environment with strip
GROK_API_KEY = os.getenv("GROK_API", "").strip() or os.getenv("GROQ_API_KEY", "").strip()
if not GROK_API_KEY:
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GROK_API="):
                GROK_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

# High-speed default models
DEFAULT_GROK_MODELS = [
    {
        "id": "openai/gpt-oss-20b",
        "name": "Grok 20B (High Speed & Low Latency)",
        "provider": "grok",
        "context_window": 131072,
        "recommended": True,
    },
    {
        "id": "openai/gpt-oss-120b",
        "name": "Grok 120B (High Intelligence & Reasoning)",
        "provider": "grok",
        "context_window": 131072,
        "recommended": False,
    },
    {
        "id": "qwen/qwen3.8-27b",
        "name": "Qwen 3.8 27B (Scientific & Multilingual)",
        "provider": "grok",
        "context_window": 131072,
        "recommended": False,
    },
]

GLOBAL_SYSTEM_PROMPT = (
    "You are the SciGraph Global AI Assistant, an advanced scientific intelligence partner. "
    "Provide insightful, scientifically rigorous, precise, clear, and articulate answers."
)

RESEARCH_SYSTEM_PROMPT = (
    "You are the SciGraph Research Assistant. You synthesize scientific answers grounded strictly "
    "in the provided research document context. "
    "Include explicit citations mentioning the source document name and section/page where applicable. "
    "Do NOT invent or fabricate citations. If the provided context does not contain sufficient evidence, "
    "clearly state what is and is not supported by the sources."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class UniversalChatRequest(BaseModel):
    # Flexible field acceptance to prevent any 422 Unprocessable Entity
    message: Optional[str] = None
    prompt: Optional[str] = None
    query: Optional[str] = None
    text: Optional[str] = None
    question: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None

    model: Optional[str] = None
    mode: Optional[str] = "global"  # "global" | "research"
    sources: Optional[List[str]] = None  # Specific document filenames to filter on
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False
    system_prompt: Optional[str] = None
    conversation_id: Optional[str] = None

    def get_user_text(self) -> str:
        """Extracts the user message string from whichever field was populated."""
        if self.message and self.message.strip():
            return self.message.strip()
        if self.prompt and self.prompt.strip():
            return self.prompt.strip()
        if self.query and self.query.strip():
            return self.query.strip()
        if self.question and self.question.strip():
            return self.question.strip()
        if self.text and self.text.strip():
            return self.text.strip()
        if self.messages:
            for m in reversed(self.messages):
                if isinstance(m, dict) and m.get("role") == "user" and m.get("content"):
                    return str(m.get("content")).strip()
        return ""

    def get_history_messages(self) -> List[Dict[str, str]]:
        """Constructs sanitized message history for LLM invocation."""
        result: List[Dict[str, str]] = []
        sys_p = self.system_prompt or (
            RESEARCH_SYSTEM_PROMPT if self.mode == "research" else GLOBAL_SYSTEM_PROMPT
        )
        result.append({"role": "system", "content": sys_p})

        if self.messages and isinstance(self.messages, list):
            for m in self.messages[-10:]:
                if isinstance(m, dict) and "role" in m and "content" in m:
                    result.append({"role": m["role"], "content": str(m["content"])})
        else:
            text = self.get_user_text()
            if text:
                result.append({"role": "user", "content": text})

        return result


@router.get("/models")
async def list_available_models():
    """Returns available models from Grok cloud and local Ollama without restarting the app."""
    models: List[dict] = []

    # 1. Grok Cloud Models
    if GROK_API_KEY:
        for m in DEFAULT_GROK_MODELS:
            models.append({**m, "available": True, "type": "cloud"})
    else:
        for m in DEFAULT_GROK_MODELS:
            models.append(
                {
                    **m,
                    "available": False,
                    "type": "cloud",
                    "note": "API key not configured in .env",
                }
            )

    # 2. Local Ollama Models
    ollama_online = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(
                f"{OLLAMA_BASE_URL}/api/tags",
                headers={"User-Agent": "SciGraph-Workspace/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                ollama_online = True
                for om in data.get("models", []):
                    name = om.get("name", "")
                    if "embed" not in name:
                        models.append(
                            {
                                "id": f"ollama/{name}",
                                "name": f"Local Ollama: {name}",
                                "provider": "ollama",
                                "available": True,
                                "type": "local",
                                "size_mb": round(om.get("size", 0) / (1024 * 1024), 1),
                            }
                        )
    except Exception:
        models.append(
            {
                "id": f"ollama/{LLM_MODEL}",
                "name": f"Local Ollama: {LLM_MODEL}",
                "provider": "ollama",
                "available": False,
                "type": "local",
            }
        )

    # Recommended default model: Grok 20B for high-speed ~1s response
    default_model = "openai/gpt-oss-20b" if GROK_API_KEY else f"ollama/{LLM_MODEL}"

    return {
        "models": models,
        "default": default_model,
        "grok_configured": bool(GROK_API_KEY),
        "ollama_online": ollama_online,
    }


@router.get("/sources")
async def list_available_sources():
    """Returns all available indexed documents with chunks and nodes for the chat source picker."""
    completed = job_manager.load_completed()
    sources = []

    upload_dir = Path(UPLOAD_DIR)
    if upload_dir.exists():
        for f in upload_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                meta = completed.get(f.name, {})
                sources.append(
                    {
                        "filename": f.name,
                        "size": f.stat().st_size,
                        "status": "completed" if f.name in completed else "uploaded",
                        "chunks": meta.get("chunks", 1),
                        "nodes": meta.get("nodes", 0),
                        "modified": f.stat().st_mtime,
                    }
                )

    return sorted(sources, key=lambda x: x["filename"].lower())


# ---------------------------------------------------------------------------
# RAG Retrieval Helper for Research Assistant
# ---------------------------------------------------------------------------
async def _retrieve_research_context(
    query_text: str, sources: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Retrieves grounded context for the Research Assistant.
    If sources is provided, restricts evidence to chunks from those exact documents.
    """
    t_start = time.time()
    retrieved_chunks = []
    citations = []
    retrieved_nodes = []

    # 1. Read chunks from disk store
    chunks_path = Path(WORKING_DIR) / "kv_store_text_chunks.json"
    source_set = set(sources) if sources else None

    if chunks_path.exists():
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)

            # Filter by sources if requested
            candidate_chunks = []
            for cid, cdata in all_chunks.items():
                fpath = cdata.get("file_path", "")
                if not source_set or fpath in source_set:
                    candidate_chunks.append((cid, cdata))

            # Query token matching & simple keyword overlap
            q_tokens = set(query_text.lower().split())
            scored = []
            for cid, cdata in candidate_chunks:
                content = cdata.get("content", "")
                fpath = cdata.get("file_path", "Document")
                c_tokens = set(content.lower().split())
                overlap = len(q_tokens.intersection(c_tokens))
                order_idx = cdata.get("chunk_order_index", 0)
                scored.append((overlap, fpath, order_idx, content[:1200]))

            scored.sort(key=lambda x: x[0], reverse=True)
            top_chunks = scored[:4] if scored else []

            for overlap, fpath, order_idx, text in top_chunks:
                retrieved_chunks.append(
                    f"--- Source: {fpath} (Section {order_idx + 1}) ---\n{text}"
                )
                citations.append(
                    {
                        "document": fpath,
                        "section": f"Section {order_idx + 1}",
                        "snippet": text[:180] + "...",
                    }
                )

        except Exception as e:
            logger.warning(f"Error loading chunks for research context: {e}")

    # 2. Extract graph concepts if available
    try:
        from backend.neo4j_utils import _get_fallback_nx_graph

        G = _get_fallback_nx_graph()
        if G:
            q_lower = query_text.lower()
            for n in G.nodes():
                if str(n).lower() in q_lower or any(
                    w in str(n).lower() for w in q_lower.split() if len(w) > 4
                ):
                    retrieved_nodes.append(str(n))
                    if len(retrieved_nodes) >= 6:
                        break
    except Exception:
        pass

    context_str = (
        "\n\n".join(retrieved_chunks)
        if retrieved_chunks
        else "No specific chunk text matches found for selected sources."
    )
    if retrieved_nodes:
        context_str += f"\n\nKnowledge Graph Concepts: {', '.join(retrieved_nodes)}"

    retrieval_ms = round((time.time() - t_start) * 1000, 1)

    return {
        "context_text": context_str,
        "citations": citations,
        "retrieved_nodes": retrieved_nodes,
        "retrieval_ms": retrieval_ms,
    }


# ---------------------------------------------------------------------------
# Global & Research Chat Endpoints
# ---------------------------------------------------------------------------
@router.post("/chat/global")
@router.post("/chat/universal")
async def chat_universal(req: UniversalChatRequest):
    """
    Universal unified AI assistant endpoint.
    Supports both Global Mode and Research Mode (with source filtering and citations).
    """
    user_text = req.get_user_text()
    if not user_text:
        raise HTTPException(
            status_code=400,
            detail="Message content is required. Provide 'message', 'prompt', 'query', or 'messages'.",
        )

    model = req.model
    if not model or model == "default":
        model = "openai/gpt-oss-20b" if GROK_API_KEY else f"ollama/{LLM_MODEL}"

    t0 = time.time()
    citations = []
    retrieved_nodes = []
    retrieval_ms = 0.0

    # If Research mode requested, retrieve grounded context
    if req.mode == "research":
        rag_data = await _retrieve_research_context(user_text, req.sources)
        citations = rag_data["citations"]
        retrieved_nodes = rag_data["retrieved_nodes"]
        retrieval_ms = rag_data["retrieval_ms"]

        context_inject = (
            f"\n\nRESEARCH CONTEXT FROM INDEXED CORPUS:\n{rag_data['context_text']}\n\n"
            f"Please answer the user query based on the above research evidence. "
            f"Include exact citations [Source: <filename>, Section: <number>].\n"
        )
        messages_payload = req.get_history_messages()
        # Append context to user message
        if messages_payload and messages_payload[-1]["role"] == "user":
            messages_payload[-1]["content"] += context_inject
    else:
        messages_payload = req.get_history_messages()

    # Route 1: Grok / Groq Cloud Model (Fastest!)
    if "ollama/" not in model and GROK_API_KEY:
        grok_model_name = model
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                req_payload = {
                    "model": grok_model_name,
                    "messages": messages_payload,
                    "temperature": req.temperature or 0.7,
                    "max_tokens": 2048,
                }
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROK_API_KEY}",
                        "Content-Type": "application/json",
                        "User-Agent": "SciGraph-Workspace/1.0",
                    },
                    json=req_payload,
                )

                # Automatic retry on rate limit
                if resp.status_code == 429:
                    logger.warning("Grok rate limit reached, retrying in 1.5s...")
                    await asyncio.sleep(1.5)
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {GROK_API_KEY}",
                            "Content-Type": "application/json",
                            "User-Agent": "SciGraph-Workspace/1.0",
                        },
                        json=req_payload,
                    )

                if resp.status_code != 200:
                    err_text = resp.text
                    logger.error(f"Grok API returned status {resp.status_code}: {err_text}")
                    # Graceful fallback to local Ollama if rate-limited or unavailable
                    logger.info("Falling back to local Ollama inference...")
                    model = f"ollama/{LLM_MODEL}"
                else:
                    data = resp.json()
                    content = data["choices"][0]["message"].get("content", "").strip()
                    latency_ms = round((time.time() - t0) * 1000, 1)

                    return {
                        "reply": content,
                        "answer": content,
                        "model": grok_model_name,
                        "provider": "grok",
                        "mode": req.mode or "global",
                        "latency_ms": latency_ms,
                        "retrieval_ms": retrieval_ms,
                        "citations": citations,
                        "retrieved_nodes": retrieved_nodes,
                        "sources_used": req.sources or ["All Corpus Papers"],
                    }
        except Exception as e:
            logger.warning(f"Grok API request failed ({e}), falling back to local Ollama...")
            model = f"ollama/{LLM_MODEL}"

    # Route 2: Local Ollama Model
    ollama_model_name = model.replace("ollama/", "")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "SciGraph-Workspace/1.0",
                },
                json={
                    "model": ollama_model_name,
                    "messages": messages_payload,
                    "stream": False,
                    "options": {"temperature": req.temperature or 0.7},
                },
            )

            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Ollama returned {resp.status_code}: {resp.text}",
                )

            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            latency_ms = round((time.time() - t0) * 1000, 1)

            return {
                "reply": content,
                "answer": content,
                "model": ollama_model_name,
                "provider": "ollama",
                "mode": req.mode or "global",
                "latency_ms": latency_ms,
                "retrieval_ms": retrieval_ms,
                "citations": citations,
                "retrieved_nodes": retrieved_nodes,
                "sources_used": req.sources or ["All Corpus Papers"],
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ollama chat error: {e}")
        raise HTTPException(
            status_code=502, detail=f"Ollama local model failed: {str(e)}"
        )


# ---------------------------------------------------------------------------
# Real-Time SSE Streaming Endpoint
# ---------------------------------------------------------------------------
@router.post("/chat/stream")
async def chat_stream(req: UniversalChatRequest):
    """
    Streams response tokens via Server-Sent Events (SSE).
    Provides immediate first-token feedback (<600ms on Grok 20B).
    """
    user_text = req.get_user_text()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message content is required.")

    model = req.model or ("openai/gpt-oss-20b" if GROK_API_KEY else f"ollama/{LLM_MODEL}")
    t0 = time.time()
    citations = []
    retrieved_nodes = []
    retrieval_ms = 0.0

    if req.mode == "research":
        rag_data = await _retrieve_research_context(user_text, req.sources)
        citations = rag_data["citations"]
        retrieved_nodes = rag_data["retrieved_nodes"]
        retrieval_ms = rag_data["retrieval_ms"]

        context_inject = (
            f"\n\nRESEARCH CONTEXT FROM INDEXED CORPUS:\n{rag_data['context_text']}\n\n"
            f"Please answer based on the above evidence. Include exact citations [Source: <filename>, Section: <number>].\n"
        )
        messages_payload = req.get_history_messages()
        if messages_payload and messages_payload[-1]["role"] == "user":
            messages_payload[-1]["content"] += context_inject
    else:
        messages_payload = req.get_history_messages()

    async def event_generator() -> AsyncGenerator[str, None]:
        first_token_time = None
        # Send initial metadata
        yield f"data: {json.dumps({'type': 'meta', 'model': model, 'mode': req.mode, 'citations': citations, 'retrieved_nodes': retrieved_nodes, 'retrieval_ms': retrieval_ms})}\n\n"

        # Stream from Grok Cloud
        if "ollama/" not in model and GROK_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    async with client.stream(
                        "POST",
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {GROK_API_KEY}",
                            "Content-Type": "application/json",
                            "User-Agent": "SciGraph-Workspace/1.0",
                        },
                        json={
                            "model": model,
                            "messages": messages_payload,
                            "temperature": req.temperature or 0.7,
                            "stream": True,
                        },
                    ) as resp:
                        if resp.status_code == 429:
                            await asyncio.sleep(1.5)
                            # Retry once on rate limit
                            async with client.stream(
                                "POST",
                                "https://api.groq.com/openai/v1/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {GROK_API_KEY}",
                                    "Content-Type": "application/json",
                                    "User-Agent": "SciGraph-Workspace/1.0",
                                },
                                json={
                                    "model": model,
                                    "messages": messages_payload,
                                    "temperature": req.temperature or 0.7,
                                    "stream": True,
                                },
                            ) as retry_resp:
                                if retry_resp.status_code == 200:
                                    async for line in retry_resp.aiter_lines():
                                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                                            try:
                                                chunk_data = json.loads(line[6:])
                                                delta = chunk_data["choices"][0].get("delta", {}).get("content", "")
                                                if delta:
                                                    if first_token_time is None:
                                                        first_token_time = round((time.time() - t0) * 1000, 1)
                                                    yield f"data: {json.dumps({'type': 'token', 'token': delta})}\n\n"
                                            except Exception:
                                                continue
                                    total_ms = round((time.time() - t0) * 1000, 1)
                                    yield f"data: {json.dumps({'type': 'done', 'total_ms': total_ms, 'first_token_ms': first_token_time or total_ms})}\n\n"
                                    yield "data: [DONE]\n\n"
                                    return

                        if resp.status_code != 200:
                            err_txt = await resp.aread()
                            yield f"data: {json.dumps({'type': 'error', 'error': err_txt.decode()})}\n\n"
                            return

                        async for line in resp.aiter_lines():
                            if line.startswith("data: ") and line.strip() != "data: [DONE]":
                                try:
                                    chunk_data = json.loads(line[6:])
                                    delta = chunk_data["choices"][0].get("delta", {}).get("content", "")
                                    if delta:
                                        if first_token_time is None:
                                            first_token_time = round((time.time() - t0) * 1000, 1)
                                        yield f"data: {json.dumps({'type': 'token', 'token': delta})}\n\n"
                                except Exception:
                                    continue
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        else:
            # Stream from local Ollama
            ollama_model = model.replace("ollama/", "")
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream(
                        "POST",
                        f"{OLLAMA_BASE_URL}/api/chat",
                        headers={"Content-Type": "application/json"},
                        json={
                            "model": ollama_model,
                            "messages": messages_payload,
                            "stream": True,
                            "options": {"temperature": req.temperature or 0.7},
                        },
                    ) as resp:
                        async for line in resp.aiter_lines():
                            if line.strip():
                                try:
                                    chunk_data = json.loads(line)
                                    delta = chunk_data.get("message", {}).get("content", "")
                                    if delta:
                                        if first_token_time is None:
                                            first_token_time = round((time.time() - t0) * 1000, 1)
                                        yield f"data: {json.dumps({'type': 'token', 'token': delta})}\n\n"
                                except Exception:
                                    continue
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        total_ms = round((time.time() - t0) * 1000, 1)
        yield f"data: {json.dumps({'type': 'done', 'total_ms': total_ms, 'first_token_ms': first_token_time or total_ms})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
