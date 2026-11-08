
import copy
import json

from controller.main import api_request


def generate_proposal(workflow_id, dimension, target_option, shift=0.10):
    """
    Generate a candidate configuration without applying it.

    This function performs no simulator mutations.
    """

    workflow = api_request(
        "GET",
        f"/workflows/{workflow_id}",
    )

    current = api_request(
        "GET",
        f"/workflows/{workflow_id}/config",
    )

    options = workflow.get("options", {})

    if dimension not in (
        "welcome_message",
        "voice",
        "caller_id",
    ):
        raise ValueError(
            f"Unsupported allocation dimension: {dimension}"
        )

    if target_option not in options.get(dimension, []):
        raise ValueError(
            f"{target_option} is not allowed for {dimension}"
        )

    if not 0 < shift <= 1:
        raise ValueError("shift must be between 0 and 1")

    proposed = copy.deepcopy(current["config"])

    allocations = proposed["allocations"]["default"]
    existing = allocations[dimension]

    if target_option in existing and existing[target_option] == 1.0:
        raise ValueError("Target option already has 100% allocation")

    # Preserve relative allocation among existing options.
    new_allocation = {
        option: weight * (1 - shift)
        for option, weight in existing.items()
    }

    new_allocation[target_option] = (
        new_allocation.get(target_option, 0.0) + shift
    )

    allocations[dimension] = new_allocation

    governance = workflow.get("governance", {})
    auto_apply = governance.get("auto_apply", {})

    can_auto_apply = (
        auto_apply.get("enabled", False)
        and dimension in auto_apply.get("allowed_dims", [])
        and shift <= auto_apply.get("max_shift", 0)
    )

    return {
        "workflow_id": workflow_id,
        "base_version": current["version"],
        "dimension": dimension,
        "target_option": target_option,
        "shift": shift,
        "can_auto_apply": can_auto_apply,
        "requires_approval": not can_auto_apply,
        "proposed_config": proposed,
    }


def main():
    proposal = generate_proposal(
        workflow_id="nw_kyc",
        dimension="caller_id",
        target_option="D2",
        shift=0.10,
    )

    print(json.dumps(proposal, indent=2))


if __name__ == "__main__":
    main()

