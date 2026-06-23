"""
Experiment A — Single-process, internal concurrency.

One process, one SamplingClient. Fire an increasing number of CONCURRENT
requests from inside this one process (via asyncio.gather), and measure
how latency/throughput change as concurrency rises.

Narrowed range per the issue report: the original poster used 16 concurrent
requests/process, so we sweep around and past that point, not up toward the
documented 1,000-connection ceiling (that ceiling doesn't explain a slowdown
observed at 16).

If THIS experiment shows degradation, the bottleneck is something contained
within a single process/client (connection handling, event loop, whatever
transport is in play). Compare against Experiment B to know for sure.

Usage:
    python experiment_a.py
"""

import asyncio
import time

from bench_common import (
    PROMPTS,
    make_sampling_client,
    sample_one_async,
    summarize,
    print_level_result,
)

# Concurrency levels to sweep. Bracket the reported failure zone (16/process).
CONCURRENCY_LEVELS = [1, 2, 4, 8, 16, 24, 32, 48, 64]

# Repeat each level this many times (different prompts cycled) for stable stats.
REQUESTS_PER_LEVEL = 32

# How many times to repeat the whole level (different random ordering) for
# basic seed/variance sanity. Keep at 1 first; raise to 3 once methodology
# is confirmed working and you're ready to spend more budget.
TRIALS_PER_LEVEL = 1


async def run_level(sampling_client, renderer, params, concurrency: int, n_requests: int):
    """Fire n_requests requests, but only `concurrency` in flight at once."""
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_sample(prompt_text):
        async with semaphore:
            return await sample_one_async(sampling_client, renderer, params, prompt_text)

    prompts_cycle = [PROMPTS[i % len(PROMPTS)] for i in range(n_requests)]

    start = time.time()
    results = await asyncio.gather(*[bounded_sample(p) for p in prompts_cycle])
    wall_time = time.time() - start

    return summarize(concurrency, results, wall_time)


async def main():
    print(f"=== Experiment A: single-process internal concurrency sweep ===")
    print(f"Levels: {CONCURRENCY_LEVELS}, requests/level: {REQUESTS_PER_LEVEL}\n")

    sampling_client, renderer, params = make_sampling_client()

    all_results = []
    for concurrency in CONCURRENCY_LEVELS:
        for trial in range(TRIALS_PER_LEVEL):
            lr = await run_level(sampling_client, renderer, params, concurrency, REQUESTS_PER_LEVEL)
            print_level_result("A", lr)
            all_results.append(lr)

    # Dump raw rows as CSV for charting later.
    with open("experiment_a_results.csv", "w") as f:
        f.write("concurrency,n_requests,wall_time_s,throughput_rps,p50_latency_s,p95_latency_s,n_errors\n")
        for lr in all_results:
            f.write(
                f"{lr.concurrency},{lr.n_requests},{lr.wall_time_s:.4f},"
                f"{lr.throughput_rps:.4f},{lr.p50_latency_s:.4f},{lr.p95_latency_s:.4f},{lr.n_errors}\n"
            )
    print("\nWrote experiment_a_results.csv")


if __name__ == "__main__":
    asyncio.run(main())
