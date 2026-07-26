"""Mocked domain tools, built dynamically from ToolSpec JSON.

`filter-rows` mocks apply the agent's ACTUAL time bounds to the scenario's
canned rows — wrong bounds return wrong data, like production. Unparseable
datetime args return a tool error, like a real API's 400.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from .timeparse import parse_instant

_TYPE_MAP = {
    "string": types.Type.STRING,
    "integer": types.Type.INTEGER,
    "number": types.Type.NUMBER,
    "boolean": types.Type.BOOLEAN,
}


class MockTool(BaseTool):
    """One domain tool for one scenario: spec from the domain, data from the scenario."""

    def __init__(self, spec: dict[str, Any], scenario_mock: dict[str, Any] | None, recorder: list[dict[str, Any]]):
        super().__init__(name=spec["name"], description=spec["description"])
        self._spec = spec
        self._mock_cfg = spec["mock"]
        self._data = scenario_mock or {}
        self._recorder = recorder

    def _get_declaration(self) -> types.FunctionDeclaration:
        properties = {
            p["name"]: types.Schema(type=_TYPE_MAP[p["type"]], description=p["description"])
            for p in self._spec["params"]
        }
        required = [p["name"] for p in self._spec["params"] if p.get("required")]
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(type=types.Type.OBJECT, properties=properties, required=required),
        )

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        self._recorder.append({"tool": self.name, "args": dict(args)})
        cfg = self._mock_cfg
        if cfg["kind"] == "static":
            # An explicit marker beats an empty dict, which tempts models to hallucinate.
            return self._data.get("response", {"status": "no data available"})

        # filter-rows
        rows = self._data.get("rows", [])
        start = parse_instant(args.get(cfg["startParam"]))
        end = parse_instant(args.get(cfg["endParam"]))
        if start is None or end is None:
            return {
                "error": (
                    f"Invalid or missing datetime for '{cfg['startParam']}'/'{cfg['endParam']}'. "
                    "Both must be ISO 8601 UTC strings, e.g. 2026-07-01T04:00:00Z."
                )
            }
        selected = []
        for row in rows:
            ts = parse_instant(row[cfg["timestampField"]])
            if ts is not None and start <= ts < end:
                selected.append(row)
        return {cfg["rowsKey"]: selected, "count": len(selected)}


def build_mock_tools(
    tools: list[dict[str, Any]], scenario_mocks: dict[str, Any], recorder: list[dict[str, Any]]
) -> list[MockTool]:
    return [MockTool(spec, scenario_mocks.get(spec["name"]), recorder) for spec in tools]
