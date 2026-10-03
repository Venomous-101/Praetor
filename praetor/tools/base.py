"""Tool base class: every tool declares a strict schema."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from praetor.security.integrity import envelope
from praetor.security.schema import validate_arguments, validate_schema


class ToolError(RuntimeError):
    """A tool failed while executing (the run may degrade gracefully)."""


class Tool(ABC):
    """A capability exposed to the agent.

    Subclasses declare `name`, `description`, and a strict `parameters`
    schema. Unknown arguments are always rejected. Observations returned
    to the model are wrapped in an untrusted-data envelope.
    """

    name: str = ""
    description: str = ""
    parameters: Mapping[str, Any] = {}

    def spec(self) -> dict[str, Any]:
        validate_schema(self.parameters)
        return {
            "name": self.name,
            "description": self.description,
            "parameters": dict(self.parameters),
        }

    def invoke(self, arguments: Mapping[str, Any]) -> str:
        validate_arguments(self.parameters, arguments)
        return envelope(self.name, self.run(dict(arguments)))

    @abstractmethod
    def run(self, arguments: dict[str, Any]) -> str:
        """Execute the tool and return a string observation."""
