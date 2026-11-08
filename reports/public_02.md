# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.247 | -0.4% | 0.184 | +0.3% | 0.475 | -0.2% | 0% | 308 (330) |
| nw_kyc | 0.402 | +7.4% | 0.260 | +7.3% | 0.591 | -0.2% | 0% | 34 (31) |
| nw_renewal | 0.438 | +2.8% | 0.267 | +1.8% | 0.552 | +0.8% | 5% | 61 (55) |
| ALL | 0.344 | +2.8% | 0.227 | +2.4% | 0.532 | +0.4% | 3% | 403 (416) |

## Changes applied by the controller

4 applied — beneficial: 2, neutral: 1, harmful: 1

- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.033 → **beneficial**
- nw_renewal v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.013 → **neutral**
- ks_cancel v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.067 → **beneficial**
- ks_cancel v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.067 → **harmful**

## Governance

```
{
  "approval_requests": 5,
  "decisions": {
    "approved": 4,
    "expired": 1
  },
  "rejection_reasons": {},
  "applied_via_approval": 4,
  "auto_applied": 0,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_kyc": 1,
    "nw_renewal": 1,
    "ks_cancel": 3
  }
}
```

## Incidents

```
[
  {
    "type": "did_flagged",
    "workflow": "ks_cancel",
    "at": "D2 10:00",
    "flagged_did_share_by_day": {
      "2": 0.505,
      "3": 0.504,
      "4": 0.497,
      "5": 0.487,
      "6": 0.505,
      "7": 0.494,
      "8": 0.509,
      "9": 0.505
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D3 11:30",
    "mttr_minutes": null,
    "fixed_by": null
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D5 15:00"
  }
]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0