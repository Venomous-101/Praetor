"""Bounded conversation memory.

The preamble (system prompt and initial task) stays pinned; the most
recent exchanges live in a fixed-size window so long tool chains cannot
grow the context without bound.
"""
from __future__ import annotations

from collections import deque

from praetor.llm.base import Message

DEFAULT_MAX_MESSAGES = 64


class BoundedHistory:
    def __init__(self, max_messages: int = DEFAULT_MAX_MESSAGES) -> None:
        if max_messages < 1:
            raise ValueError("max_messages must be >= 1")
        self._pinned: list[Message] = []
        self._recent: deque[Message] = deque(maxlen=max_messages)

    def append(self, message: Message) -> None:
        if not self._recent and message.role in ("system", "user") and not message.tool_calls:
            self._pinned.append(message)
            return
        self._recent.append(message)

    def messages(self) -> list[Message]:
        return self._pinned + list(self._recent)
