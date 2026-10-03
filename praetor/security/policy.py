"""Least-privilege policy enforcement for tool calls."""
from __future__ import annotations

from dataclasses import dataclass, field


class PolicyViolation(RuntimeError):
    """A tool call would violate the security policy."""


@dataclass
class ToolPolicy:
    """Static, inspectable policy for one agent run.

    Default-deny: a tool must be explicitly allowed before it can run.
    Budgets are enforced per tool and in total.
    """

    allowed_tools: frozenset[str] = frozenset()
    max_calls_per_tool: int = 8
    max_total_calls: int = 32
    _counts: dict[str, int] = field(default_factory=dict)

    def allow(self, *names: str) -> "ToolPolicy":
        self.allowed_tools = self.allowed_tools | frozenset(names)
        return self

    def check(self, tool: str) -> None:
        """Raise PolicyViolation if `tool` cannot be invoked now."""
        if tool not in self.allowed_tools:
            raise PolicyViolation("tool '" + tool + "' is not in the allowlist")
        if self._counts.get(tool, 0) >= self.max_calls_per_tool:
            raise PolicyViolation(
                "tool '" + tool + "' exceeded the per-tool call budget ("
                + str(self.max_calls_per_tool) + ")"
            )
        if sum(self._counts.values()) >= self.max_total_calls:
            raise PolicyViolation("total tool-call budget exhausted")

    def record(self, tool: str) -> None:
        self._counts[tool] = self._counts.get(tool, 0) + 1

    def call_count(self, tool: str) -> int:
        return self._counts.get(tool, 0)
