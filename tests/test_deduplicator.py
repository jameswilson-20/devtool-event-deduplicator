from typing import Any

from devtool_dedup import DeveloperEvent, EventDeduplicator, EventKind


class RecordedBackend:
    def __init__(self) -> None:
        self.stored: list[str] = []

    def embed(self, text: str) -> list[float]:
        return [0.2, 0.8]

    def search(self, embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        return [
            {
                "metadata": {
                    "event_id": "release-previous-017",
                    "text": (
                        "event kind: release\nproject: medication-reminders\n"
                        "summary: Bundle signing stopped; CI alias was absent\n"
                        "details: Android packaging did not complete."
                    ),
                }
            }
        ]

    def rerank(self, query: str, candidates: list[str]) -> list[dict[str, Any]]:
        return [{"index": 0, "relevance_score": 0.94}]

    def store(self, event: DeveloperEvent, embedding: list[float]) -> None:
        self.stored.append(event.event_id)


def test_semantic_duplicate_links_existing_release_without_reindexing() -> None:
    backend = RecordedBackend()
    event = DeveloperEvent(
        event_id="release-new-042",
        kind=EventKind.RELEASE,
        project="medication-reminders",
        summary="Android release halted while signing the application bundle",
        details="The signing task could not locate the CI keystore alias.",
    )

    decision = EventDeduplicator(backend).inspect(event)

    assert decision.duplicate is True
    assert decision.matched_event_id == "release-previous-017"
    assert decision.action == "linked"
    assert backend.stored == []
