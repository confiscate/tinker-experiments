"""tinker-billing: cost estimation for the Tinker SDK.

Install alongside the tinker SDK:
    pip install tinker tinker-billing

Then use the CLI:
    tinker-billing estimate --model Qwen/Qwen3.5-9B --prefill-tokens 50000
    tinker-billing rates
"""

from ._estimator import PRICING, estimate_cost

__all__ = ["PRICING", "estimate_cost"]
