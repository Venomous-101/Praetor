"""Deterministic replay provider for reproducible tests and benchmarks.

Every Praetor benchmark that runs in CI uses this provider (or a local
Ollama one): no cloud APIs, no non-determinism, no fabricated results.
"""
from __future__ import annotations

from praetor.llm.base import Message, ModelTurn


class ScriptedProvider:
    """Replays a fixed script of turns and refuses to improvise."""

    def __init__(self, turns: list[ModelTurn]) -> None:
        if not turns:
            raise ValueError("script must contain at least one turn")
        self._turns = list(turns)
        self._index = 0

    @property
    def exhausted(self) -> bool:
        return self._index >= len(self._turns)

    def complete(self, messages: list[Message], tools: list[dict]) -> ModelTurn:
        if self.exhausted:
            raise RuntimeError(
                "script exhausted: the agent iterated beyond the scripted turns"
            )
        turn = self._turns[self._index]
        self._index += 1
        return ModelTurn(
            content=turn.content,
            tool_calls=turn.tool_calls,
            usage=turn.usage,
            provider="scripted",
        )
