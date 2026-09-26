"""Semantic deduplication for developer-tool events."""

from .deduplicator import EventDeduplicator
from .models import DeveloperEvent, DuplicateDecision, EventKind

__all__ = ["DeveloperEvent", "DuplicateDecision", "EventDeduplicator", "EventKind"]
