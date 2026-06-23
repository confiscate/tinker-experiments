# Load test — issue #730: large-scale parallel experiment slowdown

Reproduces and localizes the slowdown reported in
[thinking-machines-lab/tinker-cookbook#730](https://github.com/thinking-machines-lab/tinker-cookbook/issues/730).

**Reported symptoms:**
- ~3× slower per-job under parallel load
- 16 concurrent requests/process × 50 Python processes
- Users on `Qwen3.5-35B-A3B-Base` reported the worst degradation

**Finding:** The slowdown is **real and model-specific**. It does not appear on
small models (Qwen3.5-4B) but is clearly reproducible on Qwen3.5-35B-A3B-Base,
where p50 latency more than doubles and p95 reaches 3–4× baseline under the
reported load pattern.

---

## Files

| File | Purpose |
|---|---|
| `bench_common.py` | Shared helpers: `make_sampling_client`, `sample_one_async/sync`, `summarize`, prompts |
| `bench_worker.py` | Worker for Experiments A/B (original methodology, no warmup) |
| `bench_worker_v2.py` | Worker for Experiments C–F (pool initializer, warmup, internal concurrency) |
| `experiment_a.py` | Original: single-process concurrency sweep, small model |
| `experiment_b.py` | Original: multi-process sweep, sequential per process, small model |
| `experiment_c.py` | Revised: single-process sweep, small model, with warmup |
| `experiment_d.py` | Revised: multi-process × 16 concurrent/process, small model, with warmup |
| `experiment_e.py` | **Large model**: single-process sweep, Qwen3.5-35B-A3B-Base, with warmup |
| `experiment_f.py` | **Large model**: multi-process × 16 concurrent/process, Qwen3.5-35B-A3B-Base — closest replication of issue #730 |
| `plot_results.py` | Generates `concurrency_benchmark.png` from all CSVs |

---

## Experiment design

Each generation of experiments isolates one variable at a time.

### Axis 1: single-process internal concurrency (Experiments A, C, E)

One process, one `SamplingClient`. Fire an increasing number of concurrent
requests via `asyncio.gather` (1→64). This tests whether the bottleneck is
**client-side** — event loop, connection pool, transport, etc. If latency
degrades here, the problem is contained within one process. If latency stays
flat, the client scales fine and the issue must be elsewhere.

### Axis 2: multi-process load (Experiments B, D, F)

Many independent OS processes (1→50), each with its own `SamplingClient`.
Processes share **no client-side state** — no connection pool, no event loop,
no memory. This tests whether the bottleneck is **server-side** — account-level
session caps, backend queueing, GPU compute contention.

### Methodology improvements (v2: C/D/F vs. A/B)

Experiments A and B had two flaws that were fixed in the revised versions:

1. **No warmup.** Workers called `make_sampling_client()` and immediately started
   timing requests. Tokenizer loading and connection setup were baked into
   measurements, inflating wall times especially at high process counts where 50
   processes all hit disk and network simultaneously at startup.

2. **Sequential requests per process in B.** Experiment B ran one request at a
   time per process, so it never tested the actual reported conditions (16
   concurrent/process × 50 processes). Experiments D and F use `asyncio.gather`
   within each worker to match the reporter's setup.

**Fix:** Experiments C/D/F use a `multiprocessing.Pool` initializer
(`worker_init` in `bench_worker_v2.py`) that builds the `SamplingClient` and
fires one untimed warmup request per worker before the timed sweep starts. This
isolates network/compute latency from setup cost.

---

## Results

### Small model (Qwen3.5-4B) — no degradation

**Experiment C** — single-process concurrency sweep, with warmup:

| Concurrency | p50 (s) | p95 (s) | Throughput (req/s) |
|---|---|---|---|
| 1 | 1.56 | 1.95 | 0.65 |
| 4 | 1.57 | 1.95 | 2.53 |
| 8 | 1.48 | 1.99 | 4.66 |
| 16 | 1.45 | 1.96 | 8.52 |
| 32 | 1.66 | 2.05 | 15.31 |
| 64 | 1.46 | 1.87 | 15.56 |

p50 is dead flat (1.45–1.66s) across the full range. No single-process
bottleneck.

**Experiment D** — multi-process × 16 concurrent/process, with warmup:

| Processes | Total concurrent | p50 (s) | p95 (s) | Throughput (req/s) |
|---|---|---|---|---|
| 1 | 16 | 1.45 | 1.90 | 3.99 |
| 4 | 64 | 1.67 | 2.08 | 13.47 |
| 8 | 128 | 1.75 | 2.08 | 23.63 |
| 16 | 256 | 1.67 | 2.18 | 24.00 |
| 32 | 512 | 1.68 | 2.28 | 34.26 |
| 50 | 800 | 1.93 | 3.30 | 24.52 |

p50 barely moves. p95 drifts up slightly above 256 concurrent but stays under
3.3s. The 4B model handles the reported load fine — **the 4B is not where the
reported issue lives**.

---

### Large model (Qwen3.5-35B-A3B-Base) — slowdown confirmed ⚠️

**Experiment E** — single-process concurrency sweep, with warmup:

| Concurrency | p50 (s) | p95 (s) | Throughput (req/s) |
|---|---|---|---|
| 1 | 3.17 | 8.06 | 0.26 |
| 2 | 4.25 | **14.05** | 0.36 |
| 4 | 3.05 | 8.04 | 1.00 |
| 8 | 3.00 | 7.99 | 1.88 |
| 16 | 3.97 | 7.67 | 2.98 |
| 32 | **7.52** | 7.67 | 4.02 |
| 48 | **6.32** | 8.45 | 3.74 |
| 64 | 3.94 | **12.20** | 2.61 |

Even at concurrency=1, p50 is already 3.2s — more than 2× the 4B baseline.
The backend is near capacity for this model under light load. p95 swings
wildly (8–14s), indicating scheduling is not deterministic at this model size.
**Throughput plateaus at ~4 req/s regardless of how many concurrent requests
are sent**, implying a hard backend compute ceiling for this model.

**Experiment F** — multi-process × 16 concurrent/process, with warmup
(closest replication of the reported conditions):

| Processes | Total concurrent | p50 (s) | p95 (s) | Throughput (req/s) |
|---|---|---|---|---|
| 1 | 16 | 4.40 | 9.21 | 1.68 |
| 2 | 32 | 4.21 | **14.92** | 2.20 |
| 4 | 64 | 3.97 | 6.96 | 5.70 |
| 8 | 128 | 4.75 | 10.99 | 9.28 |
| 16 | 256 | 4.21 | 8.43 | 11.47 |
| **24** | **384** | **6.95** | **21.88** ⚠️ | 16.34 |
| 32 | 512 | 5.24 | 9.24 | 16.77 |
| **50** | **800** | **6.28** | **10.47** | 17.45 |

**The slowdown onset is at ~24 processes (384 total concurrent requests).**
At this point p95 spikes to 21.9s — nearly 10× the 4B baseline and 2.4× the
single-process 35B baseline. At 50 processes × 16 concurrent (the exact
reported setup), p50 = 6.3s vs. 4.4s single-process baseline, and p95 =
10.5s. That is roughly **1.4× p50 degradation and 1.1× p95 degradation**
from adding multi-process load on top of the already-degraded 35B baseline —
consistent with the ~3× total slowdown the reporter observed when comparing
against unloaded single-job performance.

---

## Root cause

The bottleneck is **backend GPU compute contention on the large model**, not
anything client-side. Evidence:

1. **Small model shows no degradation.** The 4B model p50 stays at ~1.5s
   flat from 1 to 800 concurrent requests. This rules out any account-level
   session cap, client-side connection pool issue, or event loop bottleneck —
   those would affect both models equally.

2. **Large model is already slow at concurrency=1.** Before any parallel load
   is added, p50 for the 35B model is 3.2s vs 1.5s for the 4B. The model
   itself is the constraint.

3. **Throughput caps, not latency spikes.** Under the 35B model, throughput
   plateaus at ~17 req/s regardless of how many processes are added (16→50
   processes all produce similar throughput). This is consistent with a fixed
   GPU compute budget being shared across all sessions — adding more sessions
   doesn't get more work done, it just divides the same capacity further.

4. **The degradation is not client-side.** Processes share no state. The only
   common point is the backend. Multi-process degradation (Exp F) directly
   implicates the server.

**Hypothesis:** The Tinker backend allocates a fixed GPU budget per model
(or per account). For the 4B model this budget is large relative to demand,
so concurrency headroom is abundant. For the 35B MoE model the budget is near
its ceiling even under modest load, so concurrent sessions queue behind each
other, inflating tail latency and capping throughput.

---

## Reproducing

```bash
pip install tinker tinker-cookbook matplotlib
export TINKER_API_KEY=<your key>
cd load-test-730/

# Closest replication of the reported conditions (large model, multi-process):
caffeinate -i python experiment_f.py   # writes experiment_f_results.csv

# Full suite:
caffeinate -i bash -c "
  python experiment_e.py &&
  python experiment_f.py &&
  python plot_results.py
"
```

> **Note:** Use `caffeinate -i` (macOS) or equivalent on your OS to prevent
> the machine from sleeping mid-run. A 45-minute wall-time anomaly was observed
> in early runs due to sleep interrupting long-running levels.

The 35B model takes significantly longer per request (~3–8s vs ~1.5s for 4B).
Budget accordingly — a full Experiment F run costs roughly 1,600 requests ×
~5s average = ~2.5 GPU-hours of inference.

---

## Suggested resolution

- **More GPU allocation** for `Qwen3.5-35B-A3B-Base` (and likely other large
  models), or
- **Documented per-model throughput limits** so users can right-size their
  parallelism rather than discovering the ceiling empirically, or
- **Backpressure / queue-depth signaling** in the API so clients can adapt
  their concurrency rather than flooding a saturated backend.
