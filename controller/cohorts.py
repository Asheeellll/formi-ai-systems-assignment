
import json
from collections import defaultdict

from controller.database import connect


FEATURES = (
    "lang",
    "city_tier",
    "age_band",
    "value_band",
)


def analyze_cohorts(workflow_id="nw_kyc", recent_days=3):
    """Compare recent and historical pickup rates by lead feature."""

    with connect() as conn:
        lead_rows = conn.execute(
            """
            SELECT payload
            FROM events
            WHERE event_type = 'lead'
              AND workflow_id = ?
            """,
            (workflow_id,),
        ).fetchall()

        call_rows = conn.execute(
            """
            SELECT payload
            FROM events
            WHERE event_type = 'call'
              AND workflow_id = ?
            ORDER BY event_ts
            """,
            (workflow_id,),
        ).fetchall()

    leads = {}

    for (payload,) in lead_rows:
        lead = json.loads(payload)
        key = (lead.get("campaign_id"), lead.get("lead_id"))
        leads[key] = lead.get("features", {})

    calls = [json.loads(payload) for (payload,) in call_rows]

    if not calls:
        return []

    days = sorted({
        call["ts"][:10]
        for call in calls
        if call.get("ts")
    })

    recent_dates = set(days[-recent_days:])

    stats = defaultdict(
        lambda: {
            "historical_dials": 0,
            "historical_connected": 0,
            "recent_dials": 0,
            "recent_connected": 0,
        }
    )

    for call in calls:
        key = (call.get("campaign_id"), call.get("lead_id"))
        features = leads.get(key)

        if features is None:
            continue

        period = (
            "recent"
            if call["ts"][:10] in recent_dates
            else "historical"
        )

        for feature in FEATURES:
            value = features.get(feature)

            if value is None:
                continue

            item = stats[(feature, str(value))]
            item[f"{period}_dials"] += 1

            if call.get("connected"):
                item[f"{period}_connected"] += 1

    results = []

    for (feature, value), item in stats.items():
        historical_dials = item["historical_dials"]
        recent_dials = item["recent_dials"]

        if historical_dials < 100 or recent_dials < 50:
            continue

        historical_rate = (
            item["historical_connected"] / historical_dials
        )
        recent_rate = (
            item["recent_connected"] / recent_dials
        )

        results.append({
            "feature": feature,
            "value": value,
            "historical_dials": historical_dials,
            "recent_dials": recent_dials,
            "historical_rate": historical_rate,
            "recent_rate": recent_rate,
            "change_pp": (
                recent_rate - historical_rate
            ) * 100,
        })

    return sorted(
        results,
        key=lambda item: item["change_pp"],
    )


def main():
    print("\nNW_KYC COHORT PERFORMANCE")
    print("-" * 80)

    for item in analyze_cohorts()[:15]:
        print(
            f"{item['feature']:12} "
            f"{item['value']:10} "
            f"Historical: {item['historical_rate']:.2%}  "
            f"Recent: {item['recent_rate']:.2%}  "
            f"Change: {item['change_pp']:+.2f} pp  "
            f"Recent dials: {item['recent_dials']}"
        )


if __name__ == "__main__":
    main()

