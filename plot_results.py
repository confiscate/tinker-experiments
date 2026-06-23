"""
Plot Experiment A and Experiment B results side by side.

Run this AFTER both experiment_a.py and experiment_b.py have produced
their CSVs.

Usage:
    python plot_results.py
"""

import csv
import matplotlib.pyplot as plt


def load_csv(path):
    rows = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: float(v) for k, v in row.items()})
    return rows


def main():
    a_rows = load_csv("experiment_a_results.csv")
    b_rows = load_csv("experiment_b_results.csv")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # --- Experiment A: single-process internal concurrency ---
    ax = axes[0]
    x = [r["concurrency"] for r in a_rows]
    ax.plot(x, [r["p50_latency_s"] for r in a_rows], marker="o", label="p50 latency")
    ax.plot(x, [r["p95_latency_s"] for r in a_rows], marker="o", label="p95 latency")
    ax.set_xlabel("Concurrent requests (1 process)")
    ax.set_ylabel("Latency (s)")
    ax.set_title("Experiment A: single-process concurrency")
    ax.legend()
    ax.grid(alpha=0.3)

    # --- Experiment B: multi-process, no shared client ---
    ax = axes[1]
    x = [r["n_processes"] for r in b_rows]
    ax.plot(x, [r["p50_latency_s"] for r in b_rows], marker="o", color="tab:green", label="p50 latency")
    ax.plot(x, [r["p95_latency_s"] for r in b_rows], marker="o", color="tab:red", label="p95 latency")
    ax.set_xlabel("Number of independent processes")
    ax.set_ylabel("Latency (s)")
    ax.set_title("Experiment B: multi-process, no shared client")
    ax.legend()
    ax.grid(alpha=0.3)

    fig.suptitle("Tinker sampling latency vs. concurrency (issue #730 repro)")
    fig.tight_layout()
    fig.savefig("concurrency_benchmark.png", dpi=150)
    print("Wrote concurrency_benchmark.png")


if __name__ == "__main__":
    main()
