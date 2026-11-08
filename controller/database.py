
import json
import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = PROJECT_ROOT / "controller_state.db"


def get_db_path():
    """
    Resolve the controller database location.

    CONTROLLER_DB may be an absolute path or a path
    relative to the project root.

    Default retains compatibility with existing runs.
    """
    configured = os.environ.get("CONTROLLER_DB")

    if configured:
        path = Path(configured).expanduser()

        if not path.is_absolute():
            path = PROJECT_ROOT / path
    else:
        path = DEFAULT_DB_PATH

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path.resolve()


def connect():
    """Open a SQLite connection with WAL enabled."""
    conn = sqlite3.connect(
        get_db_path(),
        timeout=30,
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    return conn


def initialize():
    """Create the core persistent controller tables."""
    with connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY,
                event_type TEXT NOT NULL,
                workflow_id TEXT,
                event_ts TEXT,
                payload TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_events_workflow
            ON events(workflow_id, event_type);

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL,
                workflow_id TEXT,
                details TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS controller_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)


def save_events(events):
    """Insert events idempotently using simulator event IDs."""
    inserted = 0

    with connect() as conn:
        for event in events:
            event_id = event.get("event_id")

            if event_id is None:
                continue

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO events (
                    event_id,
                    event_type,
                    workflow_id,
                    event_ts,
                    payload
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event.get("type", "unknown"),
                    event.get("workflow_id"),
                    event.get("ts"),
                    json.dumps(event),
                ),
            )

            inserted += cursor.rowcount

    return inserted


def log_action(action, workflow_id=None, details=None):
    """Append a durable audit event."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (
                action,
                workflow_id,
                details
            )
            VALUES (?, ?, ?)
            """,
            (
                action,
                workflow_id,
                json.dumps(details or {}),
            ),
        )


def event_count():
    """Return the number of locally persisted events."""
    with connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]
