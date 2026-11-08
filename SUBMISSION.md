# Outcome-First Agent Loop — Submission

**Name:** Asheel (confirm full name before submitting) · **Date:** 8 November 2026 · **Hours actually spent:** [ENTER HONEST TOTAL] · **Language / storage:** Python 3.11 / SQLite (WAL)

> Evidence status: Public 01 and 02 were graded; Public 03 cold-start and bounded active-load measurements were captured. At the time of this draft, completion of the full Public 03 run and a forced-kill recovery test had **not** been verified. Bracketed items require a measured value or command output before submission. Do not convert unverified tests into claims.

## 0. TL;DR

An autonomous, HTTP-only controller ingests events durably, detects workflow-level KPI drift, proposes governed caller-ID changes, monitors outcomes and requests approved rollback on deterioration. Public 01 improved overall conclusion rate **+3.2% relative** to baseline; Public 02 improved it **+2.8% relative**, while also making **one harmful change** and failing to remediate a bad supervisor prompt. Public 03 ingested **5,537,379 historical events** and completed bounded daytime-load tests. I deliberately did not claim a production-quality causal experiment engine, complete hallucination remediation, or a supervisor UI.

## 1. Assumptions

1. The simulator HTTP API, not its scenario files, is the controller's source of operational truth. Scenario YAML is used only for offline test setup; controller behavior does not inspect simulator internals or hidden truth.
2. Pickup means connected calls / dials. Engagement means concluded conversations / connected calls. The top-level business outcome is concluded leads / uploaded leads. These are not interchangeable.
3. A 1.5 percentage-point drop across a recent three-day window is an initial drift *screen*, not a test of statistical significance. A rollback trigger of at least 300 monitored observations and >2 pp decline is a safety heuristic, not causal proof.
4. Historical lead/call data contains enough stable identifiers to perform retrospective joins for exploratory cohort analysis; incomplete IDs must not silently fabricate a join.
5. A supervisor's live configuration edit is authoritative. Automated work must not silently replace it with a stale proposal.
6. A refused or expired approval is not authorization; an approval is bound to its workflow, proposal, base version and application window.
7. SQLite on one process is acceptable for this assignment's MVP; this is not a statement that one SQLite file is the right multi-node production architecture.
8. The simulator may fail between a remote side effect and the HTTP response, so approval/apply operations require reconciliation rather than blind POST retries.
9. UTC/local timestamps are preserved as supplied by the simulator; date-level grouping uses the date portion of the event timestamp, corresponding to its embedded offset.
10. The actual experiment traffic is allocated by the simulator after an approved configuration change; an unrun proposed variant is not counted as evidence.
11. Reported grade deltas are relative changes against the simulator's no-op baseline, not percentage-point gains.
12. Simulator speed is not production real-time performance; cold historical imports, warm restarts and active dialing must be measured separately.

## 2. Scope decisions

