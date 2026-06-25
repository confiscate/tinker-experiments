"""Standalone CLI entry point for tinker-billing.

Mirrors the `tinker billing` subcommands exactly, so users get the same
experience whether they use the merged SDK command or this package.
"""

import json
import sys

import click

from ._estimator import PRICING, CostEstimate, estimate_cost


def _print_table(title: str, headers: list, rows: list) -> None:
    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(title=title)
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*row)
        Console(emoji=False).print(table)
    except ImportError:
        # Fallback to plain text if rich is not installed
        print(title)
        print("  ".join(headers))
        for row in rows:
            print("  ".join(row))


@click.group()
@click.option("--format", "-f", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.pass_context
def main(ctx: click.Context, fmt: str) -> None:
    """Estimate and review Tinker API costs."""
    ctx.ensure_object(dict)
    ctx.obj["format"] = fmt


@main.command()
@click.option("--model", required=True, help="Tinker model ID (e.g. Qwen/Qwen3.5-9B)")
@click.option("--prefill-tokens", default=0, help="Number of prefill (input) tokens")
@click.option("--sample-tokens",  default=0, help="Number of sample (output) tokens")
@click.option("--train-tokens",   default=0, help="Number of training tokens")
@click.pass_context
def estimate(ctx: click.Context, model: str, prefill_tokens: int, sample_tokens: int, train_tokens: int) -> None:
    """Estimate cost for a given model and token counts.

    \b
    Example:
      tinker-billing estimate \\
        --model Qwen/Qwen3.5-9B \\
        --prefill-tokens 50000 \\
        --sample-tokens 20000 \\
        --train-tokens 100000
    """
    if prefill_tokens == 0 and sample_tokens == 0 and train_tokens == 0:
        raise click.UsageError("Provide at least one of --prefill-tokens, --sample-tokens, or --train-tokens.")

    try:
        est = estimate_cost(model, prefill_tokens=prefill_tokens, sample_tokens=sample_tokens, train_tokens=train_tokens)
    except KeyError as e:
        raise click.BadParameter(str(e), param_hint="--model")

    fmt = ctx.obj["format"]
    if fmt == "json":
        data = {
            "model": est.model,
            "prefill_tokens": est.prefill_tokens,
            "sample_tokens": est.sample_tokens,
            "train_tokens": est.train_tokens,
            "prefill_cost": round(est.prefill_cost, 6),
            "sample_cost": round(est.sample_cost, 6),
            "train_cost": round(est.train_cost, 6),
            "total_cost": round(est.total_cost, 6),
        }
        json.dump(data, sys.stdout, indent=2)
        print()
    else:
        p_rate, s_rate, t_rate = PRICING[model]
        rows = []
        if prefill_tokens:
            rows.append(["Prefill", f"{prefill_tokens:,}", f"${p_rate:.2f}", f"${est.prefill_cost:.4f}"])
        if sample_tokens:
            rows.append(["Sample", f"{sample_tokens:,}", f"${s_rate:.2f}", f"${est.sample_cost:.4f}"])
        if train_tokens:
            rows.append(["Train",  f"{train_tokens:,}",  f"${t_rate:.2f}",  f"${est.train_cost:.4f}"])
        rows.append(["Total", "", "", f"${est.total_cost:.4f}"])
        _print_table(f"Cost estimate — {model}", ["Operation", "Tokens", "Rate ($/M)", "Cost"], rows)


@main.command()
@click.pass_context
def rates(ctx: click.Context) -> None:
    """List per-million-token rates for all available models."""
    fmt = ctx.obj["format"]
    if fmt == "json":
        data = {m: {"prefill": p, "sample": s, "train": t} for m, (p, s, t) in PRICING.items()}
        json.dump(data, sys.stdout, indent=2)
        print()
    else:
        rows = [[m, f"${p:.2f}", f"${s:.2f}", f"${t:.2f}"] for m, (p, s, t) in sorted(PRICING.items())]
        _print_table("Model rates (USD per million tokens)", ["Model", "Prefill", "Sample", "Train"], rows)
