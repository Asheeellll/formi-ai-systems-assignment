
from collections import defaultdict

from controller.analytics import daily_metrics


PRIMARY_METRICS = {
    "nw_renewal": "engagement_rate",
    "nw_kyc": "pickup_rate",
    "ks_cancel": "engagement_rate",
}


def calculate_rates(rows):
    dials = sum(row["dials"] for row in rows)
    connected = sum(row["connected"] for row in rows)
    engaged = sum(row["engaged"] for row in rows)

    return {
        "pickup_rate": connected / dials if dials else 0.0,
        "engagement_rate": (
            engaged / connected if connected else 0.0
        ),
        "dials": dials,
        "connected": connected,
    }


def detect_drift(threshold_pp=1.5, recent_days=3):
    """
    Compare recent performance against earlier historical data.

    threshold_pp is an initial screening threshold,
    not a statistical significance test.
    """
    grouped = defaultdict(list)

    for row in daily_metrics():
        grouped[row["workflow_id"]].append(row)

    findings = []

    for workflow_id, days in sorted(grouped.items()):
        if len(days) < recent_days + 3:
            continue

        historical = calculate_rates(days[:-recent_days])
        recent = calculate_rates(days[-recent_days:])

        primary_metric = PRIMARY_METRICS.get(workflow_id)

        if primary_metric is None:
            continue

        change_pp = (
            recent[primary_metric] - historical[primary_metric]
        ) * 100

        findings.append({
            "workflow_id": workflow_id,
            "primary_metric": primary_metric,
            "historical_rate": historical[primary_metric],
            "recent_rate": recent[primary_metric],
            "change_pp": change_pp,
            "drift_detected": change_pp <= -threshold_pp,
            "historical_dials": historical["dials"],
            "recent_dials": recent["dials"],
            "recent_days": recent_days,
        })

    return findings


def main():
    print("\nDRIFT DETECTION REPORT")
    print("-" * 72)

    for finding in detect_drift():
        status = (
            "DRIFT DETECTED"
            if finding["drift_detected"]
            else "NO DRIFT ALERT"
        )

        print(
            f"\nWorkflow: {finding['workflow_id']}"
            f"\nPrimary KPI: {finding['primary_metric']}"
            f"\nHistorical: {finding['historical_rate']:.2%}"
            f"\nRecent: {finding['recent_rate']:.2%}"
            f"\nChange: {finding['change_pp']:+.2f} pp"
            f"\nStatus: {status}"
        )


if __name__ == "__main__":
    main()