| # | Capability | Status | Why / actual implementation | Work to finish |
|---|---|---|---|---|
| C1 | Scalable idempotent ingestion | **Built, constrained** | HTTP chunk ingestion, SQLite event-ID uniqueness, processed-chunk records, durable checkpointed daily aggregates; >5.5M events ingested on Public 03 | Streaming/bulk-copy pipeline, throughput and peak RSS profiling at 10× |
| C2 | Shared cohort identity | **Partial** | Lead-to-call joins and cohort cuts by city tier, language, age and value | Persist a canonical cohort ID and reuse consistently across detection, experiment and supervisor views |
| C3 | Historical bootstrap | **Built** | Sync historical chunks before day-zero optimization | Bound cold-start SLA and summarize during ingestion |
| C4 | Call-time optimization | **Cut** | Avoid changing business-owned cadence/capacity; schedule personalization lacked robust evaluation | Cohort hourly exploration with explicit policy and adequate samples |
| C5 | Caller-ID health | **Partial** | Governed caller-ID reallocation experiments | Dedicated flagged-DID detection, safe rapid containment and DID-level control chart |
| C6 | Welcome/voice experiments | **Partial** | Read-only Wilson intervals and two-proportion comparison helper; no deployed multi-factor randomized design | Factorial welcome × voice assignment, minimum samples, alpha control and pre-registered stop conditions |
| C7 | Promotion, decay, rollback | **Partial** | Versioned post-change monitoring, governed rollback requests, fixed rollback-on-rollback loop | Cohort-aware guardrails, causally sound comparisons, expiry-aware recovery |
| C8 | Hallucination incident response | **Cut** | No deployed detector → LLM fix → validation → approval → verification loop; **Public 02 missed prompt incident** | Severity threshold, holdout validation and protected prompt remediation |
| C9 | Governance | **Partial** | Durable proposal/approval state, reconciliation on restart, pre-apply intent, approved apply, TTL outcomes | Full policy-aware approval batching, fatigue and robust stale-base re-proposal |
| C10 | Honest impact/dry run | **Partial** | Proposals include a diff/rationale and preflight checks; impact-score heuristics, zero affected-lead estimate | Backtest on historical cohort denominators, calibrated score and actual affected leads |
| C11 | Consolidated supervisor view | **Cut** | Queryable audit exists, no UI | Small read-only queue/experiment/change dashboard |
| C12 | Queryable audit store | **Built** | SQLite `audit_log`, `proposals`, `change_monitoring`, `rollback_requests`, `events` | Retention/access controls, searchable customer-level trace |
| C13 | Crash recovery | **Partial** | Completed controlled restart with same DB and simulator state; forced-kill evidence pending | Kill mid-operation, restart, verify zero duplicate side effects and final completion |
| C14 | Observability | **Partial** | Event progress and governance actions logged, DB-queryable health | Metrics export, decision lag / peak memory and alerting |
| C15 | Fair credit/attention allocation | **Cut** | No LLM/validation credit consumed; conservative proposal generation | Tenant budget scheduler and weighted queues |

**Selection principle.** Prioritize a correctly governed, restartable event-to-decision path and honest evidence over a thin implementation of every requested feature. The Public 02 incident grade demonstrates that conservative scope alone does not provide incident safety: prompt-remediation and guardrail testing are important outstanding work.

## 3. Stakeholders

### 01 — Nikhil Rao, VP Sales

**Accepted:** Communicate understandable improvement numbers, limit excessive approval volume, and make proposals operationally actionable. **Pushed back:** A single blended performance score hides pickup/engagement trade-offs; one lunchtime winner is inadequate evidence; importing a persuasive prompt from another client's demo violates the principle of per-workflow evidence. **Incorrect claims:** Kestrel's auto-apply is **not** blanket permission for every dimension; Northwind KYC auto-apply is **not** enabled under the simulator policy. The policy, not QBR recollection, controls.

**Reply (≤120 words):**

> I can give the summit a verified, per-client view of pickup, engagement and conclusion separately, plus the no-op baseline comparison. I won't combine them into a score that conceals a regression. Changes only ship after sufficient evidence and the workflow's actual approval rules. Kestrel does not authorize unrestricted auto-apply, and Northwind's KYC policy is not overridden by a QBR conversation. I also won't reuse a persuasive prompt across client accounts without validation and approval. We can tell a stronger story: the agent improves when it can support the decision, and stops when it cannot.

### 02 — Meera Iyer, Northwind Life Compliance

**Accepted:** Treat customer-facing script/voice changes as high risk, preserve variant/version evidence, avoid overnight approval floods, and separate operational adjustments from script modifications. **Pushed back:** A 24-hour audit answer down to customer-variant level is a target, but the current local audit is better at workflow/proposal history than fully indexed per-customer explanation. **Policy distinction:** Operational dimensions may have policy-granted latitude, but not unrestricted permission; the controller voluntarily used approval for every applied change in Public 01/02. Script edits require validation evidence.

**Reply (≤120 words):**

> Northwind's customer-facing changes should never be pushed on model opinion alone. The current controller uses governed approval even for caller-ID changes, records the proposed configuration and reason, and keeps an auditable version trail. I will not claim we already satisfy every customer-level IRDAI audit query; that needs a dedicated call-to-variant retrieval path and access-controlled retention. I will schedule approvals around your published hours and validate any script change before requesting permission. The priority is defensible improvement with a reversible audit trail, not maximum change frequency.

### 03 — Kabir Menon, Platform & SRE

