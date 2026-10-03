"""Sandboxed Python execution tool."""
from __future__ import annotations

import tempfile
from typing import Any

from praetor.security.sandbox import run_python_sandboxed
from praetor.tools.base import Tool


class PythonTool(Tool):
    """Executes untrusted Python inside the process-level sandbox."""

    def __init__(self, workdir: str | None = None) -> None:
        self._workdir = workdir
        self.name = "python"
        self.description = (
            "Execute a short Python script in a locked-down sandbox "
            "(isolated interpreter, scrubbed environment, CPU/memory/time limits) "
            "and return its stdout."
        )
        self.parameters = {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        }

    def run(self, arguments: dict[str, Any]) -> str:
        result = run_python_sandboxed(
            arguments["code"],
            timeout_s=10.0,
            workdir=self._workdir or tempfile.mkdtemp(prefix="praetor-run-"),
        )
        parts: list[str] = []
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            parts.append("[stderr] " + result.stderr)
        if result.timed_out:
            parts.append("[sandbox] execution timed out")
        if not parts:
            return "(no output)"
        return chr(10).join(parts)
