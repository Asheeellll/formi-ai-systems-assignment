
import json
import uuid
from datetime import datetime, timezone

from controller.main import api_request
from controller.database import connect, log_action


PRIMARY_METRICS = {
    "nw_renewal": "engagement_rate",
    "nw_kyc": "pickup_rate",
    "ks_cancel": "engagement_rate",
}


def initialize_governance():
    """Create durable approval and application records."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                proposal_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                base_version INTEGER NOT NULL,
                proposed_config TEXT NOT NULL,
                rationale TEXT NOT NULL,
                status TEXT NOT NULL,
                approval_id TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS apply_intents (
                proposal_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                base_version INTEGER NOT NULL,
                previous_config TEXT NOT NULL,
                proposed_config TEXT NOT NULL,
                event_watermark INTEGER NOT NULL,
                primary_metric TEXT NOT NULL,
                baseline_rate REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()


def create_proposal_record(
    workflow_id,
    base_version,
    proposed_config,
    rationale,
):
    """Persist a proposal before submitting it."""
    initialize_governance()

    proposal_id = f"agent-{uuid.uuid4().hex[:16]}"

    with connect() as conn:
        conn.execute("""
            INSERT INTO proposals (
                proposal_id,
                workflow_id,
                base_version,
                proposed_config,
                rationale,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            proposal_id,
            workflow_id,
            base_version,
            json.dumps(proposed_config),
            rationale,
            "created",
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()

    log_action(
        "proposal_created",
        workflow_id=workflow_id,
        details={"proposal_id": proposal_id},
    )

    return proposal_id


def update_proposal(proposal_id, status, approval_id=None):
    """Update the persisted proposal state."""
    with connect() as conn:
        conn.execute("""
            UPDATE proposals
            SET status = ?,
                approval_id = COALESCE(?, approval_id)
            WHERE proposal_id = ?
        """, (
            status,
            approval_id,
            proposal_id,
        ))

        conn.commit()


def submit_for_approval(
    proposal_id,
    workflow_id,
    base_version,
    proposed_config,
    rationale,
    change_summary,
    diff,
    dry_run,
    affected_leads=0,
    impact_score=0.5,
):
    """Submit a governed configuration proposal."""
    initialize_governance()

    if not all((change_summary, diff, dry_run, rationale)):
        raise ValueError("Approval evidence must not be empty")

    if not isinstance(affected_leads, int) or affected_leads < 0:
        raise ValueError("affected_leads must be non-negative")

    if not 0 <= impact_score <= 1:
        raise ValueError("impact_score must be between 0 and 1")

    payload = {
        "proposal_id": proposal_id,
        "workflow_id": workflow_id,
        "base_version": base_version,
        "proposed_config": proposed_config,
        "change_summary": change_summary,
        "diff": diff,
        "affected_leads": affected_leads,
        "dry_run": dry_run,
        "impact_score": impact_score,
        "rationale": rationale,
        "expires_in_hours": 12,
    }

    update_proposal(proposal_id, "submitting")

    try:
        response = api_request(
            "POST",
            "/approvals",
            payload,
        )
    except Exception as exc:
        log_action(
            "approval_submission_uncertain",
            workflow_id=workflow_id,
            details={
                "proposal_id": proposal_id,
                "error": str(exc),
            },
        )
        raise

    approval_id = (
        response.get("approval_id")
        or response.get("id")
    )

    if not approval_id:
        raise RuntimeError(
            f"Approval response missing ID: {response}"
        )

    update_proposal(
        proposal_id,
        "pending",
        approval_id,
    )

    log_action(
        "approval_submitted",
        workflow_id=workflow_id,
        details={
            "proposal_id": proposal_id,
            "approval_id": approval_id,
        },
    )

    return response


def _extract_approvals(response):
    """Normalize the simulator's approval listing."""
    if isinstance(response, list):
        return response

    if isinstance(response, dict):
        for key in ("approvals", "items", "results"):
            if isinstance(response.get(key), list):
                return response[key]

    raise RuntimeError(
        f"Unexpected approval response: {response}"
    )


def get_apply_intent(proposal_id):
    """Read a previously persisted application intent."""
    with connect() as conn:
        row = conn.execute("""
            SELECT
                workflow_id,
                base_version,
                previous_config,
                proposed_config,
                event_watermark,
                primary_metric,
                baseline_rate
            FROM apply_intents
            WHERE proposal_id = ?
        """, (proposal_id,)).fetchone()

    if row is None:
        return None

    return {
        "workflow_id": row[0],
        "base_version": row[1],
        "previous_config": json.loads(row[2]),
        "proposed_config": json.loads(row[3]),
        "event_watermark": row[4],
        "primary_metric": row[5],
        "baseline_rate": row[6],
    }


def prepare_apply_intent(
    proposal_id,
    workflow_id,
    base_version,
    proposed_config,
):
    """
    Durably capture the rollback target and KPI baseline
    BEFORE sending the apply request.
    """
    from controller.monitoring import (
        calculate_metric,
        get_latest_event_id,
    )

    existing = get_apply_intent(proposal_id)

    if existing is not None:
        return existing

    current = api_request(
        "GET",
        f"/workflows/{workflow_id}/config",
    )

    if current["version"] != base_version:
        raise RuntimeError(
            f"Stale configuration for {workflow_id}: "
            f"expected v{base_version}, "
            f"found v{current['version']}"
        )

    metric = PRIMARY_METRICS.get(workflow_id)

    if metric is None:
        raise RuntimeError(
            f"Unknown primary metric for {workflow_id}"
        )

    baseline = calculate_metric(workflow_id, metric)

    if baseline["rate"] is None:
        raise RuntimeError(
            f"No baseline observations for {workflow_id}"
        )

    event_watermark = get_latest_event_id()

    with connect() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO apply_intents (
                proposal_id,
                workflow_id,
                base_version,
                previous_config,
                proposed_config,
                event_watermark,
                primary_metric,
                baseline_rate,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            proposal_id,
            workflow_id,
            base_version,
            json.dumps(current["config"]),
            json.dumps(proposed_config),
            event_watermark,
            metric,
            baseline["rate"],
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()

    log_action(
        "apply_intent_saved",
        workflow_id=workflow_id,
        details={
            "proposal_id": proposal_id,
            "base_version": base_version,
            "event_watermark": event_watermark,
            "primary_metric": metric,
            "baseline_rate": baseline["rate"],
        },
    )

    return get_apply_intent(proposal_id)


def finalize_applied_change(proposal_id, workflow_id):
    """
    Recover or register a confirmed application.

    Uses the pre-apply event watermark, not a newly
    calculated watermark after the change.
    """
    from controller.monitoring import initialize_monitoring

    initialize_monitoring()

    intent = get_apply_intent(proposal_id)

    if intent is None:
        log_action(
            "applied_change_missing_intent",
            workflow_id=workflow_id,
            details={"proposal_id": proposal_id},
        )
        return "applied_untracked"

    current = api_request(
        "GET",
        f"/workflows/{workflow_id}/config",
    )

    if current["config"] != intent["proposed_config"]:
        log_action(
            "applied_change_config_mismatch",
            workflow_id=workflow_id,
            details={
                "proposal_id": proposal_id,
                "current_version": current["version"],
            },
        )
        return "applied_config_changed"

    if current["version"] <= intent["base_version"]:
        return "applied_version_unconfirmed"

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'monitoring')
        """, (
            proposal_id,
            workflow_id,
            json.dumps(intent["previous_config"]),
            json.dumps(intent["proposed_config"]),
            current["version"],
            intent["event_watermark"],
            intent["primary_metric"],
            intent["baseline_rate"],
        ))

        # Record application only after monitoring registration.
        conn.execute("""
            UPDATE proposals
            SET status = 'applied'
            WHERE proposal_id = ?
        """, (proposal_id,))

        conn.commit()

    log_action(
        "change_registered_for_monitoring",
        workflow_id=workflow_id,
        details={
            "proposal_id": proposal_id,
            "applied_version": current["version"],
            "event_watermark": intent["event_watermark"],
        },
    )

    return "applied"


def reconcile_approvals():
    """Reconcile, apply, and recover governed changes."""
    initialize_governance()

    remote_response = api_request(
        "GET",
        "/approvals",
    )

    remote_approvals = _extract_approvals(
        remote_response
    )

    remote_by_proposal = {
        approval["proposal_id"]: approval
        for approval in remote_approvals
        if isinstance(approval, dict)
        and approval.get("proposal_id")
    }

    with connect() as conn:
        rows = conn.execute("""
            SELECT
                proposal_id,
                workflow_id,
                base_version,
                proposed_config,
                approval_id,
                status
            FROM proposals
            WHERE status IN (
                'created',
                'submitting',
                'pending',
                'approved',
                'applied_untracked',
                'applied_config_changed',
                'applied_version_unconfirmed'
            )
        """).fetchall()

    results = []

    for (
        proposal_id,
        workflow_id,
        base_version,
        proposed_json,
        approval_id,
        local_status,
    ) in rows:

        proposed_config = json.loads(
            proposed_json
        )

        if not approval_id:
            remote = remote_by_proposal.get(
                proposal_id
            )

            if remote:
                approval_id = (
                    remote.get("approval_id")
                    or remote.get("id")
                )

                if approval_id:
                    update_proposal(
                        proposal_id,
                        "pending",
                        approval_id,
                    )

            if not approval_id:
                results.append((
                    proposal_id,
                    "submission_unconfirmed",
                ))
                continue

        approval = api_request(
            "GET",
            f"/approvals/{approval_id}",
        )

        status = approval.get("status")

        if status == "pending":
            update_proposal(
                proposal_id,
                "pending",
            )

            results.append((
                proposal_id,
                "pending",
            ))
            continue

        if status in (
            "rejected",
            "expired",
            "lapsed",
        ):
            update_proposal(
                proposal_id,
                status,
            )

            results.append((
                proposal_id,
                status,
            ))
            continue

        if status == "approved":
            # Prepare safely before any external mutation.
            try:
                prepare_apply_intent(
                    proposal_id,
                    workflow_id,
                    base_version,
                    proposed_config,
                )

            except Exception as exc:
                log_action(
                    "apply_preparation_failed",
                    workflow_id=workflow_id,
                    details={
                        "proposal_id": proposal_id,
                        "error": str(exc),
                    },
                )

                results.append((
                    proposal_id,
                    "apply_preparation_failed",
                ))
                continue

            # No blind retry if a mutating HTTP request fails.
            try:
                api_request(
                    "POST",
                    f"/workflows/{workflow_id}/apply",
                    {"approval_id": approval_id},
                )

            except Exception as exc:
                log_action(
                    "apply_outcome_uncertain",
                    workflow_id=workflow_id,
                    details={
                        "proposal_id": proposal_id,
                        "approval_id": approval_id,
                        "error": str(exc),
                    },
                )

                # Ask the simulator for authoritative state.
                latest = api_request(
                    "GET",
                    f"/approvals/{approval_id}",
                )

                if latest.get("status") == "applied":
                    status = "applied"

                elif latest.get("status") in (
                    "lapsed",
                    "expired",
                    "rejected",
                ):
                    final_status = latest["status"]

                    update_proposal(
                        proposal_id,
                        final_status,
                    )

                    results.append((
                        proposal_id,
                        final_status,
                    ))
                    continue

                else:
                    update_proposal(
                        proposal_id,
                        "approved",
                    )

                    results.append((
                        proposal_id,
                        "apply_outcome_uncertain",
                    ))
                    continue

            else:
                status = "applied"

        if status == "applied":
            final_status = finalize_applied_change(
                proposal_id,
                workflow_id,
            )

            update_proposal(
                proposal_id,
                final_status,
            )

            results.append((
                proposal_id,
                final_status,
            ))
            continue

        log_action(
            "approval_unknown_status",
            workflow_id=workflow_id,
            details={
                "proposal_id": proposal_id,
                "approval_id": approval_id,
                "remote_status": status,
            },
        )

        results.append((
            proposal_id,
            f"unknown_status:{status}",
        ))

    return results


def main():
    initialize_governance()

    print(
        "Governance database initialized."
    )

    results = reconcile_approvals()

    print(
        "Existing approvals:"
    )

    print(
        json.dumps(
            results,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
