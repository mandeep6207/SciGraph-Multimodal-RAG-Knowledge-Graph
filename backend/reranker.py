import os
import logging
import asyncio
from pathlib import Path
import httpx

# NOTE: sentence_transformers / CrossEncoder is imported lazily inside load()
# to avoid network hangs at module import time when HF Hub is unreachable.

_logger = logging.getLogger(__name__)


class DocumentReranker:
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        base_url: str = "",
        api_key: str = "",
        timeout: int = 60,
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.api_key = api_key
        self.timeout = timeout
        self._reranker = None

    def _find_cached_snapshot_path(self, model_name: str) -> str | None:
        """Find local cached Hugging Face snapshot path if it exists to load instantly offline."""
        try:
            hub_folder_name = "models--" + model_name.replace("/", "--")
            snapshots_dir = (
                Path.home() / ".cache" / "huggingface" / "hub" / hub_folder_name / "snapshots"
            )
            if snapshots_dir.exists():
                for snapshot in snapshots_dir.iterdir():
                    if snapshot.is_dir() and (snapshot / "config.json").exists():
                        return str(snapshot)
        except Exception:
            pass
        return None

    def load(self):
        """Preloads the local model into memory if we are NOT using an external API."""
        if self.base_url:
            return None  # Skip loading on CPU if an external URL is provided

        if self._reranker is None:
            _logger.info(f"Loading local CPU reranker {self.model_name} ...")
            local_path = self._find_cached_snapshot_path(self.model_name)
            target = local_path if local_path else self.model_name
            if local_path:
                # Fast path: ensure huggingface offline flags so it loads instantly without network checks
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            try:
                # Lazy import: avoids network hang at module load time
                from sentence_transformers import CrossEncoder  # noqa: PLC0415
                self._reranker = CrossEncoder(target, device="cpu")
                _logger.info(f"Local CPU Reranker ready (loaded from {target}).")
            except Exception as e:
                _logger.warning(
                    "Could not load local reranker model '%s': %s. Reranking will pass-through.",
                    self.model_name,
                    e,
                )
                self._reranker = None
        return self._reranker

    async def rerank(self, query: str, documents: list[str], top_n: int = 20):
        """Routes to an external API if configured, otherwise runs local CPU inference."""
        if not documents:
            return []

        # External routing
        if self.base_url:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "model": self.model_name,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    _logger.info(
                        f"Sending rerank request to {self.base_url} for {len(documents)} docs"
                    )
                    resp = await client.post(
                        f"{self.base_url}/rerank", json=payload, headers=headers
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    if "results" in data:
                        results = data["results"]
                        _logger.info(
                            f"[rerank-external] top: "
                            f"{[round(r.get('relevance_score', 0), 3) for r in results[:5]]}"
                        )
                        return results
                    return [{"index": i, "relevance_score": 1.0} for i in range(min(len(documents), top_n))]
            except Exception as e:
                _logger.warning(f"External rerank failed ({e}). Returning original document order.")
                return [{"index": i, "relevance_score": 1.0} for i in range(min(len(documents), top_n))]

        # Local routing
        loop = asyncio.get_running_loop()
        reranker_instance = self.load()
        if reranker_instance is None:
            return [{"index": i, "relevance_score": 1.0} for i in range(min(len(documents), top_n))]

        # Truncate text pairs to 150 chars to avoid transformer quadratic latency
        doc_subset = documents[:top_n]
        pairs = [[query[:100], doc[:150]] for doc in doc_subset]

        try:
            scores = await loop.run_in_executor(
                None, lambda: reranker_instance.predict(pairs, show_progress_bar=False)
            )

            results = [
                {"index": i, "relevance_score": float(s)} for i, s in enumerate(scores)
            ]
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

            _logger.info(
                f"[rerank-local] {len(documents)} docs → top: "
                f"{[round(r['relevance_score'], 3) for r in results[:5]]}"
            )
            return results[:top_n]
        except Exception as e:
            _logger.warning(f"Local reranking computation error ({e}). Returning original order.")
            return [{"index": i, "relevance_score": 1.0} for i in range(min(len(documents), top_n))]
