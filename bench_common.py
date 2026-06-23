"""
Shared helpers for the concurrency benchmark (Experiments A and B).

Goal: reproduce the slowdown reported in
https://github.com/thinking-machines-lab/tinker-cookbook/issues/730

Original report: 16 concurrent requests/process x 50 processes (~800 total),
~3x slower per-job than running a single job alone.
"""

import time
import statistics
from dataclasses import dataclass, field

import tinker
from tinker_cookbook.renderers import get_renderer, get_text_content

# Use a small, cheap model to keep iteration fast and cost low while we
# nail the methodology. Swap to a larger model only after the methodology
# is validated.
BASE_MODEL = "Qwen/Qwen3.5-4B"
RENDERER_NAME = "qwen3_5"

PROMPTS = [
    "What causes thunder?",
    "Write a haiku about the ocean.",
    "What is the capital of New Zealand?",
    "Explain what a hash table is in two sentences.",
    "Name three inventions from the 19th century.",
    "Why do leaves change color in autumn?",
    "Translate to Spanish: The library closes at nine.",
    "What is the smallest prime number greater than 50?",
]


@dataclass
class RequestResult:
    latency_s: float
    ok: bool
    error: str | None = None


@dataclass
class LevelResult:
    """Aggregated stats for one concurrency level (one row in the final chart)."""
    concurrency: int
    n_requests: int
    wall_time_s: float
    throughput_rps: float
    p50_latency_s: float
    p95_latency_s: float
    n_errors: int
    raw_latencies: list[float] = field(default_factory=list)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def summarize(concurrency: int, results: list[RequestResult], wall_time_s: float) -> LevelResult:
    latencies = [r.latency_s for r in results if r.ok]
    n_errors = sum(1 for r in results if not r.ok)
    return LevelResult(
        concurrency=concurrency,
        n_requests=len(results),
        wall_time_s=wall_time_s,
        throughput_rps=len(results) / wall_time_s if wall_time_s > 0 else float("nan"),
        p50_latency_s=percentile(latencies, 0.50),
        p95_latency_s=percentile(latencies, 0.95),
        n_errors=n_errors,
        raw_latencies=latencies,
    )


def make_sampling_client(base_model: str = BASE_MODEL, renderer_name: str = RENDERER_NAME):
    """Build a fresh service client + sampling client + renderer.
    Used identically by Experiment A (once) and Experiment B (once per process).
    Accepts optional overrides so later experiments can swap models without
    touching bench_common.
    """
    service_client = tinker.ServiceClient()
    sampling_client = service_client.create_sampling_client(base_model=base_model)
    tokenizer = sampling_client.get_tokenizer()
    renderer = get_renderer(renderer_name, tokenizer)
    stop_sequences = renderer.get_stop_sequences()
    params = tinker.SamplingParams(max_tokens=80, temperature=0.7, stop=stop_sequences)
    return sampling_client, renderer, params


async def sample_one_async(sampling_client, renderer, params, prompt_text: str) -> RequestResult:
    start = time.time()
    try:
        messages = [{"role": "user", "content": prompt_text}]
        model_input = renderer.build_generation_prompt(messages)
        result = await sampling_client.sample_async(
            prompt=model_input, num_samples=1, sampling_params=params
        )
        # touch the response so parsing cost is included, matching real usage
        response_msg, _ = renderer.parse_response(result.sequences[0].tokens)
        get_text_content(response_msg)
        return RequestResult(latency_s=time.time() - start, ok=True)
    except Exception as e:
        return RequestResult(latency_s=time.time() - start, ok=False, error=str(e))


def sample_one_sync(sampling_client, renderer, params, prompt_text: str) -> RequestResult:
    start = time.time()
    try:
        messages = [{"role": "user", "content": prompt_text}]
        model_input = renderer.build_generation_prompt(messages)
        result = sampling_client.sample(
            prompt=model_input, num_samples=1, sampling_params=params
        ).result()
        response_msg, _ = renderer.parse_response(result.sequences[0].tokens)
        get_text_content(response_msg)
        return RequestResult(latency_s=time.time() - start, ok=True)
    except Exception as e:
        return RequestResult(latency_s=time.time() - start, ok=False, error=str(e))


def print_level_result(label: str, lr: LevelResult):
    print(
        f"[{label}] concurrency={lr.concurrency:>4} "
        f"n={lr.n_requests:>4} "
        f"wall={lr.wall_time_s:7.2f}s "
        f"throughput={lr.throughput_rps:6.2f} req/s "
        f"p50={lr.p50_latency_s:6.2f}s "
        f"p95={lr.p95_latency_s:6.2f}s "
        f"errors={lr.n_errors}"
    )
