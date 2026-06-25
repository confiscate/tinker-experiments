"""Core cost estimation logic — identical to the billing.py PR, extracted for standalone use."""

from dataclasses import dataclass
from typing import Dict, Tuple

_PER_MILLION = 1_000_000

# (prefill, sample, train) — USD per million tokens
# Source: https://tinker-docs.thinkingmachines.ai/tinker/models/
# fmt: off
PRICING: Dict[str, Tuple[float, float, float]] = {
    "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16":             (1.66,  4.15,  4.98),
    "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16:peft:262144": (3.32,  8.30,  9.96),
    "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16":             (0.38,  0.96,  1.16),
    "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16:peft:262144": (0.76,  1.92,  2.32),
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16":                (0.13,  0.33,  0.40),
    "moonshotai/Kimi-K2.6":                                      (1.47,  3.66,  4.40),
    "moonshotai/Kimi-K2.6:peft:131072":                          (5.15, 12.81, 15.40),
    "moonshotai/Kimi-K2.5":                                      (1.47,  3.66,  4.40),
    "moonshotai/Kimi-K2.5:peft:131072":                          (5.15, 12.81, 15.40),
    "Qwen/Qwen3.6-35B-A3B":                                      (0.36,  0.89,  1.07),
    "Qwen/Qwen3.6-27B":                                          (1.24,  3.73,  3.73),
    "Qwen/Qwen3.5-397B-A17B":                                    (2.00,  5.00,  6.00),
    "Qwen/Qwen3.5-397B-A17B:peft:262144":                       (4.00, 10.00, 12.00),
    "Qwen/Qwen3.5-35B-A3B-Base":                                 (0.36,  0.89,  1.07),
    "Qwen/Qwen3.5-9B":                                           (0.44,  1.33,  1.33),
    "Qwen/Qwen3.5-9B-Base":                                      (0.44,  1.33,  1.33),
    "Qwen/Qwen3.5-4B":                                           (0.22,  0.67,  0.67),
    "Qwen/Qwen3-8B":                                             (0.13,  0.40,  0.40),
    "openai/gpt-oss-120b":                                       (0.18,  0.44,  0.52),
    "openai/gpt-oss-120b:peft:131072":                           (0.63,  1.54,  1.82),
    "openai/gpt-oss-20b":                                        (0.12,  0.30,  0.36),
    "deepseek-ai/DeepSeek-V3.1":                                 (1.13,  2.81,  3.38),
}
# fmt: on


@dataclass(frozen=True)
class CostEstimate:
    model: str
    prefill_tokens: int
    sample_tokens: int
    train_tokens: int
    prefill_cost: float
    sample_cost: float
    train_cost: float

    @property
    def total_cost(self) -> float:
        return self.prefill_cost + self.sample_cost + self.train_cost


def estimate_cost(
    model: str,
    *,
    prefill_tokens: int = 0,
    sample_tokens: int = 0,
    train_tokens: int = 0,
) -> CostEstimate:
    """Return a cost estimate for the given model and token counts.

    Args:
        model: Tinker model ID, e.g. ``"Qwen/Qwen3.5-9B"``.
        prefill_tokens: Number of input/prompt tokens processed.
        sample_tokens: Number of output tokens generated.
        train_tokens: Number of tokens used in training steps.

    Raises:
        KeyError: If the model is not in the pricing table.

    Example::

        from tinker_billing import estimate_cost
        est = estimate_cost("Qwen/Qwen3.5-9B", prefill_tokens=50_000, train_tokens=100_000)
        print(f"Estimated cost: ${est.total_cost:.4f}")
    """
    if model not in PRICING:
        raise KeyError(
            f"Unknown model '{model}'. "
            f"Available: {sorted(PRICING)}"
        )
    p_rate, s_rate, t_rate = PRICING[model]
    return CostEstimate(
        model=model,
        prefill_tokens=prefill_tokens,
        sample_tokens=sample_tokens,
        train_tokens=train_tokens,
        prefill_cost=prefill_tokens / _PER_MILLION * p_rate,
        sample_cost=sample_tokens / _PER_MILLION * s_rate,
        train_cost=train_tokens / _PER_MILLION * t_rate,
    )
