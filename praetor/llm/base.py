"""Provider interface: Praetor is model-agnostic by design."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from praetor.types import ToolCall


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""


@dataclass(frozen=True)
class ModelTurn:
    """One model response: a final answer, tool calls, or both."""

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Mapping[str, Any] | None = None
    provider: str = "unknown"


@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, messages: list[Message], tools: list[dict]) -> ModelTurn:
        """Produce the next turn given the conversation so far."""
        ...


def render_tools(tools: list[dict]) -> str:
    """Plain-text rendering of tool specs for providers without native tools."""
    lines: list[str] = []
    for spec in tools:
        lines.append("- " + spec["name"] + ": " + spec["description"])
        for prop, meta in spec.get("parameters", {}).get("properties", {}).items():
            lines.append("    arg " + str(prop) + " (" + str(meta.get("type")) + ")")
    return chr(10).join(lines)
