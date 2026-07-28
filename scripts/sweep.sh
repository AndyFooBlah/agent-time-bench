#!/bin/bash
# Multi-model sweep (docs/results-flash-lite.md "Next"). Frozen config:
# prompt baseline-v2, skill nl2time-v3, nl2time 0.3.1, both conditions.
# Sequential per run (rate-limit friendly); resumable: existing output files
# are skipped, so rerunning the script continues where it left off.
#
# Needs: .env at repo root with OPENAI_API_KEY / ANTHROPIC_API_KEY /
# OPENROUTER_API_KEY (harness loads it), plus gcloud ADC for the Vertex pair.
set -uo pipefail
cd "$(dirname "$0")/../harness"

export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=weatherbot-prod
export GOOGLE_CLOUD_LOCATION=global

PROMPT=baseline-v2
SKILL=nl2time-v3

run() { # model repeats concurrency
  local model="$1" repeats="$2" conc="${3:-3}" slug
  slug=$(echo "$model" | tr '/:' '__')
  for i in $(seq 1 "$repeats"); do
    local out="../results/sweep-${slug}-r${i}.jsonl"
    if [ -s "$out" ]; then echo "skip existing $out"; continue; fi
    echo "=== $model repeat $i (concurrency $conc)"
    uv run atb run --model "$model" --conditions baseline nl2time \
      --prompt "$PROMPT" --skill "$SKILL" --concurrency "$conc" --out "$out" \
      || echo "!! run failed: $model r$i (continuing)"
  done
}

run gemini-3.5-flash-lite 3
run gemini-3.6-flash 3
run litellm:openrouter/google/gemma-4-26b-a4b-it 3
run litellm:openrouter/deepseek/deepseek-v4-pro 3
run litellm:openrouter/moonshotai/kimi-k3 3 2
# Sol routed via OpenRouter (direct OpenAI account has no quota);
# concurrency 1 for the new-account per-minute limit on premium models.
run litellm:openrouter/openai/gpt-5.6-sol 2 1
run litellm:anthropic/claude-opus-5 2 2

echo "=== sweep complete; aggregate:"
uv run atb report ../results/sweep-*.jsonl
