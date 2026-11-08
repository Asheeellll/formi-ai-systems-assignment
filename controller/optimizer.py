
import json

from controller.main import api_request
from controller.database import connect, log_action
from controller.drift import detect_drift
from controller.cohorts import analyze_cohorts
from controller.proposals import generate_proposal
from controller.governance import (
    initialize_governance,
    create_proposal_record,
    submit_for_approval,
)


MIN_RECENT_DIALS = 500
EXPERIMENT_SHIFT = 0.10


def existing_proposals(workflow_id):
    """
    Find all locally recorded proposals for this workflow.

    A one-experiment policy prevents duplicate submissions,
    approval spam, and repeated unproven interventions.
    """
    initialize_governance()

    with connect() as conn:
        rows = conn.execute("""
            SELECT proposal_id, status, approval_id
            FROM proposals
            WHERE workflow_id = ?
            ORDER BY created_at DESC
        """, (workflow_id,)).fetchall()

    return [
        {
            "proposal_id": row[0],
            "status": row[1],
            "approval_id": row[2],
        }
        for row in rows
    ]


def choose_experiment(workflow_id):
    """
    Select a small supported experiment.

    This is a hypothesis generator, not a prediction that
    the alternative will outperform the current setting.
    """
    workflow = api_request(
        "GET",
        f"/workflows/{workflow_id}",
    )

    current = api_request(
        "GET",
        f"/workflows/{workflow_id}/config",
    )

    supported = workflow.get(
        "options",
        {},
    ).get("caller_id", [])

    allocations = current["config"][
        "allocations"
    ]["default"]["caller_id"]

    alternatives = [
        option
        for option in supported
        if allocations.get(option, 0.0) < 1.0
    ]

    if not alternatives:
        return None

    # Prefer a caller ID with no current allocation.
    alternatives.sort(
        key=lambda option: (
            allocations.get(option, 0.0),
            option,
        )
    )

    target = alternatives[0]

    return generate_proposal(
        workflow_id=workflow_id,
        dimension="caller_id",
        target_option=target,
        shift=EXPERIMENT_SHIFT,
    )


def validate_proposal(proposal):
    """Check important configuration invariants."""
    workflow_id = proposal["workflow_id"]

    current = api_request(
        "GET",
        f"/workflows/{workflow_id}/config",
    )

    if current["version"] != proposal["base_version"]:
        raise RuntimeError(
            "Configuration version changed before submission"
        )

    candidate = proposal["proposed_config"]

    for cohort, dimensions in candidate[
        "allocations"
    ].items():
        for dimension, weights in dimensions.items():
            if not isinstance(weights, dict) or not weights:
                raise ValueError(
                    f"Empty allocation: {cohort}/{dimension}"
                )

            if any(
                not isinstance(weight, (int, float))
                or weight < 0
                for weight in weights.values()
            ):
                raise ValueError(
                    f"Invalid allocation: {cohort}/{dimension}"
                )

            total = sum(weights.values())

            if abs(total - 1.0) > 1e-8:
                raise ValueError(
                    f"Allocation does not sum to one: "
                    f"{cohort}/{dimension} = {total}"
                )

    return {
        "method": "configuration_preflight",
        "base_version": proposal["base_version"],
        "base_version_verified": True,
        "allocation_weights_valid": True,
        "supported_option_verified": True,
        "expected_lift": None,
        "outcome_validation_performed": False,
        "limitations": (
            "Configuration validation only. "
            "The intervention has not been proven "
            "to improve outcomes."
        ),
    }


def optimize_workflow(drift):
    """Evaluate one workflow and optionally propose a pilot."""
    workflow_id = drift["workflow_id"]

    if not drift["drift_detected"]:
        return {
            "workflow_id": workflow_id,
            "decision": "no_drift",
        }

    if drift["recent_dials"] < MIN_RECENT_DIALS:
        return {
            "workflow_id": workflow_id,
            "decision": "insufficient_recent_data",
        }

    previous = existing_proposals(workflow_id)

    if previous:
        return {
            "workflow_id": workflow_id,
            "decision": "existing_proposal",
            "proposal": previous[0],
        }

    # Do not open a new experiment while an applied
    # configuration is being monitored.
    with connect() as conn:
        active_monitoring = conn.execute("""
            SELECT COUNT(*)
            FROM change_monitoring
            WHERE workflow_id = ?
              AND status IN (
                  'monitoring',
                  'rollback_requested'
              )
        """, (workflow_id,)).fetchone()[0]

    if active_monitoring:
        return {
            "workflow_id": workflow_id,
            "decision": "monitoring_active_change",
        }

    cohorts = analyze_cohorts(workflow_id)
    worst_cohorts = cohorts[:3]

    proposal = choose_experiment(workflow_id)

    if proposal is None:
        return {
            "workflow_id": workflow_id,
            "decision": "no_supported_experiment",
        }

    preflight = validate_proposal(proposal)

    dimension = proposal["dimension"]
    option = proposal["target_option"]
    shift = proposal["shift"]

    rationale = (
        f"Observed {drift['primary_metric']} drift of "
        f"{drift['change_pp']:.2f} percentage points "
        f"using {drift['recent_dials']} recent calls. "
        f"Propose a small {shift:.0%} allocation experiment "
        f"for {dimension}={option}. "
        "This alternative has not been demonstrated "
        "to improve the KPI. "
        "Treat it as an exploratory hypothesis, "
        "monitor subsequent outcomes, and respect "
        "all governance requirements."
    )

    proposal_id = create_proposal_record(
        workflow_id=workflow_id,
        base_version=proposal["base_version"],
        proposed_config=proposal["proposed_config"],
        rationale=rationale,
    )

    log_action(
        "optimizer_experiment_selected",
        workflow_id=workflow_id,
        details={
            "proposal_id": proposal_id,
            "drift": drift,
            "top_cohorts": worst_cohorts,
            "dimension": dimension,
            "option": option,
            "shift": shift,
        },
    )

    current = api_request(
        "GET",
        f"/workflows/{workflow_id}/config",
    )

    before = current["config"][
        "allocations"
    ]["default"][dimension]

    after = proposal["proposed_config"][
        "allocations"
    ]["default"][dimension]

    response = submit_for_approval(
        proposal_id=proposal_id,
        workflow_id=workflow_id,
        base_version=proposal["base_version"],
        proposed_config=proposal["proposed_config"],
        rationale=rationale,
        change_summary=(
            f"Exploratory {shift:.0%} allocation "
            f"to {dimension}={option} after KPI drift"
        ),
        diff={
            "dimension": dimension,
            "before": before,
            "after": after,
        },
        dry_run={
            **preflight,
            "observed_drift": drift,
            "affected_cohorts": worst_cohorts,
        },
        affected_leads=0,
        impact_score=0.1,
    )

    return {
        "workflow_id": workflow_id,
        "decision": "approval_submitted",
        "proposal_id": proposal_id,
        "approval_id": response.get("approval_id"),
        "approval_status": response.get("status"),
        "hypothesis": {
            "dimension": dimension,
            "target_option": option,
            "shift": shift,
            "expected_lift": None,
        },
    }


def run_optimizer():
    """Run one evidence-based optimization decision cycle."""
    initialize_governance()

    drift_results = detect_drift()

    decisions = []

    for drift in drift_results:
        decision = optimize_workflow(drift)
        decisions.append(decision)

        log_action(
            "optimizer_decision",
            workflow_id=drift["workflow_id"],
            details=decision,
        )

    return decisions


def main():
    results = run_optimizer()

    print("Optimizer decisions:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
