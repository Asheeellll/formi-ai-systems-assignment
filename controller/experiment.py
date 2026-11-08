
import json
import math

from controller.database import connect


MIN_CALLS_PER_VARIANT = 200
Z_SCORE = 1.96


def wilson_interval(successes, trials, z=Z_SCORE):
    if trials <= 0:
        return None

    p = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials

    center = (
        p + z2 / (2 * trials)
    ) / denominator

    margin = (
        z * math.sqrt(
            p * (1 - p) / trials
            + z2 / (4 * trials * trials)
        )
    ) / denominator

    return [
        center - margin,
        center + margin,
    ]


def get_variant_metrics(
    workflow_id,
    config_version,
    dimension="caller_id",
):
    allowed_dimensions = {
        "caller_id",
        "voice",
        "welcome_message",
    }

    if dimension not in allowed_dimensions:
        raise ValueError(
            f"Unsupported dimension: {dimension}"
        )

    path = f"$.variant.{dimension}"

    with connect() as conn:
        rows = conn.execute("""
            SELECT
                json_extract(payload, ?) AS variant,
                COUNT(*) AS dials,
                SUM(
                    CASE
                        WHEN json_extract(payload, '$.connected') = 1
                        THEN 1 ELSE 0
                    END
                ) AS connected,
                SUM(
                    CASE
                        WHEN json_extract(payload, '$.engaged') = 1
                        THEN 1 ELSE 0
                    END
                ) AS engaged
            FROM events
            WHERE event_type = 'call'
              AND workflow_id = ?
              AND CAST(
                  json_extract(payload, '$.config_version')
                  AS INTEGER
              ) = ?
            GROUP BY variant
            ORDER BY variant
        """, (
            path,
            workflow_id,
            config_version,
        )).fetchall()

    results = []

    for variant, dials, connected, engaged in rows:
        connected = connected or 0
        engaged = engaged or 0

        results.append({
            "variant": variant,
            "dials": dials,
            "connected": connected,
            "engaged": engaged,
            "pickup_rate": connected / dials if dials else None,
            "engagement_rate": (
                engaged / connected if connected else None
            ),
            "pickup_ci_95": wilson_interval(
                connected,
                dials,
            ),
        })

    return results


def compare_variants(
    workflow_id,
    config_version,
    control="D1",
    treatment="D2",
):
    variants = get_variant_metrics(
        workflow_id,
        config_version,
    )

    by_name = {
        item["variant"]: item
        for item in variants
    }

    if control not in by_name or treatment not in by_name:
        return {
            "decision": "missing_variant",
            "variants": variants,
        }

    a = by_name[control]
    b = by_name[treatment]

    result = {
        "workflow_id": workflow_id,
        "config_version": config_version,
        "control": a,
        "treatment": b,
        "decision": "insufficient_data",
        "difference_pp": None,
        "p_value": None,
    }

    if (
        a["dials"] < MIN_CALLS_PER_VARIANT
        or b["dials"] < MIN_CALLS_PER_VARIANT
    ):
        return result

    p1 = a["pickup_rate"]
    p2 = b["pickup_rate"]

    difference = p2 - p1

    pooled = (
        a["connected"] + b["connected"]
    ) / (
        a["dials"] + b["dials"]
    )

    standard_error = math.sqrt(
        pooled * (1 - pooled) * (
            1 / a["dials"] + 1 / b["dials"]
        )
    )

    if standard_error == 0:
        return {
            **result,
            "difference_pp": difference * 100,
            "decision": "no_detectable_difference",
        }

    z = difference / standard_error

    # Two-sided normal approximation.
    p_value = math.erfc(
        abs(z) / math.sqrt(2)
    )

    if p_value < 0.05:
        decision = (
            "treatment_better"
            if difference > 0
            else "treatment_worse"
        )
    else:
        decision = "inconclusive"

    return {
        **result,
        "difference_pp": difference * 100,
        "p_value": p_value,
        "decision": decision,
    }


def main():
    result = compare_variants(
        workflow_id="nw_kyc",
        config_version=2,
        control="D1",
        treatment="D2",
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

