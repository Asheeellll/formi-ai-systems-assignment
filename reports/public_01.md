# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.343 | +3.1% | 0.243 | +1.9% | 0.494 | +0.6% | 0% | 56 (47) |
| nw_kyc | 0.396 | +8.8% | 0.257 | +6.4% | 0.601 | +1.7% | 0% | 26 (21) |
| nw_renewal | 0.421 | +0.4% | 0.266 | +1.1% | 0.544 | -0.4% | 0% | 47 (42) |
| ALL | 0.380 | +3.2% | 0.254 | +2.4% | 0.533 | +0.6% | 0% | 129 (110) |

## Changes applied by the controller

2 applied — beneficial: 1, neutral: 1

- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.033 → **beneficial**
- nw_renewal v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.015 → **neutral**

## Governance

```
{
  "approval_requests": 3,
  "decisions": {
    "approved": 2,
    "expired": 1
  },
  "rejection_reasons": {},
  "applied_via_approval": 2,
  "auto_applied": 0,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_kyc": 1,
    "nw_renewal": 1
  }
}
```

## Incidents

```
[]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0