from __future__ import annotations

import json
import logging
import time
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger("app.llm.client")


class LLMClient:
    """Thin wrapper around the OpenAI SDK for chat, JSON-schema output, and embeddings."""

    def __init__(self) -> None:
        self.base_url = (settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = settings.openai_model
        self.api_key = settings.openai_api_key
        self.timeout = settings.llm_timeout_sec
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    @property
    def provider_name(self) -> str:
        return "openai-compatible"

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed_sec = time.perf_counter() - start
        logger.info("LLM chat ok model=%s latency_s=%.2f", self.model, elapsed_sec)
        return response.model_dump()

    def structured_chat(
        self,
        messages: list[dict[str, str]],
        *,
        schema_name: str,
        schema: dict[str, Any],
        description: str,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Request strict JSON-schema output and parse the resulting JSON content."""
        payload_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "description": description,
                "schema": schema,
            },
        }
        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            response_format=payload_schema,
        )
        elapsed_sec = time.perf_counter() - start
        logger.info(
            "LLM structured chat ok model=%s schema=%s latency_s=%.2f",
            self.model,
            schema_name,
            elapsed_sec,
        )

        choices = response.choices or []
        if not choices:
            raise ValueError(f"No choices returned for schema {schema_name}")
        content = choices[0].message.content or ""
        data = _safe_json(content)
        if not isinstance(data, dict):
            raise ValueError(f"Structured response for {schema_name} was not an object")
        return data

    def embedding(self, text: str, *, model: str = "text-embedding-3-small") -> list[float]:
        start = time.perf_counter()
        response = self._client.embeddings.create(
            model=model,
            input=text[:2000],
        )
        elapsed_sec = time.perf_counter() - start
        logger.info("LLM embedding ok model=%s latency_s=%.2f", model, elapsed_sec)
        return list(response.data[0].embedding)


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(text[start : end + 1])
