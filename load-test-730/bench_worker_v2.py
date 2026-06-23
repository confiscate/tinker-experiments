"""
Worker v2 for Experiments C and D (and their large-model variants E/F).

Improvements over bench_worker.py (used by Experiments A/B):
- Pool initializer: each process builds its SamplingClient and fires one
  warmup request BEFORE any timed work, so startup cost is excluded.
- Internal concurrency: workers use asyncio.gather rather than sequential
  requests, matching the original reporter's 16-concurrent-per-process setup.
"""

import asyncio
import os

from bench_common import PROMPTS, make_sampling_client, sample_one_async, RequestResult

_sampling_client = None
_renderer = None
_params = None


def worker_init(api_key: str, base_model: str, renderer_name: str):
    global _sampling_client, _renderer, _params
    os.environ["TINKER_API_KEY"] = api_key
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    _sampling_client, _renderer, _params = make_sampling_client(
        base_model=base_model, renderer_name=renderer_name
    )
    asyncio.run(sample_one_async(_sampling_client, _renderer, _params, PROMPTS[0]))


def worker_run(args: tuple) -> list:
    """Returns list of (latency_s, ok, error)."""
    n_requests, concurrency = args

    async def _run():
        sem = asyncio.Semaphore(concurrency)

        async def bounded(prompt_text):
            async with sem:
                return await sample_one_async(_sampling_client, _renderer, _params, prompt_text)

        prompts = [PROMPTS[i % len(PROMPTS)] for i in range(n_requests)]
        return await asyncio.gather(*[bounded(p) for p in prompts])

    results: list[RequestResult] = asyncio.run(_run())
    return [(r.latency_s, r.ok, r.error) for r in results]
