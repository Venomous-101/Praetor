"""Core data types shared across Praetor.

These types are deliberately small and dependency-free so every layer
(runtime, tools, security, eval) speaks the same language.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class RunStatus(str, Enum):
    """Terminal state of an agent run."""

    OK = "ok"
    ERROR = "error"                     # unrecoverable internal error
    ABORTED_POLICY = "aborted_policy"   # security policy terminated the run
    ABORTED_BUDGET = "aborted_budget"   # step/tool-call budget exhausted


@dataclass(frozen=True)
class ToolSpec:
    """Public description of a tool, shown to the model."""

    name: str
    description: str
    parameters: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class ToolCall:
    """A model-issued request to invoke a tool."""

    id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """Structured, size-bounded observation returned to the model."""

    ok: bool
    output: str
    error: str | None = None


@dataclass(frozen=True)
class Step:
    """One act-observe cycle of the agent."""

    index: int
    tool_call: ToolCall
    result: ToolResult
    duration_s: float


@dataclass
class AgentResult:
    """Everything a run produced, for auditing and evaluation."""

    status: RunStatus
    answer: str | None = None
    steps: list[Step] = field(default_factory=list)
    tool_calls: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
