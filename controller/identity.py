
import json

from controller.database import connect


def verify_simulator_identity(state):
    """
    Bind persistent controller state to one simulator run.

    Detects scenario changes and obvious run resets.
    Does not require access to simulator internals.
    """
    scenario = state["scenario"]
    sim_minute = int(state["sim_minute"])
    end_minute = int(state["end_minute"])
    last_event_id = int(state["last_event_id"])

    with connect() as conn:
        row = conn.execute("""
            SELECT value
            FROM controller_state
            WHERE key = 'simulator_identity'
        """).fetchone()

        if row is None:
            identity = {
                "scenario": scenario,
                "end_minute": end_minute,
                "highest_minute": sim_minute,
                "highest_event_id": last_event_id,
            }

            conn.execute("""
                INSERT INTO controller_state (key, value)
                VALUES ('simulator_identity', ?)
            """, (json.dumps(identity),))

            conn.commit()

            return "identity_initialized"

        saved = json.loads(row[0])

        if saved["scenario"] != scenario:
            raise RuntimeError(
                "Database belongs to scenario "
                f"{saved['scenario']}, not {scenario}. "
                "Use a separate CONTROLLER_DB."
            )

        if saved["end_minute"] != end_minute:
            raise RuntimeError(
                "Simulator end-minute mismatch. "
                "Possible scenario reset or database reuse."
            )

        if sim_minute < saved["highest_minute"]:
            raise RuntimeError(
                "Simulator time moved backwards. "
                "Possible run reset or wrong simulator instance."
            )

        if last_event_id < saved["highest_event_id"]:
            raise RuntimeError(
                "Simulator event IDs moved backwards. "
                "Possible run reset or wrong simulator instance."
            )

        saved["highest_minute"] = max(
            saved["highest_minute"],
            sim_minute,
        )

        saved["highest_event_id"] = max(
            saved["highest_event_id"],
            last_event_id,
        )

        conn.execute("""
            UPDATE controller_state
            SET value = ?
            WHERE key = 'simulator_identity'
        """, (json.dumps(saved),))

        conn.commit()

    return "identity_verified"


def main():
    from controller.main import api_request
    from controller.database import initialize

    initialize()

    state = api_request("GET", "/sim/state")

    result = verify_simulator_identity(state)

    print("Scenario:", state["scenario"])
    print("Verification:", result)


if __name__ == "__main__":
    main()
