
from controller.database import connect


BATCH_SIZE = 250_000


def initialize_analytics():
    """Create persistent KPI summaries and aggregation progress."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_kpi_summary (
                workflow_id TEXT NOT NULL,
                event_day TEXT NOT NULL,
                dials INTEGER NOT NULL DEFAULT 0,
                connected INTEGER NOT NULL DEFAULT 0,
                engaged INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (workflow_id, event_day)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_checkpoint (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_event_id INTEGER NOT NULL DEFAULT 0
            )
        """)

        conn.execute("""
            INSERT OR IGNORE INTO analytics_checkpoint (
                id,
                last_event_id
            )
            VALUES (1, 0)
        """)

        conn.commit()


def refresh_daily_summaries(batch_size=BATCH_SIZE):
    """
    Aggregate newly ingested events exactly once.

    Each batch updates both KPI summaries and the event
    checkpoint within one SQLite transaction.
    """
    initialize_analytics()

    batches = 0
    total_events_scanned = 0

    while True:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            checkpoint = conn.execute("""
                SELECT last_event_id
                FROM analytics_checkpoint
                WHERE id = 1
            """).fetchone()[0]

            upper_row = conn.execute("""
                SELECT MAX(event_id)
                FROM (
                    SELECT event_id
                    FROM events
                    WHERE event_id > ?
                    ORDER BY event_id
                    LIMIT ?
                )
            """, (checkpoint, batch_size)).fetchone()

            upper_id = upper_row[0]

            if upper_id is None:
                conn.commit()
                break

            scanned = conn.execute("""
                SELECT COUNT(*)
                FROM events
                WHERE event_id > ?
                  AND event_id <= ?
            """, (checkpoint, upper_id)).fetchone()[0]

            conn.execute("""
                INSERT INTO daily_kpi_summary (
                    workflow_id,
                    event_day,
                    dials,
                    connected,
                    engaged
                )
                SELECT
                    workflow_id,
                    SUBSTR(event_ts, 1, 10),
                    COUNT(*),
                    SUM(
                        CASE
                            WHEN json_extract(
                                payload,
                                '$.connected'
                            ) = 1
                            THEN 1 ELSE 0
                        END
                    ),
                    SUM(
                        CASE
                            WHEN json_extract(
                                payload,
                                '$.engaged'
                            ) = 1
                            THEN 1 ELSE 0
                        END
                    )
                FROM events
                WHERE event_id > ?
                  AND event_id <= ?
                  AND event_type = 'call'
                  AND workflow_id IS NOT NULL
                  AND event_ts IS NOT NULL
                GROUP BY
                    workflow_id,
                    SUBSTR(event_ts, 1, 10)
                ON CONFLICT(workflow_id, event_day)
                DO UPDATE SET
                    dials = dials + excluded.dials,
                    connected = connected + excluded.connected,
                    engaged = engaged + excluded.engaged
            """, (checkpoint, upper_id))

            conn.execute("""
                UPDATE analytics_checkpoint
                SET last_event_id = ?
                WHERE id = 1
            """, (upper_id,))

            conn.commit()

        batches += 1
        total_events_scanned += scanned

        if batches % 5 == 0:
            print(
                f"[ANALYTICS] Batches: {batches} | "
                f"Events scanned: {total_events_scanned:,}",
                flush=True,
            )

    return {
        "batches": batches,
        "events_scanned": total_events_scanned,
    }


def workflow_metrics():
    """Calculate workflow KPIs from persistent daily summaries."""
    refresh_daily_summaries()

    with connect() as conn:
        rows = conn.execute("""
            SELECT
                workflow_id,
                SUM(dials),
                SUM(connected),
                SUM(engaged)
            FROM daily_kpi_summary
            GROUP BY workflow_id
            ORDER BY workflow_id
        """).fetchall()

    results = []

    for workflow_id, dials, connected, engaged in rows:
        dials = dials or 0
        connected = connected or 0
        engaged = engaged or 0

        results.append({
            "workflow_id": workflow_id,
            "dials": dials,
            "connected": connected,
            "engaged": engaged,
            "pickup_rate": connected / dials if dials else 0.0,
            "engagement_rate": (
                engaged / connected if connected else 0.0
            ),
        })

    return results


def daily_metrics():
    """Read daily KPIs without rescanning historical call JSON."""
    refresh_daily_summaries()

    with connect() as conn:
        rows = conn.execute("""
            SELECT
                workflow_id,
                event_day,
                dials,
                connected,
                engaged
            FROM daily_kpi_summary
            ORDER BY workflow_id, event_day
        """).fetchall()

    results = []

    for workflow_id, day, dials, connected, engaged in rows:
        dials = dials or 0
        connected = connected or 0
        engaged = engaged or 0

        results.append({
            "workflow_id": workflow_id,
            "day": day,
            "dials": dials,
            "connected": connected,
            "engaged": engaged,
            "pickup_rate": connected / dials if dials else 0.0,
            "engagement_rate": (
                engaged / connected if connected else 0.0
            ),
        })

    return results


def main():
    print("Updating persistent analytics summaries...")

    print("\nWORKFLOW PERFORMANCE")
    print("-" * 72)

    for item in workflow_metrics():
        print(
            f"{item['workflow_id']:15} "
            f"Dials: {item['dials']:7}  "
            f"Pickup: {item['pickup_rate']:.2%}  "
            f"Engagement: {item['engagement_rate']:.2%}"
        )

    print("\nDAILY PERFORMANCE - LAST 9 RECORDS")
    print("-" * 85)

    for item in daily_metrics()[-9:]:
        print(
            f"{item['day']}  "
            f"{item['workflow_id']:15} "
            f"Dials: {item['dials']:6}  "
            f"Pickup: {item['pickup_rate']:.2%}  "
            f"Engagement: {item['engagement_rate']:.2%}"
        )


if __name__ == "__main__":
    main()
