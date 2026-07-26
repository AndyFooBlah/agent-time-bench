"""Load and validate domain scenario files against the canonical JSON schema."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_DIR = REPO_ROOT / "scenarios"
SCHEMA_PATH = REPO_ROOT / "schema" / "scenario.schema.json"


@dataclass(frozen=True)
class Scenario:
    domain: str
    raw: dict[str, Any]
    tools: list[dict[str, Any]]

    @property
    def id(self) -> str:
        return self.raw["id"]

    @property
    def context(self) -> dict[str, str]:
        return self.raw["context"]

    @property
    def user(self) -> str:
        return self.raw["user"]

    @property
    def mocks(self) -> dict[str, Any]:
        return self.raw.get("mocks", {})

    @property
    def expect(self) -> dict[str, Any]:
        return self.raw["expect"]

    @property
    def directions(self) -> list[str]:
        return self.raw["directions"]


@dataclass
class Domain:
    name: str
    description: str
    tools: list[dict[str, Any]]
    scenarios: list[Scenario] = field(default_factory=list)


def load_domain(path: Path, validate: bool = True) -> Domain:
    data = json.loads(path.read_text())
    if validate:
        schema = json.loads(SCHEMA_PATH.read_text())
        jsonschema.validate(data, schema)
    domain = Domain(name=data["domain"], description=data["description"], tools=data["tools"])
    tool_names = {t["name"] for t in domain.tools}
    for raw in data["scenarios"]:
        for tc in raw["expect"].get("toolCalls", []):
            if tc["tool"] not in tool_names:
                raise ValueError(f"{raw['id']}: expectation references unknown tool {tc['tool']}")
        for mock_name in raw.get("mocks", {}):
            if mock_name not in tool_names:
                raise ValueError(f"{raw['id']}: mock for unknown tool {mock_name}")
        domain.scenarios.append(Scenario(domain=domain.name, raw=raw, tools=domain.tools))
    return domain


def load_all(scenarios_dir: Path = SCENARIOS_DIR, only: list[str] | None = None) -> list[Domain]:
    domains = []
    for path in sorted(scenarios_dir.glob("*.json")):
        if only and path.stem not in only:
            continue
        domains.append(load_domain(path))
    return domains
