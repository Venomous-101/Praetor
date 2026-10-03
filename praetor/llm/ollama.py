"""Local-first provider for Ollama (default: http://localhost:11434).

No cloud keys required. Set PRAETOR_OLLAMA_URL to override the endpoint.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from praetor.llm.base import LLMProvider, Message, ModelTurn
from praetor.types import ToolCall

DEFAULT_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """Talks to a local Ollama server with plain stdlib HTTP."""

    def __init__(
        self,
        model: str = "llama3.1",
        url: str | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.model = model
        self.url = (url or os.environ.get("PRAETOR_OLLAMA_URL") or DEFAULT_URL).rstrip("/")
        self.timeout_s = timeout_s

    def complete(self, messages: list[Message], tools: list[dict]) -> ModelTurn:
        payload = {
            "model": self.model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        request = urllib.request.Request(
            self.url + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(
                "ollama unavailable at " + self.url + ": " + str(exc)
            ) from exc

        message = data.get("message") or {}
        calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            calls.append(
                ToolCall(
                    id=raw.get("id") or ("call_" + str(len(calls))),
                    name=function.get("name", ""),
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
        usage = None
        if data.get("prompt_eval_count") is not None:
            usage = {
                "prompt_tokens": data.get("prompt_eval_count"),
                "completion_tokens": data.get("eval_count"),
            }
        return ModelTurn(
            content=message.get("content") or None,
            tool_calls=tuple(calls),
            usage=usage,
            provider="ollama",
        )
