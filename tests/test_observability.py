import json
import os
import tempfile
import unittest

from praetor.eval.harness import EvalHarness
from praetor.eval.tasks import FIB_20, task_compute_fib
from praetor.llm.base import ModelTurn
from praetor.llm.scripted import ScriptedProvider
from praetor.observability import spans_from_result, summarize, trace_id, write_jsonl
from praetor.runtime.agent import Agent
from praetor.tools.exec import PythonTool
from praetor.types import RunStatus, ToolCall


def compute_turns():
    return [
        ModelTurn(tool_calls=(ToolCall(id="c1", name="python", arguments={"code": "print(2 + 2)"}),)),
        ModelTurn(content="4"),
    ]


class ObservabilityTests(unittest.TestCase):
    def test_summary_counts(self):
        result = Agent(ScriptedProvider(compute_turns()), tools=[PythonTool()]).run("compute")
        summary = summarize(result)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["tool_calls"], 1)
        self.assertEqual(summary["steps"], 1)
        self.assertEqual(summary["ok_steps"], 1)
        self.assertEqual(summary["failed_steps"], 0)

    def test_spans_follow_genai_shape(self):
        result = Agent(ScriptedProvider(compute_turns()), tools=[PythonTool()]).run("compute")
        spans = spans_from_result(result, model="scripted-demo")
        self.assertEqual(spans[0]["name"], "invoke_agent")
        self.assertEqual(spans[0]["attributes"]["gen_ai.operation.name"], "invoke_agent")
        self.assertEqual(spans[0]["attributes"]["gen_ai.request.model"], "scripted-demo")
        tool_spans = [s for s in spans if s["name"] == "execute_tool"]
        self.assertEqual(len(tool_spans), 1)
        self.assertEqual(tool_spans[0]["parent_id"], spans[0]["context"]["span_id"])
        self.assertEqual(tool_spans[0]["context"]["trace_id"], spans[0]["context"]["trace_id"])
        self.assertEqual(tool_spans[0]["attributes"]["gen_ai.tool.name"], "python")
        self.assertTrue(tool_spans[0]["attributes"]["praetor.step.ok"])

    def test_trace_id_is_content_addressed_and_deterministic(self):
        first = Agent(ScriptedProvider(compute_turns()), tools=[PythonTool()]).run("compute")
        second = Agent(ScriptedProvider(compute_turns()), tools=[PythonTool()]).run("compute")
        self.assertEqual(trace_id(first), trace_id(second))

    def test_usage_is_aggregated_and_mapped(self):
        turns = [
            ModelTurn(
                tool_calls=(ToolCall(id="c1", name="python", arguments={"code": "print(1)"}),),
                usage={"prompt_tokens": 10, "completion_tokens": 2},
            ),
            ModelTurn(content="done", usage={"prompt_tokens": 5, "completion_tokens": 1}),
        ]
        result = Agent(ScriptedProvider(turns), tools=[PythonTool()]).run("job")
        self.assertEqual(result.usage, {"prompt_tokens": 15, "completion_tokens": 3})
        spans = spans_from_result(result)
        self.assertEqual(spans[0]["attributes"]["gen_ai.usage.prompt_tokens"], 15)
        self.assertEqual(spans[0]["attributes"]["gen_ai.usage.completion_tokens"], 3)

    def test_result_to_dict_is_payload_free(self):
        result = Agent(ScriptedProvider(compute_turns()), tools=[PythonTool()]).run("compute")
        data = result.to_dict()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["answer"], "4")
        for step in data["steps"]:
            self.assertNotIn("output", step)
            self.assertIn("arguments", step)

    def test_jsonl_export_roundtrips(self):
        result = Agent(ScriptedProvider(compute_turns()), tools=[PythonTool()]).run("compute")
        spans = spans_from_result(result)
        handle = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        path = handle.name
        handle.close()
        try:
            written = write_jsonl(path, spans)
            self.assertEqual(written, len(spans))
            with open(path, "r", encoding="utf-8") as stream:
                lines = [line for line in stream if line.strip()]
            self.assertEqual(len(lines), len(spans))
            for line in lines:
                self.assertIsInstance(json.loads(line), dict)
        finally:
            os.unlink(path)

    def test_suite_report_serialization(self):
        def make_agent():
            turns = [
                ModelTurn(
                    tool_calls=(
                        ToolCall(
                            id="c1",
                            name="python",
                            arguments={
                                "code": "a, b = 0, 1" + chr(10) + "for _ in range(20):" + chr(10) + "    a, b = b, a + b" + chr(10) + "print(a)"
                            },
                        ),
                    )
                ),
                ModelTurn(content=FIB_20),
            ]
            return Agent(ScriptedProvider(turns), tools=[PythonTool()])

        report = EvalHarness(trials=2).run_suite(make_agent, [task_compute_fib()])
        data = report.to_dict()
        self.assertEqual(data["tasks"][0]["trials"], 2)
        self.assertEqual(data["tasks"][0]["successes"], 2)
        self.assertEqual(data["pass^k"], 1.0)
        self.assertEqual(data["pass@k"], 1.0)


if __name__ == "__main__":
    unittest.main()