**Accepted:** Durable SQLite state, event and proposal idempotency, restart reconciliation, actionable logging; no extra running infrastructure. **Pushed back:** A bounded warm run does not establish a production SLA, and no claim is made that Public 03 ran one simulated day in <10 minutes on the evaluator's specified 4-vCPU/8-GB Linux system. **Known gap:** Forced-kill-at-arbitrary-point demonstration and instrumented peak memory are outstanding. A write-intent before remote apply reduces ambiguity but does not eliminate all distributed transaction problems.

**Reply (≤120 words):**

> I kept the controller to Python and SQLite WAL so the assignment needs no additional persistent service. Incoming events are deduplicated and approval state is reconciled on restart. I measured a 563.62-second initial Public 03 cold tick including historical ingestion, a 0.84-second four-tick restart, and a 15.26-second bounded active-load test. Those are not equivalent to your full-day SLO. Before production I would run forced-kill and 4-vCPU/8-GB tests, export ingestion-lag/credit/decision metrics, and page only on stuck ingestion, unauthorized changes or unresolved severe incidents.

### 04 — Anita Desai, Kestrel Finance Operations Supervisor

**Accepted:** Supervisor edits are authoritative; avoid overwhelming the queue; show recent changes and why; monitor engagement rather than maximizing hallucination suppression at any cost. **Pushed back:** A requested one-screen supervisor UI was cut in favor of an auditable backend. **Mismatch:** A five-dimension bundled request is only valid when the simulator's policy permits the combined change; `approval` rules and fatigue/TTL still apply. **Observed failure:** Public 02 did not remediate the supervisor's bad prompt; a caller-ID rollback did not alter the problem prompt.

**Reply (≤120 words):**

> Your prompt edits must be treated as intentional, not automatically overwritten by an earlier proposal. I kept a versioned audit trail and approval requests rather than making hidden live changes. I haven't built the single screen yet; the next interface would show pending approvals, running variants, today's changes and measured results. We also learned something important in the incident test: a caller-ID rollback cannot repair a harmful prompt, and a statistically weak engagement decline shouldn't trigger a chain of reversals. I'll prioritize specific incident diagnosis and guardrail verification before recommending broader automation.

### 05 — Tara Kulkarni, Head of Product

**Accepted:** Separate pickup and engagement denominators; report unrun experiments as unrun; only change the relevant workflow; provide proposals with a rationale and structured diff. **Pushed back:** Cohorts, per-person time, consolidated view and caller-ID health cannot all be fully production-quality P0 in the time budget. **Incorrect claim:** An expired proposal is not the same legal/state-machine event as a rejected proposal. Expiry may justify a fresh re-proposal with new evidence, but must remain distinct in audit. **Gap:** Impact scores and affected leads are not yet calibrated; no shared persisted cohort ID.

**Reply (≤120 words):**

> I kept pickup and engagement as separate KPIs and limited all changes to the current workflow. Historical joins support exploratory cohorts, but the shared canonical cohort object and supervisor screen are not finished. The current proposal impact score is a heuristic, and affected-lead estimation is incomplete; I will label those honestly rather than rank customer risk on fabricated precision. Expiry remains a distinct state, not a rejection, and fresh requests should recompute evidence. I would prioritize reliable experimentation and caller-ID safety before per-person scheduling or a polished dashboard.

### 06 — Aryamann, CTO

**Accepted:** Outcomes need explainability and governance, wasted credit is a liability, and scaling requires explicit measurement. **Pushed back:** Supporting every requested capability in superficial form would make safety failures more likely. **Incorrect universal assumption:** None required; the CTO correctly warns that other memos can contradict policy. **Observed finding:** A positive aggregate outcome can conceal harmful workflow-level actions and missed incidents.

**Reply (≤120 words):**

> I focused on an auditable controller that runs against the simulator over HTTP and survives normal restarts without rebuilding its event history. Public 01 and 02 produced positive aggregate conclusion-rate changes, but Public 02 also exposed a harmful caller-ID rollback and an unresolved prompt incident. I fixed the rollback loop, retained the failed run as evidence and am documenting the remaining limitations. At scale I measured over 5.5 million events in a cold bootstrap, then reduced repeated daily aggregation to checkpointed summaries. I would fund incident response, statistical guardrails and recovery testing before promising fully autonomous optimization.

## 4. Architecture

