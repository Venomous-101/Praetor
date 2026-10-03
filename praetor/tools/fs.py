"""Workspace-confined filesystem tools (read/write/list)."""
from __future__ import annotations

import os
from typing import Any

from praetor.tools.base import Tool, ToolError

MAX_READ_BYTES = 65536
MAX_WRITE_BYTES = 65536


class Workspace:
    """A confined directory: all paths are resolved against its root."""

    def __init__(self, root: str) -> None:
        self.root = os.path.realpath(root)
        os.makedirs(self.root, exist_ok=True)

    def resolve(self, path: str) -> str:
        root_real = self.root
        candidate = os.path.realpath(os.path.join(root_real, path))
        if candidate != root_real and not candidate.startswith(root_real + os.sep):
            raise ToolError("path escapes the workspace: " + repr(path))
        return candidate


class ReadFileTool(Tool):
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.name = "read_file"
        self.description = (
            "Read a text file from the agent workspace. Paths are relative to the workspace root."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "relative file path"}
            },
            "required": ["path"],
        }

    def run(self, arguments: dict[str, Any]) -> str:
        target = self.workspace.resolve(arguments["path"])
        if not os.path.isfile(target):
            raise ToolError("no such file: " + repr(arguments["path"]))
        with open(target, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read(MAX_READ_BYTES)


class WriteFileTool(Tool):
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.name = "write_file"
        self.description = (
            "Write a text file inside the agent workspace. Overwrites existing files. "
            "Paths are relative to the workspace root; parent-directory escapes are rejected."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        }

    def run(self, arguments: dict[str, Any]) -> str:
        content = arguments["content"]
        if len(content.encode("utf-8", "replace")) > MAX_WRITE_BYTES:
            raise ToolError("content exceeds the maximum write size")
        target = self.workspace.resolve(arguments["path"])
        directory = os.path.dirname(target)
        os.makedirs(directory, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(content)
        return "wrote " + str(len(content)) + " chars to " + arguments["path"]


class ListFilesTool(Tool):
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.name = "list_files"
        self.description = "List files present in the agent workspace."
        self.parameters = {"type": "object", "properties": {}}

    def run(self, arguments: dict[str, Any]) -> str:
        found: list[str] = []
        for base, dirs, files in os.walk(self.workspace.root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                full = os.path.join(base, name)
                found.append(os.path.relpath(full, self.workspace.root))
        found.sort()
        return chr(10).join(found) if found else "(workspace is empty)"
