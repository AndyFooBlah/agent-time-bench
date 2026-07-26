"""Per-scenario agent assembly: instruction, mocked domain tools, optional time tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent

from .mocktools import build_mock_tools
from .nl2time_tools import build_nl2time_tools
from .scenarios import Scenario

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO_ROOT / "skills"

INSTRUCTION_TEMPLATE = """\
You are a helpful assistant for the user's {domain_description}
Answer the user's question using the available tools. Be concise and factual;
if the data doesn't support an answer, say so.

Current date and time: {now}
User timezone: {timeZone}
User locale: {locale}
"""


def load_skill(skill: str | None) -> str:
    if not skill:
        return ""
    path = SKILLS_DIR / f"{skill}.md"
    return "\n" + path.read_text()


def make_model(model_id: str):
    """'gemini-*' → native model string; 'litellm:<provider/model>' → LiteLlm wrapper."""
    if model_id.startswith("litellm:"):
        from google.adk.models.lite_llm import LiteLlm  # requires google-adk[extensions]

        return LiteLlm(model=model_id.split(":", 1)[1])
    return model_id


def build_agent(
    scenario: Scenario,
    domain_description: str,
    model_id: str,
    condition: str,
    skill: str | None,
    recorder: list[dict[str, Any]],
) -> LlmAgent:
    ctx = scenario.context
    instruction = INSTRUCTION_TEMPLATE.format(
        domain_description=domain_description.rstrip(".") + ".",
        now=ctx["now"],
        timeZone=ctx["timeZone"],
        locale=ctx["locale"],
    )
    tools: list[Any] = build_mock_tools(scenario.tools, scenario.mocks, recorder)
    if condition == "nl2time":
        tools.extend(build_nl2time_tools(dict(ctx)))
        instruction += load_skill(skill)
    return LlmAgent(
        name="atb_agent",
        model=make_model(model_id),
        instruction=instruction,
        tools=tools,
    )
