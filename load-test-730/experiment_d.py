"""
Experiment D — Multi-process with internal concurrency (revised methodology).

Same axis as Experiment B (varying process count), but with three fixes over B:
  1. Workers are pre-initialized via a Pool initializer — each process builds
     its SamplingClient and fires one warmup request before timed work begins,
     so startup/tokenizer-load cost is excluded from measurements.
  2. Each worker fires 16 concurrent requests via asyncio.gather, matching the
     original reporter's setup (16 concurrent/process × N processes).
  3. More requests per process (32) for stable latency stats.

Model: Qwen/Qwen3.5-4B (same small model as A/B — see Experiment F for the
large-model version that matches the original reporter's setup).

Usage:
    python experiment_d.py
"""

import os
import time
import multiprocessing as mp

from bench_common import RequestResult, summarize, print_level_result
from bench_worker_v2 import worker_init, worker_run

PROCESS_COUNT_LEVELS = [1, 2, 4, 8, 16, 24, 32, 50]
CONCURRENCY_PER_PROCESS = 16
REQUESTS_PER_PROCESS = 32

BASE_MODEL = "Qwen/Qwen3.5-4B"
RENDERER_NAME = "qwen3_5"


def run_level(n_processes: int, api_key: str):
    with mp.Pool(
        processes=n_processes,
        initializer=worker_init,
        initargs=(api_key, BASE_MODEL, RENDERER_NAME),
    ) as pool:
        args = [(REQUESTS_PER_PROCESS, CONCURRENCY_PER_PROCESS)] * n_processes
        start = time.time()
        per_process_results = pool.map(worker_run, args)
    wall_time = time.time() - start

    flat = [
        RequestResult(latency_s=lat, ok=ok, error=err)
        for proc in per_process_results
        for lat, ok, err in proc
    ]
    return summarize(n_processes, flat, wall_time)


def main():
    api_key = os.environ["TINKER_API_KEY"]
    print("=== Experiment D: multi-process + internal concurrency (small model, with warmup) ===")
    print(
        f"Process-count levels: {PROCESS_COUNT_LEVELS}, "
        f"{CONCURRENCY_PER_PROCESS} concurrent req/process, "
        f"{REQUESTS_PER_PROCESS} req/process\n"
    )
    print("(Workers warm up before timed sweep — this may take a moment at high process counts)\n")

    all_results = []
    for n_processes in PROCESS_COUNT_LEVELS:
        lr = run_level(n_processes, api_key)
        print_level_result("D", lr)
        all_results.append(lr)

    with open("experiment_d_results.csv", "w") as f:
        f.write("n_processes,n_requests,wall_time_s,throughput_rps,p50_latency_s,p95_latency_s,n_errors\n")
        for lr in all_results:
            f.write(
                f"{lr.concurrency},{lr.n_requests},{lr.wall_time_s:.4f},"
                f"{lr.throughput_rps:.4f},{lr.p50_latency_s:.4f},{lr.p95_latency_s:.4f},{lr.n_errors}\n"
            )
    print("\nWrote experiment_d_results.csv")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
