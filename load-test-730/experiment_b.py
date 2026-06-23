"""
Experiment B — Many independent processes, no internal concurrency.

Each process makes requests ONE AT A TIME (sequential), with its own
independent SamplingClient. We vary the NUMBER OF PROCESSES, not the
concurrency within any one of them.

Why this matters: these processes share nothing client-side -- no connection
pool, no event loop, no memory. The only thing they have in common is
hitting the same Tinker account/backend. So:

  - If THIS experiment shows degradation as process count rises, the
    bottleneck can't be a client-side connection pool or event loop issue
    (there's no shared client to exhaust). It points at something
    server-side: an account-level session cap, queueing, or scheduling
    contention -- exactly what the original issue reporter asked about
    ("does tinker backend has any session cap?").
  - If it does NOT degrade, that's consistent with the maintainer's claim
    that "our backend can handle many thousands of concurrent requests
    easily" -- and narrows the problem back to Experiment A's territory.

Narrowed range per the issue report: the original poster used 50 processes
(at 16 concurrent each -- we isolate the process-count axis alone here).

Usage:
    python experiment_b.py
"""

import os
import time
import multiprocessing as mp

from bench_common import RequestResult, summarize, print_level_result
from bench_worker import worker_run

# Sweep process count. Bracket the reported failure zone (50 processes).
PROCESS_COUNT_LEVELS = [1, 2, 4, 8, 16, 24, 32, 50]

# Sequential requests made by EACH process (kept small -- each one is
# already a real network round trip, and we're paying per-process startup
# overhead too).
REQUESTS_PER_PROCESS = 4


def run_level(n_processes: int, n_requests_per_process: int):
    api_key = os.environ["TINKER_API_KEY"]
    start = time.time()
    with mp.Pool(processes=n_processes) as pool:
        args = [(n_requests_per_process, api_key)] * n_processes
        per_process_results = pool.map(worker_run, args)
    wall_time = time.time() - start

    flat_results = []
    for proc_results in per_process_results:
        for latency_s, ok, error in proc_results:
            flat_results.append(RequestResult(latency_s=latency_s, ok=ok, error=error))

    return summarize(n_processes, flat_results, wall_time)


def main():
    print("=== Experiment B: multi-process, no shared client state ===")
    print(f"Process-count levels: {PROCESS_COUNT_LEVELS}, requests/process: {REQUESTS_PER_PROCESS}\n")

    all_results = []
    for n_processes in PROCESS_COUNT_LEVELS:
        lr = run_level(n_processes, REQUESTS_PER_PROCESS)
        print_level_result("B", lr)
        all_results.append(lr)

    with open("experiment_b_results.csv", "w") as f:
        f.write("n_processes,n_requests,wall_time_s,throughput_rps,p50_latency_s,p95_latency_s,n_errors\n")
        for lr in all_results:
            f.write(
                f"{lr.concurrency},{lr.n_requests},{lr.wall_time_s:.4f},"
                f"{lr.throughput_rps:.4f},{lr.p50_latency_s:.4f},{lr.p95_latency_s:.4f},{lr.n_errors}\n"
            )
    print("\nWrote experiment_b_results.csv")


if __name__ == "__main__":
    # 'spawn' is the safest start method across platforms for this kind of
    # workload (avoids surprises from fork-inherited network/auth state).
    mp.set_start_method("spawn", force=True)
    main()
