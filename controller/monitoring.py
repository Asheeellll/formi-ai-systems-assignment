
import json

from controller.database import connect


def initialize_monitoring():
    """Create durable monitoring records."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS change_monitoring (
                proposal_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                previous_config TEXT NOT NULL,
                applied_config TEXT NOT NULL,
                applied_version INTEGER NOT NULL,
                applied_event_id INTEGER NOT NULL,
                primary_metric TEXT NOT NULL,
                baseline_rate REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'monitoring',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def get_latest_event_id():
    """Return the highest locally ingested event ID."""
    with connect() as conn:
        row = conn.execute("""
            SELECT COALESCE(MAX(event_id), 0)
            FROM events
        """).fetchone()

    return row[0]


def calculate_metric(
    workflow_id,
    metric,
    after_event_id=0,
    config_version=None,
):
    """
    Calculate workflow KPIs from locally ingested call events.

    Optionally restrict observations to a configuration version.
    """
    if metric not in (
        "pickup_rate",
        "engagement_rate",
    ):
        raise ValueError(
            f"Unsupported metric: {metric}"
        )

    query = """
        SELECT
            COUNT(*) AS dials,
            COALESCE(SUM(
                CASE
                    WHEN json_extract(
                        payload, '$.connected'
                    ) = 1
                    THEN 1 ELSE 0
                END
            ), 0) AS connected,
            COALESCE(SUM(
                CASE
                    WHEN json_extract(
                        payload, '$.engaged'
                    ) = 1
                    THEN 1 ELSE 0
                END
            ), 0) AS engaged
        FROM events
        WHERE event_type = 'call'
          AND workflow_id = ?
          AND event_id > ?
    """

    params = [
        workflow_id,
        after_event_id,
    ]

    if config_version is not None:
        query += """
            AND CAST(
                json_extract(
                    payload, '$.config_version'
                ) AS INTEGER
            ) = ?
        """
        params.append(config_version)

    with connect() as conn:
        row = conn.execute(
            query,
            params,
        ).fetchone()

    dials = row[0] or 0
    connected = row[1] or 0
    engaged = row[2] or 0

    if metric == "pickup_rate":
        denominator = dials
        numerator = connected
    else:
        denominator = connected
        numerator = engaged

    rate = (
        numerator / denominator
        if denominator > 0
        else None
    )

    return {
        "metric": metric,
        "rate": rate,
        "dials": dials,
        "connected": connected,
        "engaged": engaged,
        "sample_size": denominator,
    }


def register_change(
    proposal_id,
    workflow_id,
    previous_config,
    applied_config,
    applied_version,
    primary_metric,
):
    """
    Register an applied configuration for outcome monitoring.

    Uses the latest ingested event ID as a watermark.
    """
    initialize_monitoring()

    baseline = calculate_metric(
        workflow_id,
        primary_metric,
    )

    if baseline["rate"] is None:
        raise ValueError(
            "Cannot register change without baseline observations"
        )

    event_id = get_latest_event_id()

    with connect() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO change_monitoring (
                proposal_id,
                workflow_id,
                previous_config,
                applied_config,
                applied_version,
                applied_event_id,
                primary_metric,
                baseline_rate,
                status
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, 'monitoring'
            )
        """, (
            proposal_id,
            workflow_id,
            json.dumps(previous_config),
            json.dumps(applied_config),
            applied_version,
            event_id,
            primary_metric,
            baseline["rate"],
        ))
        conn.commit()

    return {
        "proposal_id": proposal_id,
        "workflow_id": workflow_id,
        "baseline_rate": baseline["rate"],
        "applied_event_id": event_id,
        "applied_version": applied_version,
    }


def evaluate_changes(
    min_samples=300,
    max_drop_pp=2.0,
):
    """
    Evaluate applied changes using events produced
    under their applied configuration version.

    This is a monitoring signal, not proof of causation.
    """
    initialize_monitoring()

    with connect() as conn:
        rows = conn.execute("""
            SELECT
                proposal_id,
                workflow_id,
                applied_event_id,
                applied_version,
                primary_metric,
                baseline_rate
            FROM change_monitoring
            WHERE status = 'monitoring'
        """).fetchall()

    results = []

    for (
        proposal_id,
        workflow_id,
        event_id,
        applied_version,
        metric,
        baseline_rate,
    ) in rows:

        current = calculate_metric(
            workflow_id,
            metric,
            after_event_id=event_id,
            config_version=applied_version,
        )

        sample_size = current["sample_size"]
        current_rate = current["rate"]

        if (
            current_rate is None
            or sample_size < min_samples
        ):
            decision = "insufficient_data"
            drop_pp = None

        else:
            drop_pp = (
                baseline_rate - current_rate
            ) * 100

            decision = (
                "rollback_recommended"
                if drop_pp > max_drop_pp
                else "continue"
            )

        results.append({
            "proposal_id": proposal_id,
            "workflow_id": workflow_id,
            "metric": metric,
            "baseline_rate": baseline_rate,
            "current_rate": current_rate,
            "applied_version": applied_version,
            "sample_size": sample_size,
            "drop_pp": drop_pp,
            "decision": decision,
        })

    return results


def recover_applied_changes():
    """
    Find applied proposals without monitoring records.

    Never invent a previous configuration.
    """
    initialize_monitoring()

    with connect() as conn:
        rows = conn.execute("""
            SELECT
                p.proposal_id,
                p.workflow_id,
                p.base_version,
                p.proposed_config
            FROM proposals AS p
            LEFT JOIN change_monitoring AS m
                ON m.proposal_id = p.proposal_id
            WHERE p.status = 'applied'
              AND m.proposal_id IS NULL
        """).fetchall()

    return [
        {
            "proposal_id": row[0],
            "workflow_id": row[1],
            "base_version": row[2],
            "proposed_config": json.loads(row[3]),
            "status": "monitoring_registration_missing",
        }
        for row in rows
    ]


def main():
    initialize_monitoring()

    print(
        "Monitoring database initialized."
    )

    print("\nMonitoring results:")
    print(
        json.dumps(
            evaluate_changes(),
            indent=2,
        )
    )

    print("\nUnregistered applied changes:")
    print(
        json.dumps(
            recover_applied_changes(),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
