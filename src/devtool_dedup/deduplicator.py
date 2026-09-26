"""Business decision for accepting or linking a developer event."""

from __future__ import annotations

from typing import Any

from .models import DeveloperEvent, DuplicateDecision


class EventDeduplicator:
    def __init__(self, backend: Any, threshold: float = 0.88) -> None:
        self.backend = backend
        self.threshold = threshold

    def inspect(self, event: DeveloperEvent) -> DuplicateDecision:
        text = event.semantic_text()
        embedding = self.backend.embed(text)
        hits = self.backend.search(embedding, top_k=8)
        candidates = [
            hit["metadata"]
            for hit in hits
            if isinstance(hit.get("metadata"), dict)
            and isinstance(hit["metadata"].get("text"), str)
        ]

        if candidates:
            ranked = self.backend.rerank(text, [item["text"] for item in candidates])
            if ranked:
                best = ranked[0]
                index = int(best["index"])
                score = float(best["relevance_score"])
                matched = candidates[index]
                if score >= self.threshold:
                    return DuplicateDecision(
                        event_id=event.event_id,
                        duplicate=True,
                        matched_event_id=str(matched["event_id"]),
                        semantic_score=score,
                        action="linked",
                    )

        self.backend.store(event, embedding)
        return DuplicateDecision(
            event_id=event.event_id,
            duplicate=False,
            matched_event_id=None,
            semantic_score=None,
            action="indexed",
        )
