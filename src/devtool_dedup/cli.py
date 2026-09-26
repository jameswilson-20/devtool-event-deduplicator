"""Initialize the index or inspect one event from a JSON file."""

import argparse
import json
import os
from pathlib import Path

from .deduplicator import EventDeduplicator
from .infrai_gateway import InfraiGateway
from .models import DeveloperEvent


def main() -> None:
    parser = argparse.ArgumentParser(prog="devtool-dedup")
    parser.add_argument("command", choices=("init", "inspect"))
    parser.add_argument("event_file", nargs="?", type=Path)
    args = parser.parse_args()

    collection = os.environ.get("INFRAI_VECTOR_COLLECTION", "developer-events-v1")
    gateway = InfraiGateway(collection)
    if args.command == "init":
        dimension = len(gateway.embed("developer event index probe"))
        gateway.create_collection(dimension)
        print(json.dumps({"collection": collection, "status": "ready"}))
        return

    if args.event_file is None:
        parser.error("inspect requires event_file")
    event = DeveloperEvent.model_validate_json(args.event_file.read_text())
    decision = EventDeduplicator(gateway).inspect(event)
    print(decision.model_dump_json())


if __name__ == "__main__":
    main()