```text
Simulator HTTP API (/sim/state, /events/chunks, /workflows, /approvals)
          |
          v
  Chunk sync + event-id dedup  -------> SQLite raw events + processed chunks
          |                                            |
          |                                            v
          |                               Checkpointed daily KPI summaries
          |                                            |
          v                                            v
  Approval reconciliation              Drift / exploratory cohort analytics
          |                                            |
          |                                   Candidate caller-ID allocation
          |                                            |
          +---------------------------> Durable proposal + rationale + diff
                                                |
                                        Approval API (human decides)
                                                |
                                         Pre-apply intent record
                                                |
                                         Version-checked apply
                                                |
                                   Change monitoring / KPI comparison
                                                |
                                    Governed rollback proposal (if triggered)
                                                |
                                         SQLite audit log
```

Each simulator tick syncs newly published chunks, reconciles approvals, evaluates monitoring and rollback signals, periodically runs drift detection and advances by 15 simulated minutes. The SQL store contains raw events, processed chunks, controller identity, proposals, application intents, monitoring snapshots, rollback relations, analytics checkpoint, daily summaries and audit log. On restart the controller uses the existing database, checks simulator identity and event progress, reconciles remote approval state and reuses prior chunk/checkpoint records. The HTTP boundary is the only operational input.

SQLite uses WAL. The backend is one-writer oriented; multi-process production scaling needs an external transactional store or tenant/workflow partitions. Remote apply and local commit are not one atomic transaction: an intent is recorded before application and reconciled afterward. Network ambiguity cannot be solved by simply retrying every POST.

## 5. The learning loop

**Cohorts.** Exploratory lead/call joins group city tier, language, age band and value band. Current thresholds are at least **100 historical observations and 50 recent observations** per subgroup, a pragmatic noise filter rather than power-derived sample size. Cohorts overlap descriptively and do **not** have a persisted canonical cohort ID. Avoid combinatorial fragmentation by withholding suggestions for sparse slices; the primary drift detector operates on workflows.

**Design.** The implemented optimizer primarily proposes a small (~10 percentage-point) caller-ID allocation shift toward an available option after drift. It does **not** currently implement rigorous random welcome × voice factorial tests. Such tests should assign traffic at the lead level, preserve exposure identity, use 2×2 interactions where traffic suffices, and never compare arms that did not run. Reusing an arm across workflows is not evidence of a win on a new client.

**Winner decision.** A separate read-only experiment helper computes Wilson 95% intervals and a two-proportion z-test after **≥200 calls per variant**, with an illustrative p<0.05 threshold. This is **not** integrated into auto-promotion, is not corrected for repeated looks or multiple variants, and therefore has no empirically measured false-winner rate. For production, pre-register primary/guardrail metrics, use a fixed sample horizon or alpha-spending, and control familywise or false-discovery error across variants/cohorts; require non-inferiority on the guardrail.

**Decay/rollback.** After approved apply, configuration snapshots and pre-change rate are persisted, and subsequent calls on the applied version are monitored. A drop of >2 pp after ≥300 observations can request a *governed* rollback; this is an observational heuristic, not causal inference. A verified bug allowed rollback-on-rollback ping-pong; a guard now prevents requesting reversal of a rollback proposal. Public 02's earlier harmful rollback remains in the graded evidence. Rollback requests can expire and leave harm unresolved.

**Call time and caller ID.** Caller-ID allocation is changed only through approved workflow configuration. Per-person call-time optimization was cut; the controller does not modify cadence, dial windows or capacity. There is no fully implemented flagged-DID detector/containment rule, demonstrated by Public 02's continued ~50% allocation to a flagged DID.

**Guardrails.** The current rollback trigger checks observed post-change engagement/pickup by configured primary metric, not a complete, policy-driven independent guardrail. Consequently it can miss regressions in another KPI or cohort; do not report it as guardrail-safe.

## 6. Governance

**Lifecycle:** created → submitting → pending → approved → [intent recorded] → applied → monitored; alternate outcomes include expired/rejected; uncertain submissions require reconciliation, and changed base configurations must be treated as stale rather than overwritten. The prototype persists `proposals`, `apply_intents`, approval decisions, change monitoring and rollback relations. Restart reconciliation discovers pending or already applied actions where possible. A version preflight guards against overwriting supervisor edits. Full stale-base re-proposal and retry scheduling are incomplete.

