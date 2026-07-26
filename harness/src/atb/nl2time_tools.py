"""Agent-facing time tools backed by the nl2time JS library via bridge/bridge.mjs.

The scenario's context (now / timeZone / locale) is injected by the harness —
the model supplies only the phrase or the timestamps. Present only in the
`nl2time` condition.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from google.adk.tools import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

BRIDGE = Path(__file__).resolve().parents[3] / "bridge" / "bridge.mjs"


def call_bridge(request: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(
        ["node", str(BRIDGE)],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": f"bridge failed: {proc.stderr[-500:]}"}
    return json.loads(proc.stdout)


class ResolveTimephraseTool(BaseTool):
    def __init__(self, context: dict[str, str]):
        super().__init__(
            name="resolve_timephrase",
            description=(
                "Convert a natural-language time expression into exact UTC bounds, using the "
                "user's current time, timezone, and locale (already configured). Pass the user's "
                "own words, e.g. 'last week', 'yesterday', 'between July 4th and July 10th', "
                "'since June 15th'. Returns {start, end, grain} as UTC ISO 8601 with end "
                "exclusive, plus ordered alternatives if the phrase is ambiguous. Use this "
                "whenever you need datetime arguments for another tool. Set direction to "
                "'future' when the user asks about upcoming things (deadlines, schedules), "
                "'past' when they ask about history; omit it for the nearest reading."
            ),
        )
        self._context = context

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "phrase": types.Schema(
                        type=types.Type.STRING,
                        description="The natural-language time expression, verbatim from the user",
                    ),
                    "direction": types.Schema(
                        type=types.Type.STRING,
                        enum=["past", "future"],
                        description="Tense hint: 'past' for history questions, 'future' for upcoming; omit for nearest",
                    ),
                },
                required=["phrase"],
            ),
        )

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        context = dict(self._context)
        direction = args.get("direction")
        context["bias"] = direction if direction in ("past", "future") else "none"
        return call_bridge({"op": "resolve", "phrase": args.get("phrase", ""), "context": context})


class DescribeTimeTool(BaseTool):
    def __init__(self, context: dict[str, str]):
        super().__init__(
            name="describe_time",
            description=(
                "Convert UTC ISO 8601 timestamps into natural language for the user, correctly "
                "rendered in the user's timezone and locale (already configured). Returns a "
                "casual and a neutral phrasing per timestamp. Use this before telling the user "
                "when something happened."
            ),
        )
        self._context = context

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "timestamps_utc": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="UTC ISO 8601 timestamps, e.g. ['2026-07-01T02:05:00Z']",
                    )
                },
                required=["timestamps_utc"],
            ),
        )

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        return call_bridge(
            {"op": "describe", "instants": args.get("timestamps_utc", []), "context": self._context}
        )


def build_nl2time_tools(context: dict[str, str]) -> list[BaseTool]:
    return [ResolveTimephraseTool(context), DescribeTimeTool(context)]
