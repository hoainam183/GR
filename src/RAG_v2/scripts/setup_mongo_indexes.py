"""Create MongoDB indexes for Week 4 agent traces.

Usage:
    python scripts/setup_mongo_indexes.py
    python scripts/setup_mongo_indexes.py --uri mongodb://localhost:27017 --db rag_chatbot
"""

from __future__ import annotations

import argparse
import os

from pymongo import DESCENDING, MongoClient


def setup_agent_trace_indexes(uri: str, db_name: str) -> list[str]:
    """Create indexes for ``agent_traces`` and return created index names."""
    client = MongoClient(uri)
    db = client[db_name]
    collection = db["agent_traces"]

    names = [
        collection.create_index([("session_id", 1)]),
        collection.create_index([("created_at", DESCENDING)]),
        collection.create_index([("tool_names_sequence", 1)]),
    ]
    client.close()
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup MongoDB indexes for agent traces")
    parser.add_argument(
        "--uri",
        default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        help="MongoDB URI",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("MONGODB_DATABASE", "rag_chatbot"),
        help="MongoDB database name",
    )
    args = parser.parse_args()

    index_names = setup_agent_trace_indexes(args.uri, args.db)
    print("Indexes created for agent_traces:")
    for name in index_names:
        print(f"- {name}")


if __name__ == "__main__":
    main()
