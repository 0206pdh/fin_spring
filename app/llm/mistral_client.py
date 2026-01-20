from __future__ import annotations

import json
import time
from typing import Any

import requests

from app.config import settings
import logging

logger = logging.getLogger("app.llm.client")


class MistralClient:
    def __init__(self) -> None:
        provider = (settings.llm_provider or "local").strip().lower()
        if provider == "openai":
            self.base_url = (settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
            self.model = settings.openai_model or settings.llm_model
            self.api_key = settings.openai_api_key
        else:
            self.base_url = settings.llm_base_url.rstrip("/")
            self.model = settings.llm_model
            self.api_key = ""
        self.timeout = settings.llm_timeout_sec

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        start = time.perf_counter()
        response = requests.post(url, json=payload, timeout=self.timeout, headers=headers)
        response.raise_for_status()
        elapsed_sec = time.perf_counter() - start
        logger.info(
            "LLM request ok provider=%s model=%s latency_s=%.2f",
            (settings.llm_provider or "local").strip().lower(),
            self.model,
            elapsed_sec,
        )
        return response.json()

    def extract_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        response = self.chat(messages)
        choices = response.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from LLM")
        content = choices[0].get("message", {}).get("content", "")
        return _safe_json(content)


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(text[start : end + 1])
