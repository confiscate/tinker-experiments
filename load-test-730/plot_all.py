"""
Plot all six experiments (A–F) in a 3×2 grid.

Each row is one iteration of the investigation:
  Row 1: A + B — original methodology, small model (Qwen3.5-4B)
  Row 2: C + D — revised methodology (warmup + internal concurrency), small model
  Row 3: E + F — revised methodology, large model (Qwen3.5-35B-A3B-Base)

Left column = single-process concurrency (x = concurrent requests).
Right column = multi-process load (x = total concurrent = processes × 16).

Usage:
    python plot_all.py
"""

import csv
import matplotlib.pyplot as plt


def load_csv(path):
    with open(path) as f:
        return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]


def plot_single_process(ax, rows, label, color_p50, color_p95, x_key="concurrency"):
    x = [r[x_key] for r in rows]
    ax.plot(x, [r["p50_latency_s"] for r in rows], marker="o", color=color_p50, label="p50")
    ax.plot(x, [r["p95_latency_s"] for r in rows], marker="o", color=color_p95, label="p95", linestyle="--")


def plot_multi_process(ax, rows, concurrency_per_process=1):
    x = [r["n_processes"] * concurrency_per_process for r in rows]
    ax.plot(x, [r["p50_latency_s"] for r in rows], marker="o", color="tab:green", label="p50")
    ax.plot(x, [r["p95_latency_s"] for r in rows], marker="o", color="tab:red", label="p95", linestyle="--")


def annotate_slowdown(ax, rows, x_key, threshold_p50=None, threshold_p95=None):
    """Mark the first point where latency exceeds a threshold."""
    for r in rows:
        x = r[x_key]
        if threshold_p50 and r["p50_latency_s"] >= threshold_p50:
            ax.annotate(
                f"⚠ p50={r['p50_latency_s']:.1f}s",
                xy=(x, r["p50_latency_s"]),
                xytext=(x, r["p50_latency_s"] + 1.5),
                arrowprops=dict(arrowstyle="->", color="tab:green"),
                color="tab:green", fontsize=8,
            )
            threshold_p50 = None
        if threshold_p95 and r["p95_latency_s"] >= threshold_p95:
            ax.annotate(
                f"⚠ p95={r['p95_latency_s']:.1f}s",
                xy=(x, r["p95_latency_s"]),
                xytext=(x + 20, r["p95_latency_s"] + 1),
                arrowprops=dict(arrowstyle="->", color="tab:red"),
                color="tab:red", fontsize=8,
            )
            threshold_p95 = None


def main():
    a = load_csv("experiment_a_results.csv")
    b = load_csv("experiment_b_results.csv")
    c = load_csv("experiment_c_results.csv")
    d = load_csv("experiment_d_results.csv")
    e = load_csv("experiment_e_results.csv")
    f = load_csv("experiment_f_results.csv")

    fig, axes = plt.subplots(3, 2, figsize=(14, 14))
    fig.suptitle(
        "Tinker sampling latency — issue #730 investigation (A→F)\n"
        "Left: single-process concurrency  |  Right: multi-process load (x = total concurrent requests)",
        fontsize=12,
    )

    # ── Row 1: A and B (original, small model) ──────────────────────────────
    ax = axes[0][0]
    plot_single_process(ax, a, "A", "tab:blue", "tab:orange")
    ax.set_title("A — single-process, 4B, no warmup (original)")
    ax.set_xlabel("Concurrent requests (1 process)")
    ax.set_ylabel("Latency (s)")
    ax.legend(); ax.grid(alpha=0.3)

    ax = axes[0][1]
    # Exp B: 1 sequential req/process → total concurrent = n_processes × 1
    plot_multi_process(ax, b, concurrency_per_process=1)
    ax.set_title("B — multi-process, 4B, 1 req/process sequential (original)")
    ax.set_xlabel("Total concurrent requests (processes × 1)")
    ax.set_ylabel("Latency (s)")
    ax.legend(); ax.grid(alpha=0.3)

    # ── Row 2: C and D (revised, small model) ───────────────────────────────
    ax = axes[1][0]
    plot_single_process(ax, c, "C", "tab:blue", "tab:orange")
    ax.set_title("C — single-process, 4B, with warmup (revised)")
    ax.set_xlabel("Concurrent requests (1 process)")
    ax.set_ylabel("Latency (s)")
    ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1][1]
    # Exp D: 16 concurrent/process → total = n_processes × 16
    plot_multi_process(ax, d, concurrency_per_process=16)
    ax.set_title("D — multi-process × 16 concurrent/process, 4B, with warmup (revised)")
    ax.set_xlabel("Total concurrent requests (processes × 16)")
    ax.set_ylabel("Latency (s)")
    ax.legend(); ax.grid(alpha=0.3)

    # ── Row 3: E and F (revised, large model) ───────────────────────────────
    ax = axes[2][0]
    plot_single_process(ax, e, "E", "tab:blue", "tab:orange")
    ax.set_title("E — single-process, 35B-A3B, with warmup ⚠️")
    ax.set_xlabel("Concurrent requests (1 process)")
    ax.set_ylabel("Latency (s)")
    ax.legend(); ax.grid(alpha=0.3)

    ax = axes[2][1]
    # Exp F: 16 concurrent/process → total = n_processes × 16
    f_for_plot = [dict(r, n_processes=r["n_processes"]) for r in f]
    plot_multi_process(ax, f, concurrency_per_process=16)
    # Annotate the spike at 24 processes (384 total)
    spike = next(r for r in f if r["n_processes"] == 24)
    ax.annotate(
        f"⚠ p95={spike['p95_latency_s']:.1f}s\n(24 proc × 16 = 384 concurrent)",
        xy=(384, spike["p95_latency_s"]),
        xytext=(280, spike["p95_latency_s"] + 2),
        arrowprops=dict(arrowstyle="->", color="tab:red"),
        color="tab:red", fontsize=8,
    )
    ax.set_title("F — multi-process × 16 concurrent/process, 35B-A3B, with warmup ⚠️")
    ax.set_xlabel("Total concurrent requests (processes × 16)")
    ax.set_ylabel("Latency (s)")
    ax.legend(); ax.grid(alpha=0.3)

    # Shared y-axis scale per row so rows are comparable
    for row_axes in axes:
        ymax = max(ax.get_ylim()[1] for ax in row_axes)
        for ax in row_axes:
            ax.set_ylim(0, ymax)

    fig.tight_layout()
    fig.savefig("concurrency_benchmark_all.png", dpi=150)
    print("Wrote concurrency_benchmark_all.png")


if __name__ == "__main__":
    main()
