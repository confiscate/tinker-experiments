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


def total_concurrent(rows, concurrency_per_process):
    """Convert rows to (x, p50, p95) using total concurrent requests as x-axis."""
    key = "concurrency" if "concurrency" in rows[0] else "n_processes"
    return (
        [r[key] * concurrency_per_process for r in rows],
        [r["p50_latency_s"] for r in rows],
        [r["p95_latency_s"] for r in rows],
    )


def save_plot(lines, metric, filename, title):
    """
    lines: list of (rows, concurrency_per_process, label, color)
    metric: "p50_latency_s" or "p95_latency_s"
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    for rows, cpp, label, color in lines:
        x, p50, p95 = total_concurrent(rows, cpp)
        y = p50 if metric == "p50_latency_s" else p95
        ax.plot(x, y, marker="o", label=label, color=color)
    ax.set_title(title)
    ax.set_xlabel("Total concurrent requests")
    ax.set_ylabel("Latency (s)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_ylim(0)
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
    print(f"Wrote {filename}")


def main():
    c = load_csv("experiment_c_results.csv")
    d = load_csv("experiment_d_results.csv")
    e = load_csv("experiment_e_results.csv")
    f = load_csv("experiment_f_results.csv")

    plots = [
        # (lines, metric, filename, title)
        (
            [(c, 1, "C — 4B, 1 process", "tab:green"),
             (e, 1, "E — 35B, 1 process", "tab:purple")],
            "p50_latency_s", "plot_ce_p50.png",
            "C vs E — single-process concurrency, p50 latency",
        ),
        (
            [(c, 1, "C — 4B, 1 process", "tab:green"),
             (e, 1, "E — 35B, 1 process", "tab:purple")],
            "p95_latency_s", "plot_ce_p95.png",
            "C vs E — single-process concurrency, p95 latency",
        ),
        (
            [(d, 16, "D — 4B, N processes × 16", "tab:red"),
             (f, 16, "F — 35B, N processes × 16", "tab:brown")],
            "p50_latency_s", "plot_df_p50.png",
            "D vs F — multi-process × 16 concurrent/process, p50 latency",
        ),
        (
            [(d, 16, "D — 4B, N processes × 16", "tab:red"),
             (f, 16, "F — 35B, N processes × 16", "tab:brown")],
            "p95_latency_s", "plot_df_p95.png",
            "D vs F — multi-process × 16 concurrent/process, p95 latency",
        ),
        (
            [(e, 1,  "E — 35B, 1 process", "tab:purple"),
             (f, 16, "F — 35B, N processes × 16", "tab:brown")],
            "p50_latency_s", "plot_ef_p50.png",
            "E vs F — 35B model, single-process vs multi-process, p50 latency",
        ),
        (
            [(e, 1,  "E — 35B, 1 process", "tab:purple"),
             (f, 16, "F — 35B, N processes × 16", "tab:brown")],
            "p95_latency_s", "plot_ef_p95.png",
            "E vs F — 35B model, single-process vs multi-process, p95 latency",
        ),
    ]

    for lines, metric, filename, title in plots:
        save_plot(lines, metric, filename, title)

    # ── EF p50: annotate slowdown ratios from E concurrency=1 ───────────────
    e_baseline_x = 1   # concurrency=1, 1 process → total concurrent = 1
    e_baseline_p50 = next(r["p50_latency_s"] for r in e if r["concurrency"] == 1)

    f_50proc  = next(r for r in f if r["n_processes"] == 50)
    f_24proc  = next(r for r in f if r["n_processes"] == 24)
    f_50_x, f_50_p50 = f_50proc["n_processes"] * 16, f_50proc["p50_latency_s"]
    f_24_x, f_24_p50 = f_24proc["n_processes"] * 16, f_24proc["p50_latency_s"]

    fig, ax = plt.subplots(figsize=(9, 6))
    xe, p50e, p95e = total_concurrent(e, 1)
    xf, p50f, p95f = total_concurrent(f, 16)
    ax.plot(xe, p50e, marker="o", label="E — 35B, 1 process", color="tab:purple")
    ax.plot(xf, p50f, marker="o", label="F — 35B, N processes × 16", color="tab:brown")

    for f_x, f_p50 in [(f_24_x, f_24_p50), (f_50_x, f_50_p50)]:
        ratio = f_p50 / e_baseline_p50
        # Horizontal dashed line from baseline up to the F point's height
        ax.annotate(
            "",
            xy=(f_x, f_p50),
            xytext=(e_baseline_x, f_p50),
            arrowprops=dict(arrowstyle="-", linestyle="dashed", color="gray"),
        )
        # Vertical line from E baseline to F p50 height at F's x
        ax.annotate(
            "",
            xy=(f_x, f_p50),
            xytext=(f_x, e_baseline_p50),
            arrowprops=dict(arrowstyle="<->", color="black"),
        )
        # Label the ratio
        ax.text(
            f_x + 15, (e_baseline_p50 + f_p50) / 2,
            f"{ratio:.2f}×",
            va="center", fontsize=10, fontweight="bold", color="black",
        )

    # Horizontal baseline reference line
    ax.axhline(e_baseline_p50, color="tab:purple", linestyle=":", linewidth=1, alpha=0.6)
    ax.text(5, e_baseline_p50 + 0.1, f"E baseline (concurrency=1): {e_baseline_p50:.2f}s",
            fontsize=8, color="tab:purple")

    ax.set_title("E vs F — 35B model, p50 latency with slowdown ratios")
    ax.set_xlabel("Total concurrent requests")
    ax.set_ylabel("Latency (s)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_ylim(0)
    fig.tight_layout()
    fig.savefig("plot_ef_p50.png", dpi=150)
    plt.close(fig)
    print("Rewrote plot_ef_p50.png")

    # ── EF p95: annotate slowdown ratios from E concurrency=1 ───────────────
    e_baseline_p95 = next(r["p95_latency_s"] for r in e if r["concurrency"] == 1)
    f_50_p95 = f_50proc["p95_latency_s"]
    f_24_p95 = f_24proc["p95_latency_s"]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(xe, p95e, marker="o", label="E — 35B, 1 process", color="tab:purple")
    ax.plot(xf, p95f, marker="o", label="F — 35B, N processes × 16", color="tab:brown")

    for f_x, f_p95 in [(f_24_x, f_24_p95), (f_50_x, f_50_p95)]:
        ratio = f_p95 / e_baseline_p95
        ax.annotate(
            "",
            xy=(f_x, f_p95),
            xytext=(e_baseline_x, f_p95),
            arrowprops=dict(arrowstyle="-", linestyle="dashed", color="gray"),
        )
        ax.annotate(
            "",
            xy=(f_x, f_p95),
            xytext=(f_x, e_baseline_p95),
            arrowprops=dict(arrowstyle="<->", color="black"),
        )
        ax.text(
            f_x + 15, (e_baseline_p95 + f_p95) / 2,
            f"{ratio:.2f}×",
            va="center", fontsize=10, fontweight="bold", color="black",
        )

    ax.axhline(e_baseline_p95, color="tab:purple", linestyle=":", linewidth=1, alpha=0.6)
    ax.text(5, e_baseline_p95 + 0.2, f"E baseline (concurrency=1): {e_baseline_p95:.2f}s",
            fontsize=8, color="tab:purple")

    ax.set_title("E vs F — 35B model, p95 latency with slowdown ratios")
    ax.set_xlabel("Total concurrent requests")
    ax.set_ylabel("Latency (s)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_ylim(0)
    fig.tight_layout()
    fig.savefig("plot_ef_p95.png", dpi=150)
    plt.close(fig)
    print("Rewrote plot_ef_p95.png")


if __name__ == "__main__":
    main()