**Timing.** Approver availability, latency, request TTL and apply windows are enforced by the simulator. Controller-side batching/fatigue scheduling is incomplete: Public 02 produced **five** approval requests, **four approved** and **one expired**, including a `ks_cancel` peak of **three requests per 24 hours**. This did not meet the supervisor's desired maximum of two. The controller conservatively used the approval path for all applied changes: Public 01 had two approved applications, Public 02 four, and zero auto-applied in both scenarios.

**Proposal evidence.** Configuration diffs and preflight state are recorded. `impact_score` is currently heuristic and `affected_leads=0` is an **uncomputed placeholder**, not a defensible estimate. Validation/dry-run material documents policy/config checks, not a scientifically valid prospective lift forecast. Credits used were **0** in both graded runs because LLM remediation and validation runs were not implemented.

**Supervisor edits.** A `config_changed` event with actor `supervisor` is ingested and audited; any pending intervention must recheck version/config. Public 02 demonstrated that passive version awareness alone does not detect or fix a harmful prompt: `ks_cancel` v2 (`P2`) persisted through subsequent caller-ID experiments.

## 7. Incidents

**Current thresholds.** Workflow drift: decrease ≥1.5 pp over latest three days relative to earlier days, with at least three prior daily records. Post-change rollback: >2 pp drop after ≥300 observations. These are heuristics; their false-positive rate has **not** been estimated and may be inflated by seasonality, repeated checking, multiple comparisons and supervisor edits. No dedicated hallucination or DID-flag signal detector is operational. No LLM credits or validation credits were spent, so no evidence-based prompt fix was attempted.

**Public 02 timeline (simulator dates):**

| Time | Observed event | Response / result |
|---|---|---|
| D2 10:00 | `ks_cancel` caller ID flagged | Flagged DID continued receiving ~48.7–50.9% daily call share on D2–D9; no containment |
| D3 11:30 (2027-01-07) | Supervisor changed `ks_cancel` to prompt P2 (v2) | No corrective prompt deployment; grader MTTR = null |
| D5 10:15 (2027-01-09) | Controller applied `ks_cancel` caller-ID v3 | Grader classified beneficial; later observational monitoring flagged 2.01 pp engagement drop |
| D5 15:00 | Supervisor changed `nw_renewal` voice (v3) | Logged external change; no evidence of subsequent unsafe overwrite in grade |
| D5 15:15 | Governed rollback changed `ks_cancel` caller-ID to v4 | Grader classified **harmful**; bad prompt P2 remained |
| Later | Engagement on v4 dropped 5.36 pp on a monitored sample of 308 | Second rollback requested; approval `apr_00005` expired |
| After test | Rollback-on-rollback guard implemented and unit-style tested | Returned `rollback_loop_prevented`; **not included in original Public 02 grade** |

**Next incident policy:** detect DID deterioration and hallucination rates per adequate population, freeze further unrelated changes, estimate severity against control/reference, escalate promptly, request a single targeted policy-authorized remediation and verify the specific incident metric plus pickup/engagement guardrails afterward. Do not infer that a caller-ID rollback repairs an unrelated prompt.

## 8. Scale

**Measured environment:** Windows host with **15.82 GB total RAM** and approximately **4.6 GB free before load startup**. These results are **not** measurements on the assignment's 4-vCPU/8-GB Linux evaluator.

| Measurement | Observed result | Qualification |
|---|---:|---|
| Simulator world/history preparation | 299.1 sec | Simulator startup, not controller compute |
| Public 03 initial controller tick | **563.62 sec** | Historical ingestion of 5,537,379 events across 23 chunks + initial optimization + 0→15 advance; **9m 23.62s** |
| Approx. cold processed events/sec | **9,824/sec** | 5,537,379 / 563.623; includes optimizer/advance, hence not an isolated ingestion throughput measure |
| Raw historical events | **5,537,379** | Includes 4,193,295 calls; 12 workflows |
| SQLite DB after historical import | **~3.28 GiB** | Observed before ongoing simulated traffic |
| Daily summary rows | **84** | 12 workflows × 7 days of historical data |
| Warm `daily_metrics()` call | **0.0061 sec** | Checkpoint caught up; repeated query, not cold summary build |
| Restart bounded 4-tick run | **0.84 sec** | Simulator minute 15→75; quiet period |
| Bounded 40-tick active-load run | **15.26 sec** | Minute 75→675, includes quiet and active ticks; last periods 13,500 events / 15-minute tick |
| Daytime event generation rate | **54,000 events/simulated hour** | 13,500 × 4 in observed consecutive chunks; simulator generation rate, not measured controller throughput |
| Full 5-day Public 03 wall-clock | **[PENDING FINAL RUN RESULT]** | Was launched, completion not yet verified |
| Peak controller RSS | **[NOT MEASURED]** | One sampled worker RSS ~723 MB during ingestion, not a validated peak |
| End-to-end peak decision lag | **[NOT MEASURED]** | Need timestamps from event arrival to action/decision |
| Wall-clock per simulated day | **[NOT MEASURED]** | A bounded 40-tick run spans 10 simulated hours, not one day |

