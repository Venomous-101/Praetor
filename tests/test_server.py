import json
import threading
import unittest
import urllib.error
import urllib.request

from praetor.llm.base import ModelTurn
from praetor.llm.scripted import ScriptedProvider
from praetor.server.app import build_server
from praetor.types import ToolCall


def scripted_factory(model=None):
    """Fresh scripted provider per run: compute via the python tool, then answer."""
    return ScriptedProvider(
        [
            ModelTurn(
                content=None,
                tool_calls=(
                    ToolCall(
                        id="call_1", name="python", arguments={"code": "print(2+2)"}
                    ),
                ),
            ),
            ModelTurn(
                content="4",
                usage={"prompt_tokens": 1, "completion_tokens": 1},
            ),
        ]
    )


class ConsoleServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = build_server(
            "127.0.0.1", 0, provider_factory=scripted_factory
        )
        cls.base = "http://127.0.0.1:" + str(cls.httpd.server_address[1])
        # No proxies for localhost in CI or developer machines.
        cls.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({})
        )
        cls.thread = threading.Thread(
            target=cls.httpd.serve_forever, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def api(self, path, data=None):
        request = urllib.request.Request(self.base + path, data=data)
        request.add_header("Content-Type", "application/json")
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def raw(self, path):
        with self.opener.open(self.base + path, timeout=30) as response:
            return (
                response.status,
                response.read().decode("utf-8"),
                response.headers.get("Content-Type", ""),
            )

    def test_health_reports_ok_and_version(self):
        status, body = self.api("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertIn("version", body)
        self.assertIn("model", body)
        self.assertIn("key_present", body)

    def test_run_executes_scripted_agent(self):
        status, body = self.api(
            "/api/run", data=json.dumps({"task": "compute 2+2"}).encode("utf-8")
        )
        self.assertEqual(status, 200)
        result = body["result"]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["answer"], "4")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["steps"][0]["tool"], "python")
        self.assertTrue(result["steps"][0]["ok"])
        self.assertTrue(body["workspace"])
        self.assertTrue(body["trace"])
        self.assertEqual(body["trace"][0]["name"], "invoke_agent")

    def test_run_rejects_missing_task(self):
        status, body = self.api(
            "/api/run", data=json.dumps({}).encode("utf-8")
        )
        self.assertEqual(status, 400)
        self.assertIn("task", body["error"])

    def test_run_rejects_non_string_task(self):
        status, body = self.api(
            "/api/run", data=json.dumps({"task": 42}).encode("utf-8")
        )
        self.assertEqual(status, 400)

    def test_run_rejects_invalid_json(self):
        status, body = self.api("/api/run", data=b'{"task": ')
        self.assertEqual(status, 400)
        self.assertIn("JSON", body["error"])

    def test_run_rejects_oversized_body(self):
        status, body = self.api("/api/run", data=b"x" * 70000)
        self.assertEqual(status, 413)
        self.assertIn("large", body["error"])

    def test_run_rejects_out_of_range_max_steps(self):
        status, body = self.api(
            "/api/run",
            data=json.dumps({"task": "hi", "max_steps": 99}).encode("utf-8"),
        )
        self.assertEqual(status, 400)
        self.assertIn("max_steps", body["error"])

    def test_unknown_paths_return_404(self):
        status, body = self.api("/api/nope")
        self.assertEqual(status, 404)
        status, _ = self.api("/../etc/passwd")
        self.assertEqual(status, 404)

    def test_console_page_and_assets_are_served(self):
        status, page, ctype = self.raw("/")
        self.assertEqual(status, 200)
        self.assertIn("Praetor Console", page)
        self.assertIn("text/html", ctype)
        status, _, ctype = self.raw("/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", ctype)
        status, _, ctype = self.raw("/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)


if __name__ == "__main__":
    unittest.main()
