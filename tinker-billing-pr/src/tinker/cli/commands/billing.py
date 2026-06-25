"""Commands for estimating Tinker API costs.

This module implements the 'tinker billing' commands, including:
- estimate: Estimate cost given token counts and a model
- rates: List per-million-token rates for all available models
"""

from typing import Any, Dict, List, Optional, Tuple

import click

from ..context import CLIContext
from ..output import OutputBase

# Rates in USD per million tokens. Sourced from https://tinker-docs.thinkingmachines.ai/tinker/models/
# fmt: off
_PRICING: Dict[str, Tuple[float, float, float]] = {
    # (prefill, sample, train) — USD per million tokens
    "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16":          (1.66,  4.15,  4.98),
    "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16:peft:262144": (3.32, 8.30, 9.96),
    "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16":          (0.38,  0.96,  1.16),
    "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16:peft:262144": (0.76, 1.92, 2.32),
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16":             (0.13,  0.33,  0.40),
    "moonshotai/Kimi-K2.6":                                   (1.47,  3.66,  4.40),
    "moonshotai/Kimi-K2.6:peft:131072":                       (5.15, 12.81, 15.40),
    "moonshotai/Kimi-K2.5":                                   (1.47,  3.66,  4.40),
    "moonshotai/Kimi-K2.5:peft:131072":                       (5.15, 12.81, 15.40),
    "Qwen/Qwen3.6-35B-A3B":                                   (0.36,  0.89,  1.07),
    "Qwen/Qwen3.6-27B":                                       (1.24,  3.73,  3.73),
    "Qwen/Qwen3.5-397B-A17B":                                 (2.00,  5.00,  6.00),
    "Qwen/Qwen3.5-397B-A17B:peft:262144":                    (4.00, 10.00, 12.00),
    "Qwen/Qwen3.5-35B-A3B-Base":                              (0.36,  0.89,  1.07),
    "Qwen/Qwen3.5-9B":                                        (0.44,  1.33,  1.33),
    "Qwen/Qwen3.5-9B-Base":                                   (0.44,  1.33,  1.33),
    "Qwen/Qwen3.5-4B":                                        (0.22,  0.67,  0.67),
    "Qwen/Qwen3-8B":                                          (0.13,  0.40,  0.40),
    "openai/gpt-oss-120b":                                    (0.18,  0.44,  0.52),
    "openai/gpt-oss-120b:peft:131072":                        (0.63,  1.54,  1.82),
    "openai/gpt-oss-20b":                                     (0.12,  0.30,  0.36),
    "deepseek-ai/DeepSeek-V3.1":                              (1.13,  2.81,  3.38),
}
# fmt: on

_PER_MILLION = 1_000_000


def _lookup(model: str) -> Tuple[float, float, float]:
    if model not in _PRICING:
        available = "\n  ".join(sorted(_PRICING))
        raise click.BadParameter(
            f"Unknown model '{model}'.\n\nAvailable models:\n  {available}",
            param_hint="--model",
        )
    return _PRICING[model]


class EstimateOutput(OutputBase):
    def __init__(
        self,
        model: str,
        prefill_tokens: int,
        sample_tokens: int,
        train_tokens: int,
        rates: Tuple[float, float, float],
    ):
        self.model = model
        self.prefill_tokens = prefill_tokens
        self.sample_tokens = sample_tokens
        self.train_tokens = train_tokens
        self.prefill_rate, self.sample_rate, self.train_rate = rates

    def _costs(self) -> Tuple[float, float, float]:
        prefill = self.prefill_tokens / _PER_MILLION * self.prefill_rate
        sample = self.sample_tokens / _PER_MILLION * self.sample_rate
        train = self.train_tokens / _PER_MILLION * self.train_rate
        return prefill, sample, train

    def to_dict(self) -> Dict[str, Any]:
        prefill_cost, sample_cost, train_cost = self._costs()
        return {
            "model": self.model,
            "prefill_tokens": self.prefill_tokens,
            "sample_tokens": self.sample_tokens,
            "train_tokens": self.train_tokens,
            "prefill_cost": round(prefill_cost, 6),
            "sample_cost": round(sample_cost, 6),
            "train_cost": round(train_cost, 6),
            "total_cost": round(prefill_cost + sample_cost + train_cost, 6),
        }

    def get_title(self) -> Optional[str]:
        return f"Cost estimate — {self.model}"

    def get_table_columns(self) -> List[str]:
        return ["Operation", "Tokens", "Rate ($/M)", "Cost"]

    def get_table_rows(self) -> List[List[str]]:
        prefill_cost, sample_cost, train_cost = self._costs()
        total = prefill_cost + sample_cost + train_cost
        rows = []
        if self.prefill_tokens:
            rows.append(["Prefill", f"{self.prefill_tokens:,}", f"${self.prefill_rate:.2f}", f"${prefill_cost:.4f}"])
        if self.sample_tokens:
            rows.append(["Sample", f"{self.sample_tokens:,}", f"${self.sample_rate:.2f}", f"${sample_cost:.4f}"])
        if self.train_tokens:
            rows.append(["Train",  f"{self.train_tokens:,}",  f"${self.train_rate:.2f}",  f"${train_cost:.4f}"])
        rows.append(["Total", "", "", f"${total:.4f}"])
        return rows


class RatesOutput(OutputBase):
    def __init__(self, pricing: Dict[str, Tuple[float, float, float]]):
        self.pricing = pricing

    def to_dict(self) -> Dict[str, Any]:
        return {
            model: {"prefill": p, "sample": s, "train": t}
            for model, (p, s, t) in self.pricing.items()
        }

    def get_title(self) -> Optional[str]:
        return "Model rates (USD per million tokens)"

    def get_table_columns(self) -> List[str]:
        return ["Model", "Prefill", "Sample", "Train"]

    def get_table_rows(self) -> List[List[str]]:
        return [
            [model, f"${p:.2f}", f"${s:.2f}", f"${t:.2f}"]
            for model, (p, s, t) in sorted(self.pricing.items())
        ]


@click.group()
def cli() -> None:
    """Estimate and review Tinker API costs."""


@cli.command()
@click.option("--model", required=True, help="Tinker model ID (e.g. Qwen/Qwen3.5-9B)")
@click.option("--prefill-tokens", default=0, show_default=True, help="Number of prefill (input) tokens")
@click.option("--sample-tokens",  default=0, show_default=True, help="Number of sample (output) tokens")
@click.option("--train-tokens",   default=0, show_default=True, help="Number of training tokens")
@click.pass_obj
def estimate(
    cli_context: CLIContext,
    model: str,
    prefill_tokens: int,
    sample_tokens: int,
    train_tokens: int,
) -> None:
    """Estimate cost for a given model and token counts.

    \b
    Example:
      tinker billing estimate \\
        --model Qwen/Qwen3.5-9B \\
        --prefill-tokens 50000 \\
        --sample-tokens 20000 \\
        --train-tokens 100000
    """
    if prefill_tokens == 0 and sample_tokens == 0 and train_tokens == 0:
        raise click.UsageError(
            "Provide at least one of --prefill-tokens, --sample-tokens, or --train-tokens."
        )
    rates = _lookup(model)
    EstimateOutput(model, prefill_tokens, sample_tokens, train_tokens, rates).print(
        format=cli_context.format
    )


@cli.command()
@click.pass_obj
def rates(cli_context: CLIContext) -> None:
    """List per-million-token rates for all available models."""
    RatesOutput(_PRICING).print(format=cli_context.format)
