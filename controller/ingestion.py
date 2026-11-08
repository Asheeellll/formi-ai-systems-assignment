
import json

from controller.database import (
    connect,
    initialize,
    save_events,
)
from controller.main import api_request


def ingest_chunk(chunk_id):
    """Download and persist one NDJSON chunk."""

    response = api_request(
        "GET",
        f"/events/chunks/{chunk_id}",
    )

    if not isinstance(response, str):
        raise TypeError(
            f"Expected NDJSON string, got {type(response).__name__}"
        )

    events = []

    for line_number, line in enumerate(
        response.splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in chunk {chunk_id}, "
                f"line {line_number}"
            ) from exc

        if not isinstance(event, dict):
            raise ValueError(
                f"Unexpected event in chunk {chunk_id}, "
                f"line {line_number}"
            )

        events.append(event)

    inserted = save_events(events)

    return {
        "chunk_id": chunk_id,
        "received": len(events),
        "inserted": inserted,
    }


def get_processed_chunks():
    """Read persistent chunk checkpoints from SQLite."""

    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_chunks (
                chunk_id INTEGER PRIMARY KEY,
                processed_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                event_count INTEGER NOT NULL
            )
        """)

        rows = conn.execute(
            "SELECT chunk_id FROM processed_chunks"
        ).fetchall()

    return {row[0] for row in rows}


def mark_chunk_processed(chunk_id, event_count):
    """Persist a checkpoint after successful ingestion."""

    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO processed_chunks
                (chunk_id, event_count)
            VALUES (?, ?)
            """,
            (chunk_id, event_count),
        )


def sync_chunks():
    """Discover and ingest all unprocessed event chunks."""

    initialize()

    processed = get_processed_chunks()

    available = []

    for kind in ("history", "events"):
        chunks = api_request(
            "GET",
            f"/events/chunks?kind={kind}",
        )

        if not isinstance(chunks, list):
            raise TypeError(
                f"Expected chunk list for {kind}"
            )

        available.extend(chunks)

    available.sort(key=lambda chunk: chunk["chunk"])

    total_inserted = 0
    total_processed = 0

    for chunk in available:
        chunk_id = chunk["chunk"]

        if chunk_id in processed:
            continue

        result = ingest_chunk(chunk_id)

        if result["received"] != chunk["events"]:
            raise RuntimeError(
                f"Chunk {chunk_id} incomplete: "
                f"expected {chunk['events']} events, "
                f"received {result['received']}"
            )

        mark_chunk_processed(
            chunk_id,
            result["received"],
        )

        total_inserted += result["inserted"]
        total_processed += 1

        print(
            f"Chunk {chunk_id}: "
            f"{result['inserted']} new events",
            flush=True,
        )

    return {
        "chunks_processed": total_processed,
        "events_inserted": total_inserted,
    }


def main():
    result = sync_chunks()

    print("\nINGESTION SUMMARY")
    print("Chunks processed:", result["chunks_processed"])
    print("New events inserted:", result["events_inserted"])


if __name__ == "__main__":
    main()
