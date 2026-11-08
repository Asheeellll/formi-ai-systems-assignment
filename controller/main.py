
import json
import os
import time
import urllib.error
import urllib.request


BASE_URL = os.environ.get(
    "SIM_URL",
    "http://127.0.0.1:8700",
).rstrip("/")


def api_request(method, path, payload=None, retries=3):
    """
    Communicate with the simulator exclusively through HTTP.

    GET requests can be retried.
    Mutating requests are not automatically retried because
    the simulator may have processed them before a timeout.
    """
    url = BASE_URL + path

    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    attempts = retries if method.upper() == "GET" else 1

    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=60,
            ) as response:
                body = response.read().decode("utf-8")

                content_type = response.headers.get(
                    "Content-Type",
                    "",
                )

                if "application/json" in content_type:
                    return json.loads(body)

                return body

        except urllib.error.HTTPError as error:
            detail = error.read().decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                f"HTTP {error.code} on "
                f"{method} {path}: {detail}"
            ) from error

        except (
            urllib.error.URLError,
            TimeoutError,
        ):
            if attempt == attempts - 1:
                raise

            time.sleep(2 ** attempt)


def initialize_controller():
    """Initialize all persistent controller tables."""
    from controller.database import initialize
    from controller.governance import initialize_governance
    from controller.monitoring import initialize_monitoring
    from controller.rollback import initialize_rollback

    initialize()
    initialize_governance()
    initialize_monitoring()
    initialize_rollback()


def ingest_events():
    """Fetch and persist available simulator events."""
    from controller.ingestion import sync_chunks

    result = sync_chunks()

    if result["chunks_processed"]:
        print(
            f"[INGESTION] "
            f"Chunks: {result['chunks_processed']} | "
            f"New events: {result['events_inserted']}",
            flush=True,
        )

    return result


def process_approvals():
    """Recover approval state and apply approved proposals."""
    from controller.governance import reconcile_approvals

    results = reconcile_approvals()

    for proposal_id, status in results:
        print(
            f"[GOVERNANCE] {proposal_id}: {status}",
            flush=True,
        )

    return results


def process_monitoring():
    """Evaluate applied configurations for KPI deterioration."""
    from controller.monitoring import evaluate_changes
    from controller.database import log_action

    results = evaluate_changes()

    for result in results:
        print(
            f"[MONITORING] "
            f"{result['workflow_id']} | "
            f"Version: {result['applied_version']} | "
            f"Samples: {result['sample_size']} | "
            f"Decision: {result['decision']}",
            flush=True,
        )

        if result["decision"] == "rollback_recommended":
            log_action(
                "rollback_recommended",
                workflow_id=result["workflow_id"],
                details=result,
            )

            print(
                "[WARNING] KPI deterioration detected. "
                "Checking rollback governance.",
                flush=True,
            )

    return results


def process_rollback_actions():
    """
    Submit rollback proposals through the governance pathway.

    Never bypass workflow approval requirements.
    """
    from controller.rollback import process_rollbacks
    from controller.database import log_action

    actions = process_rollbacks()

    for action in actions:
        status = action.get("status", "unknown")

        print(
            f"[ROLLBACK] Status: {status}",
            flush=True,
        )

        log_action(
            "rollback_action",
            workflow_id=action.get("workflow_id"),
            details=action,
        )

    return actions


def process_optimization():
    """Run a KPI-driven optimization decision cycle."""
    from controller.optimizer import run_optimizer

    decisions = run_optimizer()

    for decision in decisions:
        print(
            f"[OPTIMIZER] "
            f"{decision['workflow_id']} | "
            f"{decision['decision']}",
            flush=True,
        )

    return decisions

def get_tick_limit():
    """
    MAX_TICKS=0 runs until the simulator finishes.
    Positive values limit the number of simulation ticks.
    """
    value = int(
        os.environ.get("MAX_TICKS", "4")
    )

    if value < 0:
        raise ValueError(
            "MAX_TICKS must be zero or a positive integer"
        )

    return value


def main():
    from controller.database import log_action

    initialize_controller()

    max_ticks = get_tick_limit()

    print(
        "\nStarting autonomous controller...",
        flush=True,
    )

    if max_ticks == 0:
        print(
            "Mode: unattended until simulation completion",
            flush=True,
        )
    else:
        print(
            f"Mode: bounded test ({max_ticks} ticks)",
            flush=True,
        )

    ticks_completed = 0
    last_optimization_day = None

    print(
        "[STARTUP] Reconciling approvals...",
        flush=True,
    )

    process_approvals()

    while True:
        state = api_request(
            "GET",
            "/sim/state",
        )
        # Prevent accidental reuse of another simulator's database.
        from controller.identity import verify_simulator_identity

        identity_status = verify_simulator_identity(state)

        minute = state["sim_minute"]
        finished = state["finished"]

        print(
            f"\n[STATE] "
            f"Minute: {minute}/{state['end_minute']} | "
            f"Finished: {finished} | "
            f"Credits: {state['credits_remaining']}",
            flush=True,
        )

        # 1. Ingest simulator events before making decisions.
        ingest_events()

        # 2. Reconcile pending and approved proposals.
        process_approvals()

        # 3. Evaluate KPI performance after applied changes.
        process_monitoring()

        # 4. Submit governed rollback proposals when needed.
        if not finished:
            process_rollback_actions()
             # 5. Run optimization once per simulated day.
        # Also run once immediately after controller startup.
        simulation_day = minute // 1440

        if (
            not finished
            and simulation_day != last_optimization_day
        ):
            print(
                f"[OPTIMIZER] Evaluating simulation day "
                f"{simulation_day}",
                flush=True,
            )

            process_optimization()
            last_optimization_day = simulation_day

        # 5. Stop after processing final simulator events.
        if finished:
            log_action(
                "simulation_finished",
                details={
                    "sim_minute": minute,
                    "ticks_this_run": ticks_completed,
                },
            )

            print(
                "[COMPLETE] Simulation finished.",
                flush=True,
            )
            break

        # 6. Respect bounded test execution.
        if max_ticks > 0 and ticks_completed >= max_ticks:
            print(
                "[STOP] Configured tick limit reached.",
                flush=True,
            )
            break

        tick = state["tick_minutes"]

        # 7. Advance simulation without blindly retrying POST.
        try:
            response = api_request(
                "POST",
                "/sim/advance",
                {"minutes": tick},
            )

        except Exception as exc:
            log_action(
                "simulation_advance_uncertain",
                details={
                    "from_minute": minute,
                    "requested_minutes": tick,
                    "error": str(exc),
                },
            )

            print(
                f"[ERROR] Advance outcome uncertain: {exc}",
                flush=True,
            )

            raise

        new_minute = response["sim_minute"]

        if new_minute <= minute:
            raise RuntimeError(
                "Simulator did not advance: "
                f"{minute} -> {new_minute}"
            )

        ticks_completed += 1

        log_action(
            "simulation_advanced",
            details={
                "from_minute": minute,
                "to_minute": new_minute,
                "tick_number": ticks_completed,
            },
        )

        print(
            f"[ADVANCE] {minute} -> {new_minute}",
            flush=True,
        )

        if response.get("new_chunks"):
            print(
                "[EVENTS] New chunks:",
                json.dumps(response["new_chunks"]),
                flush=True,
            )

    print(
        f"\nController stopped after "
        f"{ticks_completed} ticks this run.",
        flush=True,
    )


if __name__ == "__main__":
    main()
