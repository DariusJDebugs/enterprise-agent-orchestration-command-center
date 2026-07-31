from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, *, system: str, user: str, temperature: float = 0.1) -> str:
        raise NotImplementedError


class DeterministicProvider(LLMProvider):
    """Offline provider used by default so the complete MVP is reproducible."""

    async def complete(self, *, system: str, user: str, temperature: float = 0.1) -> str:
        del temperature
        return (
            "Deterministic synthesis mode. The agent used structured rules, retrieved evidence, "
            "and connector outputs. System role: " + system[:140] + " | Task: " + user[:240]
        )


class OpenAICompatibleProvider(LLMProvider):
    """Optional provider for any allowlisted OpenAI-compatible chat-completions API."""

    def __init__(self, base_url: str, api_key: str, model: str):
        if not all((base_url, api_key, model)):
            raise ValueError("base_url, api_key, and model are required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, *, system: str, user: str, temperature: float = 0.1) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response: {json.dumps(data)[:500]}") from exc
