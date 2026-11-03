from typing import Optional
import httpx
import numpy as np
from lightrag.llm.openai import openai_complete_if_cache


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        llm_model: str,
        vision_model: str,
        embed_model: str,
        num_ctx: int,
        timeout: int,
    ):
        self.base_url = base_url.rstrip("/")
        self.llm_model = llm_model
        self.vision_model = vision_model
        self.embed_model = embed_model
        self.num_ctx = num_ctx
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=40, keepalive_expiry=30.0)
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                limits=limits,
            )
        return self._client

    async def close(self):
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # LLM model
    async def llm(
        self, prompt: str, system_prompt=None, history_messages=None, **kwargs
    ):
        history_messages = history_messages or []
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        client = self._get_client()
        num_predict = kwargs.get("max_tokens") or kwargs.get("num_predict") or 1536
        options = {
            "num_ctx": self.num_ctx,
            "num_predict": num_predict,
        }
        if "temperature" in kwargs:
            options["temperature"] = kwargs["temperature"]

        payload = {
            "model": self.llm_model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if "stop" in kwargs and kwargs["stop"]:
            payload["stop"] = kwargs["stop"] if isinstance(kwargs["stop"], list) else [kwargs["stop"]]

        resp = await client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    # Vision model
    async def vision(
        self,
        prompt: str,
        system_prompt=None,
        history_messages=None,
        image_data=None,
        messages=None,
        **kwargs,
    ):
        if not self.vision_model:
            if not prompt and messages:
                # Extract text content from messages if prompt is empty
                for m in reversed(messages):
                    c = m.get("content", "")
                    if isinstance(c, str) and c:
                        prompt = c
                        break
                    elif isinstance(c, list):
                        for part in c:
                            if isinstance(part, dict) and part.get("type") == "text":
                                prompt = part.get("text", "")
                                break
            return await self.llm(prompt or "", system_prompt, history_messages, **kwargs)

        client = self._get_client()

        # Handle native Multimodal Query format
        if messages:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.vision_model,
                    "messages": messages,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        # Handle standard image processing
        if image_data:
            built = []
            if system_prompt:
                built.append({"role": "system", "content": system_prompt})
            built.append({"role": "user", "content": prompt, "images": [image_data]})
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.vision_model,
                    "messages": built,
                    "stream": False,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

        return await self.llm(prompt, system_prompt, history_messages, **kwargs)

    # Embedding model
    async def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0))
        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.embed_model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        if "embeddings" in data:
            return np.array(data["embeddings"])
        elif "embedding" in data:
            return np.array([data["embedding"]])
        return np.array([])


class OpenAIProvider:
    """Supports standard OpenAI, as well as vLLM, llama.cpp, Groq, etc. via custom base_url"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        llm_model: str,
        vision_model: str,
        embed_model: str,
        timeout: int,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.llm_model = llm_model
        self.vision_model = vision_model
        self.embed_model = embed_model
        self.timeout = timeout

    # LLM model
    async def llm(
        self, prompt: str, system_prompt=None, history_messages=None, **kwargs
    ):
        timeout = kwargs.pop("timeout", self.timeout)
        return await openai_complete_if_cache(
            self.llm_model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            **kwargs,
        )

    # Vision model
    async def vision(
        self,
        prompt: str,
        system_prompt=None,
        history_messages=None,
        image_data=None,
        messages=None,
        **kwargs,
    ):
        if not self.vision_model:
            if not prompt and messages:
                for m in reversed(messages):
                    c = m.get("content", "")
                    if isinstance(c, str) and c:
                        prompt = c
                        break
                    elif isinstance(c, list):
                        for part in c:
                            if isinstance(part, dict) and part.get("type") == "text":
                                prompt = part.get("text", "")
                                break
            return await self.llm(prompt or "", system_prompt, history_messages, **kwargs)

        timeout = kwargs.pop("timeout", self.timeout)

        # Handle native Multimodal Query format
        if messages:
            return await openai_complete_if_cache(
                self.vision_model,
                "",
                system_prompt=None,
                history_messages=[],
                messages=messages,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=timeout,
                **kwargs,
            )

        # Handle standard image processing
        if image_data:
            built = []
            if system_prompt:
                built.append({"role": "system", "content": system_prompt})
            built.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                }
            )
            return await openai_complete_if_cache(
                self.vision_model,
                "",
                system_prompt=None,
                history_messages=[],
                messages=built,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=timeout,
                **kwargs,
            )

        return await self.llm(prompt, system_prompt, history_messages, **kwargs)

    # Embedding model
    async def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0))
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/embeddings" if self.base_url.endswith("/v1") else f"{self.base_url}/v1/embeddings"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={"model": self.embed_model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return np.array([item["embedding"] for item in data])
