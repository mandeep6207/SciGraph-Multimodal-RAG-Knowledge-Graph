import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root directory (dynamic resolution - avoids hardcoded drive letters)
BASE_DIR = Path(__file__).resolve().parent.parent

# Application Identity
APP_NAME = "SciGraph"
APP_FULL_TITLE = "SciGraph — Scientific Intelligence Workspace"
APP_TAGLINE = "Explore Research. Connect Knowledge. Discover What's Next."

# Engine selection
LLM_ENGINE = os.getenv("LLM_ENGINE", "ollama").lower()

# Base URLs
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LLAMA_CPP_BASE_URL = os.getenv("LLAMA_CPP_BASE_URL", "http://localhost:8080/v1")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
RERANKER_BASE_URL = os.getenv("RERANKER_BASE_URL", "")

# External API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-no-key-required")

# Model names
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")
VISION_MODEL = os.getenv("VISION_MODEL", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# Model settings
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP_SIZE", "150"))
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "8192"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))
LLM_MAX_ASYNC = int(os.getenv("LLM_MAX_ASYNC", "2"))
EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT", "120"))
EMBEDDING_MAX_ASYNC = int(os.getenv("EMBEDDING_MAX_ASYNC", "2"))
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
MAX_EMBED_TOKENS = int(os.getenv("MAX_EMBED_TOKENS", "2048"))
MAX_GLEANING = int(os.getenv("MAX_GLEANING", "0"))

# Retrieval & Query optimization
TOP_K = int(os.getenv("TOP_K", "15"))
CHUNK_TOP_K = int(os.getenv("CHUNK_TOP_K", "4"))
MAX_TOTAL_TOKENS = int(os.getenv("MAX_TOTAL_TOKENS", "4096"))
ENABLE_LOCAL_RERANKER = os.getenv("ENABLE_LOCAL_RERANKER", "false").lower() in ("true", "1")
RERANK_BY_DEFAULT = os.getenv("RERANK_BY_DEFAULT", "false").lower() in ("true", "1")

# Neo4j & Graph Storage
GRAPH_STORAGE = os.getenv("GRAPH_STORAGE", "Neo4JStorage")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Safe dynamic path resolution
def _resolve_dir(env_val: str, default_rel: str) -> str:
    if env_val and env_val.strip():
        p = Path(env_val.strip())
        if p.is_absolute():
            # If path points to obsolete folder or parent does not exist, fall back to current workspace
            if "The-Brain" in str(p) or not p.parent.exists():
                return str(BASE_DIR / default_rel)
            return str(p)
        return str(BASE_DIR / p)
    return str(BASE_DIR / default_rel)

WORKING_DIR = _resolve_dir(os.getenv("WORKING_DIR", ""), "data/rag_storage")
UPLOAD_DIR = _resolve_dir(os.getenv("UPLOAD_DIR", ""), "data/uploads")
OUTPUT_DIR = _resolve_dir(os.getenv("OUTPUT_DIR", ""), "data/output")
PARSER = os.getenv("PARSER", "mineru")

# Persistent files
HIDDEN_TYPES_FILE = Path(WORKING_DIR) / "hidden_types.json"
CONV_FILE = Path(WORKING_DIR) / "conversations.json"
COMPLETED_LOG = Path(WORKING_DIR) / "completed_docs.json"
PROFILE_FILE = Path(WORKING_DIR) / "profile.json"
WORKSPACES_FILE = Path(WORKING_DIR) / "workspaces.json"

# Document settings & Universal Format Support
ALLOWED_EXTENSIONS = {
    # PDF
    ".pdf",
    # Images
    ".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp",
    # Word
    ".docx", ".doc",
    # Excel & Tabular
    ".xlsx", ".xls", ".csv",
    # PowerPoint
    ".pptx", ".ppt",
    # LaTeX & Scientific References
    ".tex", ".bib",
    # Text & Documents
    ".txt", ".md", ".rtf",
    # Web Formats
    ".html", ".htm",
    # Structured Data
    ".json", ".xml",
}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_CONCURRENT_INGESTIONS = int(os.getenv("MAX_CONCURRENT_INGESTIONS", "3"))
