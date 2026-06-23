"""
Experiment C — Single-process internal concurrency sweep (revised methodology).

Same axis as Experiment A (varying concurrency within one process), but with
two fixes:
  1. A warmup request fires before the timed sweep so connection setup cost
     is excluded from measurements.
  2. Requests per level raised to match what we'd need for stable stats.

Model: Qwen/Qwen3.5-4B (same small model as A/B — see Experiment E for the
large-model version that matches the original reporter's setup).

Usage:
    python experiment_c.py
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

CONCURRENCY_LEVELS = [1, 2, 4, 8, 16, 24, 32, 48, 64]
REQUESTS_PER_LEVEL = 32
TRIALS_PER_LEVEL = 1


async def run_level(sampling_client, renderer, params, concurrency: int, n_requests: int):
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
    print("=== Experiment C: single-process concurrency sweep (with warmup) ===")
    print(f"Levels: {CONCURRENCY_LEVELS}, requests/level: {REQUESTS_PER_LEVEL}\n")

    sampling_client, renderer, params = make_sampling_client()

    print("Warming up (1 untimed request)...")
    await sample_one_async(sampling_client, renderer, params, PROMPTS[0])
    print("Warmup done.\n")

    all_results = []
    for concurrency in CONCURRENCY_LEVELS:
        for _ in range(TRIALS_PER_LEVEL):
            lr = await run_level(sampling_client, renderer, params, concurrency, REQUESTS_PER_LEVEL)
            print_level_result("C", lr)
            all_results.append(lr)

    with open("experiment_c_results.csv", "w") as f:
        f.write("concurrency,n_requests,wall_time_s,throughput_rps,p50_latency_s,p95_latency_s,n_errors\n")
        for lr in all_results:
            f.write(
                f"{lr.concurrency},{lr.n_requests},{lr.wall_time_s:.4f},"
                f"{lr.throughput_rps:.4f},{lr.p50_latency_s:.4f},{lr.p95_latency_s:.4f},{lr.n_errors}\n"
            )
    print("\nWrote experiment_c_results.csv")


if __name__ == "__main__":
    asyncio.run(main())
