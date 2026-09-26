"""Typed inputs and outputs for developer-tool event deduplication."""

from enum import Enum
import json
from typing import Literal

try:
    from pydantic import BaseModel, ConfigDict, Field
except ModuleNotFoundError:
    from dataclasses import asdict, dataclass


class EventKind(str, Enum):
    BUILD = "build"
    RELEASE = "release"
    DIAGNOSTIC = "diagnostic"


def _semantic_text(event: "DeveloperEvent") -> str:
    return "\n".join(
        (
            f"event kind: {event.kind.value}",
            f"project: {event.project}",
            f"summary: {event.summary}",
            f"details: {event.details}",
        )
    )


if "BaseModel" in globals():
    class DeveloperEvent(BaseModel):
        model_config = ConfigDict(extra="forbid")

        event_id: str = Field(min_length=1, max_length=120)
        kind: EventKind
        project: str = Field(min_length=1, max_length=120)
        summary: str = Field(min_length=3, max_length=500)
        details: str = Field(default="", max_length=1500)
        contains_sensitive_data: Literal[False] = False

        def semantic_text(self) -> str:
            return _semantic_text(self)


    class DuplicateDecision(BaseModel):
        event_id: str
        duplicate: bool
        matched_event_id: str | None
        semantic_score: float | None
        action: Literal["linked", "indexed"]
else:
    @dataclass
    class DeveloperEvent:
        event_id: str
        kind: EventKind
        project: str
        summary: str
        details: str = ""
        contains_sensitive_data: Literal[False] = False

        def __post_init__(self) -> None:
            self.kind = EventKind(self.kind)
            _check_length("event_id", self.event_id, 1, 120)
            _check_length("project", self.project, 1, 120)
            _check_length("summary", self.summary, 3, 500)
            _check_length("details", self.details, 0, 1500)
            if self.contains_sensitive_data is not False:
                raise ValueError("contains_sensitive_data must be false")

        def semantic_text(self) -> str:
            return _semantic_text(self)

        @classmethod
        def model_validate_json(cls, value: str) -> "DeveloperEvent":
            return cls(**json.loads(value))


    @dataclass
    class DuplicateDecision:
        event_id: str
        duplicate: bool
        matched_event_id: str | None
        semantic_score: float | None
        action: Literal["linked", "indexed"]

        def model_dump_json(self) -> str:
            return json.dumps(asdict(self))


    def _check_length(name: str, value: str, minimum: int, maximum: int) -> None:
        if not isinstance(value, str) or not minimum <= len(value) <= maximum:
            raise ValueError(
                f"{name} must contain between {minimum} and {maximum} characters"
            )