The original daily analytics implementation rescanned raw JSON calls. It was replaced with checkpointed `daily_kpi_summary` aggregation; checkpoint and increments commit in one transaction, avoiding double counts after restart. A warm read scanned just 84 summary rows, but **the 6.1 ms number is not a proven speedup factor** without comparable pre-change timing.

**10× breakpoints:** first likely disk growth and random SQLite I/O, then single-writer contention / expensive joins and governance queue bottlenecks; exact limits remain unmeasured. At 10×, move event transport to a streaming log and bulk partitioned storage, maintain per-(tenant, workflow, day, cohort) summaries incrementally, route each workflow to one ordered decision worker, preserve remote idempotency keys and separate real-time incident pipelines from daily experiments. Use a globally bounded credit/approval scheduler and backpressure based on ingestion lag.

## 9. Reliability

**Demonstrated normal restart:** Controller ran one bounded Public 03 tick 0→15 after cold import, exited with code 0, then was restarted with the **same** `state/public_03.db` and simulator and completed four ticks 15→75 in **0.84 sec**, exit code 0, without reimporting the initial 5,537,379 events. A later 40-tick bounded run completed 75→675 with exit code 0. Analytics checkpoint equals maximum stored event ID `5,537,379` after historical bootstrap; 84 daily summaries count 4,193,295 calls.

**Forced-kill recovery:** **[NOT YET DEMONSTRATED]**. Controlled bounded exits do not prove abrupt process termination. To complete: kill a running controller during ingest or approval, restart with the same DB and SIM_URL, finish the scenario, and compare unique event IDs, approval IDs, apply versions and final state. Save commands/log under `reports/`.

**Idempotency:** event primary key and processed-chunk table prevent replay duplication. Analytics checkpoint and aggregate updates are in one SQLite transaction. Rollback relationship is durable before network submission and prevents repeat rollback proposals; a rollback-of-rollback guard was implemented after observing ping-pong. A persisted apply intent aids uncertain-response reconciliation. No distributed atomic transaction exists across SQLite and simulator HTTP API, so exact-once remote side effects are not universally proven.

**HTTP failure policy:** transient GETs can retry with bounded attempts. Mutating POSTs are not blindly retried after ambiguous transport errors; reconcile via observable approval/config state. On 4xx policy rejection, persist the failure and do not bypass governance. On 5xx/network uncertainty, preserve intent and reconcile before another mutation. Incomplete paths include robust stale-base reproposal and approval-expiry rescheduling.

## 10. Audit & observability

**Example query (run with `CONTROLLER_DB=state/public_02.db`; audited results were observed):**

```sql
SELECT action, workflow_id, details
FROM audit_log
WHERE workflow_id = 'ks_cancel'
   OR (action = 'rollback_action' AND details LIKE '%ks_cancel%')
ORDER BY id DESC
LIMIT 20;
```

**Actual audit excerpts:**

```text
rollback_recommended | ks_cancel | proposal agent-8ee5d2a6ee144f2c, v3, sample 309, drop 2.00556 pp
rollback_proposal_created | ks_cancel | agent-8ee5d2a6ee144f2c -> agent-ed0959b9538d4b0a
approval_submitted | ks_cancel | agent-ed0959b9538d4b0a, approval apr_00004
rollback_recommended | ks_cancel | agent-ed0959b9538d4b0a, v4, sample 308, drop 5.36103 pp
rollback_proposal_created | ks_cancel | agent-ed0959b9538d4b0a -> agent-c115d5579a2f4e1b
approval_submitted | ks_cancel | agent-c115d5579a2f4e1b, approval apr_00005
```

