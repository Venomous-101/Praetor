"""Web Console backend: a stdlib-only localhost server.

The console is the user-ready face of Praetor: a browser UI that runs
supervised agent tasks against a real model, with zero dependencies and
zero key handling in the browser.

Security posture:
- binds 127.0.0.1 by default; it is a local tool, not a public service
- the API key comes from the environment and never leaves the process;
  it is not stored, logged, or returned by any endpoint
- request bodies are capped; task prompts are validated before any run
- static files are served from a fixed whitelist, never from disk paths
- every run goes through the full Praetor security layer: default-deny
  policy, schema validation, integrity guard, sandboxed execution, and
  the untrusted-data envelope on every observation
"""
from __future__ import annotations

import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlsplit

import praetor
from praetor.llm.base import LLMProvider
from praetor.llm.openrouter import DEFAULT_MODEL, OpenRouterProvider
from praetor.observability.trace import spans_from_result
from praetor.runtime.agent import Agent, Budget
from praetor.security.policy import ToolPolicy
from praetor.tools.exec import PythonTool
from praetor.tools.fs import ListFilesTool, ReadFileTool, Workspace, WriteFileTool

MAX_REQUEST_BYTES = 65536
MAX_TASK_CHARS = 8000
DEFAULT_PORT = 8756

# Fixed static whitelist: no filesystem browsing, no directory traversal.
_STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}

TOOL_ALLOWLIST = frozenset({"python", "write_file", "read_file", "list_files"})


def default_provider_factory(model: str | None = None) -> LLMProvider:
    """Cloud model via OpenRouter; the key comes from the environment."""
    return OpenRouterProvider(model=model)


def make_handler(
    provider_factory: Callable[..., LLMProvider] | None = None,
    static_dir: str | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler wired to a provider factory and static dir."""
    factory = provider_factory or default_provider_factory
    static = static_dir or os.path.join(os.path.dirname(__file__), "static")

    class ConsoleHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "praetor-console/" + praetor.__version__

        def log_message(self, format, *args):  # noqa: A002
            """Keep test/CI output clean; the audit trail lives in results."""

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, name: str, content_type: str) -> None:
            try:
                with open(os.path.join(static, name), "rb") as handle:
                    body = handle.read()
            except OSError:
                self._send_json(404, {"error": "not found"})
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/api/health":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "version": praetor.__version__,
                        "model": os.environ.get("PRAETOR_OPENROUTER_MODEL")
                        or DEFAULT_MODEL,
                        "key_present": bool(
                            os.environ.get("PRAETOR_OPENROUTER_KEY")
                        ),
                    },
                )
                return
            entry = _STATIC_FILES.get(path)
            if entry is None:
                self._send_json(404, {"error": "not found"})
                return
            self._send_static(*entry)

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path != "/api/run":
                self._send_json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "invalid Content-Length header"})
                return
            if length < 0 or length > MAX_REQUEST_BYTES:
                self._send_json(413, {"error": "request body too large"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._send_json(400, {"error": "request body must be valid JSON"})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "request body must be a JSON object"})
                return

            task = payload.get("task")
            if not isinstance(task, str) or not task.strip():
                self._send_json(
                    400, {"error": "'task' must be a non-empty string"}
                )
                return
            if len(task) > MAX_TASK_CHARS:
                self._send_json(
                    400,
                    {
                        "error": "task exceeds "
                        + str(MAX_TASK_CHARS)
                        + " characters"
                    },
                )
                return
            model = payload.get("model")
            if model is not None and (
                not isinstance(model, str)
                or not model.strip()
                or len(model) > 200
            ):
                self._send_json(
                    400, {"error": "'model' must be a short non-empty string"}
                )
                return
            max_steps = payload.get("max_steps", 12)
            if (
                not isinstance(max_steps, int)
                or isinstance(max_steps, bool)
                or not 1 <= max_steps <= 16
            ):
                self._send_json(
                    400,
                    {"error": "'max_steps' must be an integer between 1 and 16"},
                )
                return

            model_choice = model or None
            work_dir = tempfile.mkdtemp(prefix="praetor-console-")
            workspace = Workspace(work_dir)
            agent = Agent(
                factory(model_choice),
                tools=[
                    PythonTool(),
                    WriteFileTool(workspace),
                    ReadFileTool(workspace),
                    ListFilesTool(workspace),
                ],
                policy=ToolPolicy(allowed_tools=TOOL_ALLOWLIST),
                budget=Budget(max_steps=max_steps, max_wallclock_s=120.0),
            )
            result = agent.run(task)
            self._send_json(
                200,
                {
                    "result": result.to_dict(),
                    "trace": spans_from_result(result, model=model_choice),
                    "workspace": work_dir,
                },
            )

    return ConsoleHandler


def build_server(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    provider_factory: Callable[..., LLMProvider] | None = None,
) -> ThreadingHTTPServer:
    """Create (but do not start) the console server."""
    return ThreadingHTTPServer((host, port), make_handler(provider_factory))


def serve(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    provider_factory: Callable[..., LLMProvider] | None = None,
) -> None:
    """Start the console and serve until interrupted."""
    httpd = build_server(host, port, provider_factory)
    print("Praetor Web Console: http://" + host + ":" + str(httpd.server_address[1]))
    print("Set PRAETOR_OPENROUTER_KEY before starting to connect a cloud model.")
    httpd.serve_forever()
