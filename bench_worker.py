"""
Worker function for Experiment B. Must live in its own importable module
(not inside experiment_b.py's __main__ block) so multiprocessing can pickle
and import it correctly on all platforms, including spawn-based ones.

Each worker process:
  1. Builds its OWN SamplingClient from scratch (no shared state with
     other processes -- this is the whole point of the experiment).
  2. Makes its requests ONE AT A TIME, sequentially (no internal concurrency).
  3. Returns raw (latency, ok, error) tuples back to the parent process.
"""

import os

from bench_common import PROMPTS, make_sampling_client, sample_one_sync


def worker_run(args: tuple) -> list:
    """Runs in a separate OS process. Returns list of (latency_s, ok, error)."""
    n_requests, api_key = args
    os.environ["TINKER_API_KEY"] = api_key
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    sampling_client, renderer, params = make_sampling_client()
    results = []
    for i in range(n_requests):
        prompt_text = PROMPTS[i % len(PROMPTS)]
        r = sample_one_sync(sampling_client, renderer, params, prompt_text)
        results.append((r.latency_s, r.ok, r.error))
    return results