The `events` table supplies authoritative `approval_decided` and `config_changed` observations. In this run, `apr_00004` was approved and applied as v4 at 2027-01-09 15:15 with `actor=controller_approved`; `apr_00005` expired. For a forensic query, join `proposals`, `rollback_requests`, `change_monitoring` and event payloads by proposal ID and workflow. The source store provides evidence, not a finished single-query customer-level trace.

**Would page:** severe sustained hallucination increase, uncontained flagged-DID use, unauthorized/stale apply, event ingestion lag past decision SLA, repeated restart/reconciliation failures. **Would not page:** ordinary drift screens, a proposed change pending during closed approval hours, or a small non-significant KPI wobble. Export credit remaining, approval age, ingestion checkpoint lag, applied changes by tenant and delayed rollbacks as metrics in production; current observability is primarily logs and SQL.

## 11. Results

### Public 01 — `reports/public_01.md`

| workflow | conclusion rate | Δ relative | pickup | Δ relative | engagement | Δ relative | engagement gap captured | hallucinated calls (baseline) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ks_cancel | 0.343 | +3.1% | 0.243 | +1.9% | 0.494 | +0.6% | 0% | 56 (47) |
| nw_kyc | 0.396 | +8.8% | 0.257 | +6.4% | 0.601 | +1.7% | 0% | 26 (21) |
| nw_renewal | 0.421 | +0.4% | 0.266 | +1.1% | 0.544 | -0.4% | 0% | 47 (42) |
| **ALL** | **0.380** | **+3.2%** | **0.254** | **+2.4%** | **0.533** | **+0.6%** | **0%** | **129 (110)** |

**Governance:** two approved/applied changes, one expired approval, zero auto-apply and zero conflicts; **1 beneficial**, **1 neutral**. Improved pickup/conclusions, especially KYC, but **hallucinated calls increased** from 110 baseline to 129 despite aggregate lift. This is a safety regression in absolute event counts, not something to conceal.

### Public 02 — `reports/public_02.md`

| workflow | conclusion rate | Δ relative | pickup | Δ relative | engagement | Δ relative | engagement gap captured | hallucinated calls (baseline) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ks_cancel | 0.247 | -0.4% | 0.184 | +0.3% | 0.475 | -0.2% | 0% | 308 (330) |
| nw_kyc | 0.402 | +7.4% | 0.260 | +7.3% | 0.591 | -0.2% | 0% | 34 (31) |
| nw_renewal | 0.438 | +2.8% | 0.267 | +1.8% | 0.552 | +0.8% | 5% | 61 (55) |
| **ALL** | **0.344** | **+2.8%** | **0.227** | **+2.4%** | **0.532** | **+0.4%** | **3%** | **403 (416)** |

**Governance:** four approved/applied changes, one expired approval, zero auto-apply and zero conflicts; **2 beneficial**, **1 neutral**, **1 harmful**. This run reveals critical weaknesses: the flagged caller ID continued receiving about half of its calls, the harmful supervisor prompt was not corrected (MTTR null), and an observational rollback generated harmful v4. A post-test guard prevents rollbacks from themselves triggering another automatic rollback; it does not retroactively improve these grades.

**Interpretation:** headline positive overall lift came with important workflow/incident failures. The controller's effectiveness on hidden scenarios is not established. Guardrail violations can outweigh commercial lift in regulated settings.

## 12. Trade-offs & rejected alternatives

| Option | Why considered | Why rejected / what instead |
|---|---|---|
| Full per-person scheduling | Potential pickup improvement | Cut: requires robust lead-level evaluation and business coordination |
| Unrestricted auto-apply | Reduces approval latency | Rejected: policy boundaries and risk outweigh throughput; all observed changes approved |
| Always-on LLM prompt repair | Might remediate hallucinations | Cut: finite credits, safety/validation complexity; this caused a real incident gap |
| Broad multi-dimensional factorial experiment | Interaction insight | Only explanatory analysis built; insufficient implementation time for correct correction/stopping |
| In-memory event history | Simple analytics | Rejected: unbounded memory and crash loss; SQLite chunks + summaries |
| Recompute daily KPIs from raw JSON | Easy initial implementation | Replaced with transactional incremental summary after load bottleneck |
| Postgres/Redis deployment | Better scale/distribution | Not required for local MVP; would add operational dependencies |
| Rollback on any metric drop | Fast reaction | Unsafe: confounding and ping-pong observed; added rollback-chain guard, stronger evidence remains needed |
| One blended KPI | Easier summit dashboard | Rejected: masks pickup/engagement tradeoffs |

