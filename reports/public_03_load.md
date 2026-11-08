# Public 03 load benchmark

## Environment and scenario

- Scenario: `public_03_load`, 12 workflows, 5 simulated days (7,200 simulated minutes); seven days of historical data.
- Host: Windows with Python 3.11, SQLite-backed controller. The machine had 15.82 GiB total physical RAM and approximately 4.62 GiB available before startup. This is **not** the required 4-vCPU/8-GiB Linux benchmark environment.
- The scenario was driven through the simulator HTTP API; the controller persisted events, progress, and audit records in SQLite.

## Measured runs

| Run | Scope | Measured wall clock | Outcome |
| --- | --- | ---: | --- |
| Simulator initialization | Generate history and start HTTP server | 299.1 s | Server ready on port 8702; **not** controller time |
| Cold controller smoke test | Ingest all historical events and advance minute 0 -> 15 | 563.62 s | Exit code 0; 1 tick |
| Analytics summary verification | Read 84 cached workflow-day summary rows after backfill | 0.0061 s | Checkpoint matches max stored event ID |
| Warm controller restart | Four ticks, minute 15 -> 75 | 0.84 s | Exit code 0 |
| Daytime activity sample | Forty ticks, minute 75 -> 675 | 15.26 s | Exit code 0; observed batches of 13,500 events per 15-minute interval |
| Full-run continuation | Minute 675 -> 7200 (435 ticks) | 287.1 s | Exit code 0; simulator reports `Finished: True` |

**Important comparability note:** The initial smoke test preceded the persistent analytics summary change. The later restart and continuation reused pre-ingested data and persistent summaries. These timings are **not** independent full-run measurements or a controlled before/after benchmark.

## Event volume and throughput

- Initial historical ingestion logged **5,537,379 events in 23 chunks**. The 563.62-second smoke test includes other work as well. Therefore **9,824 events/second** (= 5,537,379 / 563.623) is a *lower-bound average over that full cold-start interval*, **not** a separately instrumented ingestion-only throughput figure.
- Historical events included **4,193,295 call records**, summarized into **84 workflow-day rows** at the time of verification.
- During daytime activity, the controller logged consecutive batches of **13,500 new events per 15-minute tick**. This corresponds to **54,000 generated events per simulated hour** for the observed intervals; it does not measure wall-clock ingestion throughput in isolation.
- The initial raw-event SQLite database reached approximately **3.28 GiB** after historical ingestion.
- The 435-tick continuation averaged approximately **0.66 seconds per tick** over mixed daytime and quiet periods (287.1 / 435). It covered 4.53 simulated days, so its average was approximately **63.4 seconds per simulated day**. This is not a measured maximum daily latency.

## Reliability observations

- Controller resumed from minute 15, 75, and 675, without repeating historical ingestion in the visible restart logs.
- Completion: `[STATE] Minute: 7200/7200 | Finished: True` and `[COMPLETE] Simulation finished.`
- No observed exception or nonzero exit in the reported Public 03 bounded/continuation runs.
- These are controlled restart observations, **not** an abrupt-kill recovery demonstration.

## Not measured and important limits

- **Peak resident memory:** not measured with a continuous sampler; observed snapshot process sizes are not a defensible peak.
- **Decision lag under peak load:** not separately instrumented. The full-run mean includes all ticks and cannot be used as a peak latency bound.
- **4-vCPU / 8-GiB Linux performance:** not tested; Windows host total RAM was ~15.82 GiB.
- **A complete 5-day wall-clock total from cold start:** not captured as one continuous measurement. Timed stages can be added as partial observations, but simulator startup and one-time backfill must be labeled separately.
- **Optimization coverage:** drift primary-metric mapping is hardcoded for three named workflows; other Public 03 workflow IDs are currently skipped by that decision policy. Completing the load scenario proves execution, not broad optimization effectiveness.
- **Storage pressure:** raw JSON per event makes the event store large; at 10x load, I/O, disk capacity, and historical backfill become significant bottlenecks.

## Scaling design for a future deployment

Partition ingestion and decision work by tenant/workflow; use durable source offsets, backpressure, and compact incremental KPI aggregates. Keep event history in a partitioned, retention-managed event store, and move workflow decisions to independent workers. Use Postgres for durable metadata, a queue or stream for event distribution, and explicit per-tenant governance budgets. Instrument ingestion lag, stage wall times, RSS/peak memory, SQLite/DB growth, approvals pending, API errors, and credits before claiming an SRE-grade SLA.
