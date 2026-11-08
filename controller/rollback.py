
import json

from controller.main import api_request
from controller.database import connect, log_action
from controller.governance import (
    create_proposal_record,
    submit_for_approval,
)
from controller.monitoring import evaluate_changes


def initialize_rollback():
    """Create durable rollback tracking records."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rollback_requests (
                original_proposal_id TEXT PRIMARY KEY,
                rollback_proposal_id TEXT NOT NULL UNIQUE,
                workflow_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def get_monitoring_record(proposal_id):
    """Read the configuration snapshot stored during application."""
    with connect() as conn:
        row = conn.execute("""
            SELECT
                workflow_id,
                previous_config,
                applied_config,
                applied_version,
                status
            FROM change_monitoring
            WHERE proposal_id = ?
        """, (proposal_id,)).fetchone()

    if row is None:
        return None

    return {
        "workflow_id": row[0],
        "previous_config": json.loads(row[1]),
        "applied_config": json.loads(row[2]),
        "applied_version": row[3],
        "status": row[4],
    }


def rollback_already_requested(original_proposal_id):
    """Find a previously submitted or prepared rollback."""
    with connect() as conn:
        row = conn.execute("""
            SELECT rollback_proposal_id
            FROM rollback_requests
            WHERE original_proposal_id = ?
        """, (original_proposal_id,)).fetchone()

    return row[0] if row else None


def is_rollback_proposal(proposal_id):
    """
    Determine whether a proposal is itself a rollback.

    This is the critical guard against rollback loops.
    """
    with connect() as conn:
        row = conn.execute("""
            SELECT 1
            FROM rollback_requests
            WHERE rollback_proposal_id = ?
            LIMIT 1
        """, (proposal_id,)).fetchone()

    return row is not None


def request_rollback(result):
    """
    Request a governed rollback of a deteriorating change.

    Never directly modify the simulator configuration.
    Never automatically roll back another rollback.
    """
    initialize_rollback()

    original_id = result["proposal_id"]
    workflow_id = result["workflow_id"]

    # SAFETY 1: A rollback cannot trigger another rollback.
    if is_rollback_proposal(original_id):
        log_action(
            "rollback_loop_prevented",
            workflow_id=workflow_id,
            details={
                "proposal_id": original_id,
                "reason": "proposal_is_already_a_rollback",
            },
        )

        return {
            "status": "rollback_loop_prevented",
            "workflow_id": workflow_id,
            "proposal_id": original_id,
        }

    # SAFETY 2: Never create duplicate rollback requests.
    existing = rollback_already_requested(original_id)

    if existing:
        return {
            "status": "already_requested",
            "workflow_id": workflow_id,
            "original_proposal_id": original_id,
            "rollback_proposal_id": existing,
        }

    record = get_monitoring_record(original_id)

    if record is None:
        return {
            "status": "monitoring_record_missing",
            "workflow_id": workflow_id,
            "proposal_id": original_id,
        }

    if record["workflow_id"] != workflow_id:
        raise RuntimeError(
            "Monitoring workflow does not match rollback request"
        )

    # SAFETY 3: Only act on an actively monitored change.
    if record["status"] != "monitoring":
        return {
            "status": "monitoring_not_active",
            "workflow_id": workflow_id,
            "monitoring_status": record["status"],
        }

    # SAFETY 4: Require sufficient monitoring evidence.
    drop_pp = result.get("drop_pp")
    sample_size = result.get("sample_size", 0)

    if (
        drop_pp is None
        or drop_pp <= 2.0
        or sample_size < 300
    ):
        return {
            "status": "insufficient_rollback_evidence",
            "workflow_id": workflow_id,
            "drop_pp": drop_pp,
            "sample_size": sample_size,
        }

    current = api_request(
        "GET",
        f"/workflows/{workflow_id}/config",
    )

    # SAFETY 5: Never revert a configuration that is no longer active.
    if (
        current["version"] != record["applied_version"]
        or current["config"] != record["applied_config"]
    ):
        log_action(
            "rollback_skipped_superseded",
            workflow_id=workflow_id,
            details={
                "proposal_id": original_id,
                "monitored_version": record["applied_version"],
                "current_version": current["version"],
            },
        )

        return {
            "status": "configuration_superseded",
            "workflow_id": workflow_id,
            "proposal_id": original_id,
        }

    previous_config = record["previous_config"]

    if previous_config == current["config"]:
        return {
            "status": "already_at_previous_config",
            "workflow_id": workflow_id,
        }

    rationale = (
        f"Safety rollback for proposal {original_id}. "
        f"Observed {result['metric']} deterioration of "
        f"{drop_pp:.2f} percentage points "
        f"across {sample_size} observations after "
        f"configuration version {record['applied_version']}. "
        "This is an observational safety signal rather than "
        "proof of causation. Restore the previously recorded "
        "configuration through the required approval process."
    )

    rollback_id = create_proposal_record(
        workflow_id=workflow_id,
        base_version=current["version"],
        proposed_config=previous_config,
        rationale=rationale,
    )

    # Persist the relationship BEFORE submitting to the simulator.
    # A restart can then detect that a rollback already exists.
    with connect() as conn:
        conn.execute("""
            INSERT INTO rollback_requests (
                original_proposal_id,
                rollback_proposal_id,
                workflow_id
            )
            VALUES (?, ?, ?)
        """, (
            original_id,
            rollback_id,
            workflow_id,
        ))
        conn.commit()

    log_action(
        "rollback_proposal_created",
        workflow_id=workflow_id,
        details={
            "original_proposal_id": original_id,
            "rollback_proposal_id": rollback_id,
            "source_version": current["version"],
        },
    )

    try:
        response = submit_for_approval(
            proposal_id=rollback_id,
            workflow_id=workflow_id,
            base_version=current["version"],
            proposed_config=previous_config,
            rationale=rationale,
            change_summary=(
                f"Restore configuration preceding {original_id}"
            ),
            diff={
                "type": "rollback",
                "original_proposal_id": original_id,
                "from_version": current["version"],
                "restore_previous_config": True,
            },
            dry_run={
                "method": "version_and_config_preflight",
                "current_version_verified": True,
                "current_config_verified": True,
                "rollback_target_recorded_before_apply": True,
                "observed_drop_pp": drop_pp,
                "sample_size": sample_size,
                "limitations": (
                    "Observational KPI comparison; "
                    "causation is not established."
                ),
            },
            affected_leads=0,
            impact_score=min(
                1.0,
                max(0.0, drop_pp / 10.0),
            ),
        )

    except Exception as exc:
        # Preserve the proposal and its rollback relationship.
        # Blind retries could create duplicate approvals.
        log_action(
            "rollback_submission_uncertain",
            workflow_id=workflow_id,
            details={
                "original_proposal_id": original_id,
                "rollback_proposal_id": rollback_id,
                "error": str(exc),
            },
        )
        raise

    with connect() as conn:
        conn.execute("""
            UPDATE change_monitoring
            SET status = 'rollback_requested'
            WHERE proposal_id = ?
        """, (original_id,))
        conn.commit()

    return {
        "status": "rollback_submitted",
        "workflow_id": workflow_id,
        "original_proposal_id": original_id,
        "rollback_proposal_id": rollback_id,
        "approval_id": response.get("approval_id"),
    }


def process_rollbacks():
    """
    Evaluate monitored changes and submit permitted
    rollback proposals when deterioration is detected.
    """
    initialize_rollback()

    results = evaluate_changes()
    actions = []

    for result in results:
        if result["decision"] != "rollback_recommended":
            continue

        action = request_rollback(result)
        actions.append(action)

    return actions


def main():
    initialize_rollback()

    print("Rollback database initialized.")

    actions = process_rollbacks()

    print(json.dumps(actions, indent=2))


if __name__ == "__main__":
    main()