## 13. Known weaknesses

1. **Missed incidents:** No dedicated flagged-DID containment, hallucination spike diagnosis, LLM suggestion or validation pipeline; Public 02 bad prompt MTTR was null.
2. **Insufficient statistical rigor:** Drift/rollback thresholds are heuristics without measured false-positive rate, seasonality controls, causal attribution, multiple-comparison correction or sequential stopping.
3. **Wrong rollback target:** Public 02 caller-ID rollback did not repair supervisor prompt P2; v4 was classified harmful. Post-test anti-ping-pong guard fixes only the loop, not the root cause.
4. **Incomplete generalization:** Primary KPI mapping names three Public 01 workflows; additional Public 03/hidden IDs may be ignored. Do not claim all 12 are independently optimized simply because all were ingested.
5. **No canonical cohort ID or production UI.** Exploratory joins are not a consistent experiment/supervisor product contract.
6. **Weak proposal estimates:** `affected_leads=0` is a placeholder; impact scores are heuristics. Dry-run is a configuration preflight rather than real uplift validation.
7. **Approval timing:** One expired approval in each graded scenario; Public 02 Kestrel peak was three requests/day, exceeding supervisor preference.
8. **Incomplete recovery proof:** Normal restart verified; arbitrary forced-kill at network mutation and simulator-advance boundary not fully exercised.
9. **Scale evidence gaps:** No validated 4-vCPU/8-GB Linux full-day SLO, end-to-end decision lag, peak memory, or completed 5-day wall clock yet. SQLite database is ~3.28 GiB after historical bootstrap.
10. **Operationalization:** Not multi-worker, no tenant fairness scheduler, no structured metric exporter, no data-retention/privacy policy or alert delivery integration.
11. **Limited testing:** Six simulator tests passed in development; dedicated property/invariant and chaos tests are still needed.

## 14. If this went to production at Formi next month

**Days 1–2: Safety gate.** Disable unsupervised change application by default, review policy per tenant, separate prompt/voice versus caller-ID incident paths, formalize primary/guardrail definitions, and freeze rollbacks on unverified causal signals.

**Days 3–4: Incident response.** Add DID health/population detector, hallucination rate thresholds, permissioned prompt remediation with validation evidence, supervisor notifications, and explicit time-to-fix measurement.

**Days 5–6: Reliability.** Add kill/restart fault injection around chunk commit, approval submission, apply and advance, plus reconciliation tests for ambiguous responses, expired approvals and supervisor version conflicts.

**Days 7–8: Statistical design.** Stable cohort IDs, pre-registered randomized assignments, a fixed evaluation window or alpha spending, minimum sample calculations, family-wise correction and independent guardrail checks. Begin with one dimension per experiment.

**Days 9–10: Scale and observability.** Benchmark one simulated day on 4-vCPU/8-GB Linux with sampled peak RSS, event-to-decision lag, event/sec, disk and approval queue; add metrics and action-only alerts. Migrate to partitioned durable storage if the measured bottleneck warrants it.

**Days 11–12: Supervisor experience.** Build a read-only queue of proposed, running, applied, expired and rolled-back changes with cohort/variant evidence and customer trace retrieval.

**Days 13–14: Guarded rollout.** Canary one low-risk workflow with named human approvals, compare to holdout, review harmful-change rate and incident MTTR daily, define rollback playbook and operational owner before expanding tenant coverage.

---

**Submission finalization checklist:** Replace name/hours placeholders; record completed Public 03 run if available; add an actual forced-kill recovery log or clearly retain the gap; include `reports/public_01.md`, `reports/public_02.md`, measured load report, `run.sh`, and genuine git history. Do not commit simulator run artifacts, local SQLite databases or enormous logs.
