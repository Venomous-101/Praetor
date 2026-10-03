"""Tool registry with integrity checks."""
from __future__ import annotations

from praetor.security.integrity import IntegrityGuard
from praetor.tools.base import Tool


class UnknownToolError(KeyError):
    pass


class ToolRegistry:
    """Holds the toolset for one agent; quarantines tampered tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._guard = IntegrityGuard()

    def add(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool must declare a name")
        if tool.name in self._tools:
            raise ValueError("duplicate tool '" + tool.name + "'")
        spec = tool.spec()  # validates the schema
        self._guard.register(spec)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownToolError(name)
        if not self._guard.verify(tool.spec()):
            raise RuntimeError(
                "integrity check failed for tool '" + name + "'; refusing to execute"
            )
        return tool

    def specs(self) -> list[dict]:
        return [self._tools[name].spec() for name in sorted(self._tools)]

    def names(self) -> list[str]:
        return sorted(self._tools)
