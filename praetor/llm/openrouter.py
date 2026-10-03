"""OpenAI-compatible provider, defaulting to OpenRouter.

OpenRouter (https://openrouter.ai) aggregates hundreds of models -
including free ones - behind a single OpenAI-style API. Because the
wire format is OpenAI-compatible, this provider also works with any
OpenAI-compatible endpoint by pointing PRAETOR_OPENROUTER_URL at it.

Security note: the API key is read from the environment (or passed
explicitly) and never stored, logged, or handed to tools. It stays
inside this process boundary.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from praetor.llm.base import LLMProvider, Message, ModelTurn
from praetor.types import ToolCall

DEFAULT_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct:free"


def _openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Render Praetor's conversation memory into the OpenAI chat format."""
    rendered: list[dict[str, Any]] = []
    for message in messages:
        entry: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.role == "assistant" and message.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(dict(call.arguments)),
                    },
                }
                for call in message.tool_calls
            ]
        if message.role == "tool":
            entry["tool_call_id"] = message.tool_call_id
        rendered.append(entry)
    return rendered


def _openai_tools(tools: list[dict]) -> list[dict[str, Any]]:
    """Praetor specs are flat; OpenAI wraps each spec in a function envelope."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": dict(spec["parameters"]),
            },
        }
        for spec in tools
    ]


class OpenRouterProvider(LLMProvider):
    """Talks to OpenRouter (or any OpenAI-compatible API) with stdlib HTTP."""

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        url: str | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self.url = (
            url or os.environ.get("PRAETOR_OPENROUTER_URL") or DEFAULT_URL
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("PRAETOR_OPENROUTER_KEY")
        self.timeout_s = timeout_s

    def complete(self, messages: list[Message], tools: list[dict]) -> ModelTurn:
        if not self._api_key:
            raise RuntimeError(
                "no API key: set PRAETOR_OPENROUTER_KEY"
                " (a free key works: https://openrouter.ai/keys)"
            )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": _openai_messages(messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = _openai_tools(tools)
            payload["tool_choice"] = "auto"
        request = urllib.request.Request(
            self.url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise RuntimeError("openrouter request failed: " + str(exc)) from exc

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(
                "openrouter returned no choices: " + json.dumps(data)[:200]
            )
        message = choices[0].get("message") or {}
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
        usage_raw = data.get("usage") or {}
        usage = None
        if usage_raw.get("prompt_tokens") is not None:
            usage = {
                "prompt_tokens": usage_raw.get("prompt_tokens"),
                "completion_tokens": usage_raw.get("completion_tokens"),
            }
        return ModelTurn(
            content=message.get("content") or None,
            tool_calls=tuple(calls),
            usage=usage,
            provider="openrouter",
        )
