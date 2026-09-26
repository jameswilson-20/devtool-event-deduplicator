"""HTTP request boundary for the event decision."""

import os

from fastapi import FastAPI, HTTPException

from .deduplicator import EventDeduplicator
from .infrai_gateway import InfraiError, InfraiGateway
from .models import DeveloperEvent, DuplicateDecision

app = FastAPI(title="Developer event deduplicator", version="0.1.0")


def build_deduplicator() -> EventDeduplicator:
    collection = os.environ.get("INFRAI_VECTOR_COLLECTION", "developer-events-v1")
    return EventDeduplicator(InfraiGateway(collection))


@app.post("/events/inspect", response_model=DuplicateDecision)
def inspect_event(event: DeveloperEvent) -> DuplicateDecision:
    try:
        return build_deduplicator().inspect(event)
    except InfraiError as error:
        caller_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": error.code, "error": error.detail},
        ) from error
