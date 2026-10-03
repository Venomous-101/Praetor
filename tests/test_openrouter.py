import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from praetor.llm.base import Message
from praetor.llm.openrouter import OpenRouterProvider
from praetor.types import ToolCall

TOOLS = [
    {
        "name": "python",
        "description": "Run sandboxed python code.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    }
]


def fake_response(body: dict) -> mock.MagicMock:
    response = mock.MagicMock()
    response.read.return_value = json.dumps(body).encode("utf-8")
    response.__enter__.return_value = response  # `with urlopen(...) as r` yields r
    return response


class OpenRouterProviderTests(unittest.TestCase):
    def test_missing_key_raises(self):
        with mock.patch.dict(os.environ, {"PRAETOR_OPENROUTER_KEY": ""}):
            provider = OpenRouterProvider()
            with self.assertRaises(RuntimeError):
                provider.complete([Message(role="user", content="hi")], [])

    def test_tool_calls_are_parsed(self):
        body = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "python",
                                    "arguments": json.dumps(
                                        {"code": "print(2 + 2)"}
                                    ),
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        provider = OpenRouterProvider(api_key="k")
        with mock.patch("praetor.llm.openrouter.urllib.request.urlopen") as urlopen:
            urlopen.return_value = fake_response(body)
            turn = provider.complete(
                [Message(role="user", content="compute")], TOOLS
            )
        self.assertEqual(turn.provider, "openrouter")
        self.assertEqual(len(turn.tool_calls), 1)
        call = turn.tool_calls[0]
        self.assertEqual(call.id, "call_1")
        self.assertEqual(call.name, "python")
        self.assertEqual(call.arguments, {"code": "print(2 + 2)"})
        self.assertEqual(turn.usage["prompt_tokens"], 10)
        self.assertEqual(turn.usage["completion_tokens"], 5)

    def test_request_uses_openai_wire_format(self):
        provider = OpenRouterProvider(api_key="k", model="test-model")
        with mock.patch("praetor.llm.openrouter.urllib.request.urlopen") as urlopen:
            urlopen.return_value = fake_response(
                {"choices": [{"message": {"content": "ok"}}]}
            )
            turn = provider.complete([Message(role="user", content="hi")], TOOLS)
        self.assertEqual(turn.content, "ok")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, provider.url + "/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer k")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["tools"][0]["type"], "function")
        self.assertEqual(payload["tools"][0]["function"]["name"], "python")
        self.assertEqual(payload["tool_choice"], "auto")

    def test_assistant_tool_history_is_rendered(self):
        provider = OpenRouterProvider(api_key="k")
        history = [
            Message(role="user", content="go"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1", name="python", arguments={"code": "print(1)"}
                    )
                ],
            ),
            Message(role="tool", content="1", tool_call_id="call_1"),
        ]
        with mock.patch("praetor.llm.openrouter.urllib.request.urlopen") as urlopen:
            urlopen.return_value = fake_response(
                {"choices": [{"message": {"content": "done"}}]}
            )
            provider.complete(history, [])
        payload = json.loads(urlopen.call_args[0][0].data.decode("utf-8"))
        assistant = payload["messages"][1]
        self.assertEqual(assistant["role"], "assistant")
        self.assertEqual(assistant["tool_calls"][0]["function"]["name"], "python")
        self.assertEqual(
            json.loads(assistant["tool_calls"][0]["function"]["arguments"]),
            {"code": "print(1)"},
        )
        tool_message = payload["messages"][2]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(tool_message["tool_call_id"], "call_1")

    def test_http_error_becomes_runtime_error(self):
        provider = OpenRouterProvider(api_key="k")
        with mock.patch("praetor.llm.openrouter.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = OSError("connection refused")
            with self.assertRaises(RuntimeError):
                provider.complete([Message(role="user", content="hi")], [])

    def test_http_error_body_is_included(self):
        provider = OpenRouterProvider(api_key="k")
        error = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"error": {"message": "No endpoints found"}}'),
        )
        with mock.patch("praetor.llm.openrouter.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = error
            with self.assertRaises(RuntimeError) as ctx:
                provider.complete([Message(role="user", content="hi")], [])
        self.assertIn("404", str(ctx.exception))
        self.assertIn("No endpoints found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
