# Tinker concurrency benchmark — repro for issue #730

Reproduces and localizes the slowdown reported in
[thinking-machines-lab/tinker-cookbook#730](https://github.com/thinking-machines-lab/tinker-cookbook/issues/730):
~3x slower per-job under parallel load (16 concurrent requests/process x 50
processes), plus questions about session caps.

## Methodology

Two experiments isolate **where** the bottleneck lives, before assuming a cause:

- **Experiment A** (`experiment_a.py`) — one process, one `SamplingClient`,
  internal concurrency via `asyncio.gather` swept from 1 to 64. Tests
  whether the bottleneck is contained within a single client/process
  (connection handling, event loop, etc.).

- **Experiment B** (`experiment_b.py`) — many independent OS processes
  (1 to 50), each with its own `SamplingClient`, each making requests
  **one at a time** (no internal concurrency). These processes share
  nothing client-side. Tests whether the bottleneck is server-side
  (account-level session caps, queueing, scheduling contention).

Both sweeps are bracketed around the concurrency level in the original
report (16/process, 50 processes) rather than the SDK's documented
1,000-connection ceiling, since the reported slowdown happens well below
that ceiling and the 1,000 number doesn't explain it.

**How to read the result:**
- A degrades, B doesn't → client-side bottleneck.
- B degrades too → server-side bottleneck (would directly test the
  maintainer's claim that the backend "can handle many thousands of
  concurrent requests easily").

## Setup

```bash
pip install tinker matplotlib --break-system-packages
export TINKER_API_KEY=<your key>
```

## Run

```bash
python experiment_a.py     # writes experiment_a_results.csv
python experiment_b.py     # writes experiment_b_results.csv
python plot_results.py     # writes concurrency_benchmark.png
```

Start with the small default model (`Qwen/Qwen3.5-4B`) and modest
request counts to validate the methodology cheaply before scaling up
request counts, trial counts, or switching to a larger model (e.g. the
Qwen3.5-35B-A3B model flagged in the issue thread as specifically slow).

## Notes / honesty checks

- Each level's wall-clock time and error count are recorded, not just
  latency — a spike in `n_errors` under load (e.g. retries/timeouts)
  would itself be a finding, separate from raw slowdown.
- `TRIALS_PER_LEVEL` in `experiment_a.py` defaults to 1 for cheap
  first-pass iteration. Raise it (e.g. to 3) and report variance across
  trials before treating any single curve as conclusive.
- This does not test the SDK's `pyqwest` vs. plain-httpx transport
  question directly. That's a reasonable follow-up only if Experiment A
  is the one that shows degradation — otherwise it's not the relevant
  layer.
