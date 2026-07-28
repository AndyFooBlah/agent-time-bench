#!/bin/bash
# One-scenario-per-domain smoke of every sweep model (both conditions):
# verifies keys, routing, and each model's tool-call plumbing before the
# full sweep. ~20 scenario-executions per model.
set -uo pipefail
cd "$(dirname "$0")/../harness"

export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=weatherbot-prod
export GOOGLE_CLOUD_LOCATION=global

for model in \
  gemini-3.5-flash-lite \
  gemini-3.6-flash \
  litellm:openrouter/google/gemma-4-26b-a4b-it \
  litellm:openrouter/deepseek/deepseek-v4-pro \
  litellm:openrouter/moonshotai/kimi-k3 \
  litellm:openai/gpt-5.6-sol \
  litellm:anthropic/claude-opus-5 \
; do
  slug=$(echo "$model" | tr '/:' '__')
  echo "=== smoke: $model"
  uv run atb run --model "$model" --conditions baseline nl2time \
    --prompt baseline-v2 --skill nl2time-v3 --limit 1 --concurrency 2 \
    --out "../results/smoke-${slug}.jsonl" \
    || echo "!! SMOKE FAILED: $model"
done
