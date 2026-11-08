
import json

from controller.main import api_request
from controller.proposals import generate_proposal
from controller.governance import (
    create_proposal_record,
    submit_for_approval,
)


def main():
    workflow_id = "nw_kyc"

    # Check the live configuration before proposing.
    current = api_request(
        "GET",
        f"/workflows/{workflow_id}/config",
    )

    print("Current config version:", current["version"])

    proposal = generate_proposal(
        workflow_id=workflow_id,
        dimension="caller_id",
        target_option="D2",
        shift=0.10,
    )

    if proposal["base_version"] != current["version"]:
        raise RuntimeError("Configuration changed during proposal creation")

    if not proposal["requires_approval"]:
        raise RuntimeError("Expected this workflow to require approval")

    rationale = (
        "Explore a small 10% D2 caller-ID allocation for KYC calls. "
        "Historical KYC calls used only D1, so D2's effect is unknown. "
        "This is an experiment, not a claimed improvement. "
        "Monitor pickup and engagement rates and revert if guardrails worsen."
    )

    proposal_id = create_proposal_record(
        workflow_id=workflow_id,
        base_version=proposal["base_version"],
        proposed_config=proposal["proposed_config"],
        rationale=rationale,
    )

    print("Saved proposal:", proposal_id)

    response = submit_for_approval(
        proposal_id=proposal_id,
        workflow_id=workflow_id,
        base_version=proposal["base_version"],
        proposed_config=proposal["proposed_config"],
        rationale=rationale,
        change_summary=(
            "Test D2 caller ID on 10% of KYC calls; retain D1 on 90%"
        ),
        diff={
            "dimension": "caller_id",
            "before": {"D1": 1.0},
            "after": {"D1": 0.9, "D2": 0.1},
        },
        dry_run={
            "method": "configuration_and_governance_preflight",
            "base_version": proposal["base_version"],
            "allocation_sum": 1.0,
            "target_option_supported": True,
            "historical_D2_KYC_calls": 0,
            "expected_lift": None,
            "limitations": (
                "No historical KYC outcomes for D2; "
                "this preflight is not an outcome replay."
            ),
        },
        affected_leads=0,
        impact_score=0.1,
    )

    print("\nApproval response:")
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
