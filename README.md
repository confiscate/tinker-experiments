# tinker-experiments

A place for tinkering with [Tinker](https://github.com/thinking-machines-lab/tinker).

## Experiments

### [load-test-730/](load-test-730/)

Reproduces the ~3× per-job slowdown reported in
[tinker-cookbook#730](https://github.com/thinking-machines-lab/tinker-cookbook/issues/730)
(large-scale parallel experiments running noticeably slower under load).

**Finding:** The slowdown is real and specific to large models (Qwen3.5-35B-A3B-Base).
Small models (Qwen3.5-4B) show no degradation up to 800 concurrent requests.
Root cause is backend GPU compute contention — the large model is near capacity
even under light load, so concurrent sessions queue and inflate tail latency.
The worst degradation (p95 = 21.9s, ~10× the small-model baseline) occurs at
around 384 total concurrent requests (24 processes × 16 concurrent each).

See [load-test-730/README.md](load-test-730/README.md) for full methodology,
results, and reproduction steps.
