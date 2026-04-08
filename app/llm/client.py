from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from app.config import settings

logger = logging.getLogger("app.llm.client")


class LLMClient:
    """Thin wrapper around the OpenAI SDK for chat, JSON-schema output, and embeddings."""

    def __init__(self) -> None:
        self.base_url = (settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = settings.openai_model
        self.api_key = settings.openai_api_key
        self.timeout = settings.llm_timeout_sec

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
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            timeout=self.timeout,
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                **({"max_tokens": max_tokens} if max_tokens is not None else {}),
            },
        )
        response.raise_for_status()
        elapsed_sec = time.perf_counter() - start
        logger.info("LLM chat ok model=%s latency_s=%.2f", self.model, elapsed_sec)
        return response.json()

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
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            timeout=self.timeout,
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "response_format": payload_schema,
            },
        )
        response.raise_for_status()
        elapsed_sec = time.perf_counter() - start
        logger.info(
            "LLM structured chat ok model=%s schema=%s latency_s=%.2f",
            self.model,
            schema_name,
            elapsed_sec,
        )

        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError(f"No choices returned for schema {schema_name}")
        content = choices[0].get("message", {}).get("content", "") or ""
        data = _safe_json(content)
        if not isinstance(data, dict):
            raise ValueError(f"Structured response for {schema_name} was not an object")
        return data

    def embedding(self, text: str, *, model: str = "text-embedding-3-small") -> list[float]:
        start = time.perf_counter()
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers=self._headers(),
            timeout=self.timeout,
            json={
                "model": model,
                "input": text[:2000],
            },
        )
        response.raise_for_status()
        elapsed_sec = time.perf_counter() - start
        logger.info("LLM embedding ok model=%s latency_s=%.2f", model, elapsed_sec)
        payload = response.json()
        return list(payload["data"][0]["embedding"])

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(text[start : end + 1])
