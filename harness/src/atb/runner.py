"""Run the benchmark matrix and emit graded results as JSONL."""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import build_agent
from .grading import grade_scenario
from .scenarios import Domain, Scenario

MAX_ATTEMPTS = 5
RETRYABLE = ("429", "RESOURCE_EXHAUSTED", "500", "503", "UNAVAILABLE", "overloaded", "RateLimit")


async def run_scenario(
    domain: Domain,
    scenario: Scenario,
    model_id: str,
    condition: str,
    skill: str | None,
    prompt: str = "baseline-v1",
) -> dict[str, Any]:
    recorder: list[dict[str, Any]] = []
    agent = build_agent(scenario, domain.description, model_id, condition, skill, recorder, prompt)
    runner = InMemoryRunner(agent)
    started = time.monotonic()
    final_text = ""
    error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        recorder.clear()
        final_text, error = "", None
        try:
            session = await runner.session_service.create_session(
                app_name=runner.app_name, user_id="bench", session_id=f"{scenario.id}-{attempt}"
            )
            message = types.Content(role="user", parts=[types.Part(text=scenario.user)])
            async for event in runner.run_async(
                user_id="bench", session_id=session.id, new_message=message
            ):
                if event.content and event.content.parts:
                    # Reasoning models emit thought parts; they are not the answer.
                    text = "".join(p.text or "" for p in event.content.parts if not getattr(p, "thought", False))
                    if text.strip() and event.is_final_response():
                        final_text = text
            break
        except Exception as exc:  # noqa: BLE001 — record and (maybe) retry
            error = f"{type(exc).__name__}: {exc}"
            if attempt < MAX_ATTEMPTS and any(marker in str(exc) for marker in RETRYABLE):
                # Per-minute quotas need long waits; other transients short ones.
                is_rate = "RateLimit" in str(exc) or "429" in str(exc)
                await asyncio.sleep(25 * attempt if is_rate else 4 * attempt)
                continue
            error += "\n" + traceback.format_exc(limit=3)
            break

    graded = grade_scenario(scenario.expect, recorder, final_text, dict(scenario.context))
    return {
        "run": {"model": model_id, "condition": condition, "skill": skill, "prompt": prompt},
        "domain": domain.name,
        "scenario": scenario.id,
        "directions": scenario.directions,
        "user": scenario.user,
        "tool_calls": recorder,
        "response": final_text,
        "error": error,
        "latency_s": round(time.monotonic() - started, 2),
        **graded,
    }


async def run_matrix(
    domains: list[Domain],
    model_id: str,
    conditions: list[str],
    skill: str | None,
    out_path: Path,
    concurrency: int = 4,
    prompt: str = "baseline-v1",
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(concurrency)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    lock = asyncio.Lock()

    async def one(domain: Domain, scenario: Scenario, condition: str) -> None:
        async with semaphore:
            row = await run_scenario(domain, scenario, model_id, condition, skill, prompt)
        async with lock:
            results.append(row)
            with out_path.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
            status = "ok" if not row["error"] else "ERR"
            print(
                f"[{len(results):3d}] {condition:8s} {row['scenario']:8s} {status} "
                f"nl2time={row['nl2time_pass']} time2nl={row['time2nl_pass']}"
            )

    header = {
        "meta": {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "model": model_id,
            "conditions": conditions,
            "skill": skill,
            "prompt": prompt,
            "scenario_count": sum(len(d.scenarios) for d in domains),
        }
    }
    with out_path.open("a") as fh:
        fh.write(json.dumps(header) + "\n")

    await asyncio.gather(
        *[
            one(domain, scenario, condition)
            for condition in conditions
            for domain in domains
            for scenario in domain.scenarios
        ]
    )
    return results
