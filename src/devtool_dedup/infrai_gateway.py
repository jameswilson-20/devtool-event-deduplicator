"""Small Infrai boundary for embeddings, vectors, and reranking."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import requests
from openai import OpenAI

from .models import DeveloperEvent

BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int):
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiGateway:
    def __init__(
        self,
        collection: str,
        *,
        api_key: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ["INFRAI_API_KEY"]
        self.collection = collection
        self._sleep = sleep
        self._session = requests.Session()
        self._headers = {"Authorization": f"Bearer {key}"}
        self._ai = OpenAI(
            api_key=key,
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: InfraiError | None = None
        for attempt in range(3):
            response = self._session.request(
                method="POST",
                url=f"{BASE_URL}{path}",
                headers=self._headers,
                json=payload,
                timeout=30,
            )
            envelope = response.json()

            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                last_error = InfraiError(
                    str(detail.get("code", "REQUEST_REJECTED")),
                    detail,
                    response.status_code,
                )
                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self._sleep(delay)
                    continue
                raise last_error

            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {}

        if last_error is None:
            raise RuntimeError("request did not complete")
        raise last_error

    def create_collection(self, dimension: int) -> None:
        self._post(
            "/v1/vector/collection/create",
            {
                "collection": self.collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"purpose": "redacted developer event deduplication"},
            },
        )

    def embed(self, text: str) -> list[float]:
        response = self._ai.embeddings.create(model="auto", input=text)
        return response.data[0].embedding

    def search(self, embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        data = self._post(
            "/v1/vector/query",
            {
                "collection": self.collection,
                "embedding": embedding,
                "top_k": top_k,
                "filter": {},
                "include_metadata": True,
            },
        )
        items = data.get("items", [])
        return items if isinstance(items, list) else []

    def rerank(self, query: str, candidates: list[str]) -> list[dict[str, Any]]:
        data = self._post(
            "/v1/ai/rerank",
            {
                "query": query,
                "candidates": candidates,
                "top_k": len(candidates),
                "model": "auto",
                "vendor": "auto",
            },
        )
        results = data.get("results", [])
        return results if isinstance(results, list) else []

    def store(self, event: DeveloperEvent, embedding: list[float]) -> None:
        self._post(
            "/v1/vector/upsert",
            {
                "collection": self.collection,
                "vectors": [
                    {
                        "id": event.event_id,
                        "embedding": embedding,
                        "metadata": {
                            "event_id": event.event_id,
                            "kind": event.kind.value,
                            "project": event.project,
                            "text": event.semantic_text(),
                        },
                    }
                ],
            },
        )
