"""
Experiment F — Multi-process with internal concurrency, large model.

Identical methodology to Experiment D, but using Qwen/Qwen3.5-35B-A3B-Base —
the model the original reporter was running when they observed ~3x slowdown.
This is the closest replication of the original reported conditions:
  16 concurrent requests/process × up to 50 processes.

Usage:
    python experiment_f.py
"""

import os
import time
import multiprocessing as mp

from bench_common import RequestResult, summarize, print_level_result
from bench_worker_v2 import worker_init, worker_run

PROCESS_COUNT_LEVELS = [1, 2, 4, 8, 16, 24, 32, 50]
CONCURRENCY_PER_PROCESS = 16
REQUESTS_PER_PROCESS = 32

BASE_MODEL = "Qwen/Qwen3.5-35B-A3B-Base"
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
    print("=== Experiment F: multi-process + internal concurrency (large model, with warmup) ===")
    print(f"Model: {BASE_MODEL}")
    print(
        f"Process-count levels: {PROCESS_COUNT_LEVELS}, "
        f"{CONCURRENCY_PER_PROCESS} concurrent req/process, "
        f"{REQUESTS_PER_PROCESS} req/process\n"
    )
    print("(Workers warm up before timed sweep — this may take a moment at high process counts)\n")

    all_results = []
    for n_processes in PROCESS_COUNT_LEVELS:
        lr = run_level(n_processes, api_key)
        print_level_result("F", lr)
        all_results.append(lr)

    with open("experiment_f_results.csv", "w") as f:
        f.write("n_processes,n_requests,wall_time_s,throughput_rps,p50_latency_s,p95_latency_s,n_errors\n")
        for lr in all_results:
            f.write(
                f"{lr.concurrency},{lr.n_requests},{lr.wall_time_s:.4f},"
                f"{lr.throughput_rps:.4f},{lr.p50_latency_s:.4f},{lr.p95_latency_s:.4f},{lr.n_errors}\n"
            )
    print("\nWrote experiment_f_results.csv")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
