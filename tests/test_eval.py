import os
import tempfile
import unittest

from praetor.eval.harness import EvalHarness, SuiteReport, TaskReport
from praetor.eval.tasks import (
    INJECTION_PAYLOAD,
    REPORT_TEXT,
    DecoyTool,
    default_pack,
    task_injection_resistant,
)
from praetor.llm.base import ModelTurn
from praetor.llm.scripted import ScriptedProvider
from praetor.runtime.agent import Agent
from praetor.security.policy import ToolPolicy
from praetor.tools.exec import PythonTool
from praetor.tools.fs import ReadFileTool, Workspace, WriteFileTool
from praetor.types import ToolCall

FIB_CODE = """
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    print(a)

fib(20)
"""

UNIVERSAL_TURNS = [
    ModelTurn(
        tool_calls=(
            ToolCall(id="c1", name="write_file", arguments={"path": "report.md", "content": REPORT_TEXT}),
            ToolCall(id="c2", name="read_file", arguments={"path": "doc.md"}),
            ToolCall(id="c3", name="python", arguments={"code": FIB_CODE}),
        )
    ),
    ModelTurn(content="6765"),
]


class EvalSuiteTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="praetor-eval-")
        with open(os.path.join(self.root, "doc.md"), "w", encoding="utf-8") as handle:
            handle.write(INJECTION_PAYLOAD)
        self.decoy = DecoyTool()

    def make_agent(self):
        workspace = Workspace(self.root)
        return Agent(
            ScriptedProvider(list(UNIVERSAL_TURNS)),
            tools=[WriteFileTool(workspace), ReadFileTool(workspace), PythonTool()],
            policy=ToolPolicy(
                allowed_tools=frozenset({"write_file", "read_file", "python"})
            ),
        )

    def test_builtin_suite_passes(self):
        harness = EvalHarness(trials=2)
        report = harness.run_suite(self.make_agent, default_pack(self.root, self.decoy))
        self.assertAlmostEqual(report.pass_hat_k, 1.0)
        self.assertAlmostEqual(report.pass_at_k, 1.0)
        for task_report in report.tasks:
            self.assertEqual(task_report.successes, 2)
        self.assertEqual(self.decoy.called, 0)

    def test_hostile_agent_fails_injection_task(self):
        def hostile():
            workspace = Workspace(self.root)
            return Agent(
                ScriptedProvider(
                    [
                        ModelTurn(
                            tool_calls=(
                                ToolCall(id="c1", name="expose_secrets", arguments={}),
                            )
                        )
                    ]
                ),
                tools=[ReadFileTool(workspace), self.decoy],
                policy=ToolPolicy(allowed_tools=frozenset({"read_file"})),
            )

        report = EvalHarness(trials=1).run_task(hostile, task_injection_resistant(self.decoy))
        self.assertEqual(report.successes, 0)
        self.assertEqual(self.decoy.called, 0)

    def test_trials_must_be_positive(self):
        with self.assertRaises(ValueError):
            EvalHarness(trials=0)


class SuiteMathTests(unittest.TestCase):
    def test_pass_hat_k_and_pass_at_k(self):
        report = SuiteReport(
            tasks=[
                TaskReport(
                    task="a", trials=3, successes=3, pass_all=True,
                    pass_any=True, mean_steps=1.0, mean_elapsed_s=0.1,
                ),
                TaskReport(
                    task="b", trials=3, successes=1, pass_all=False,
                    pass_any=True, mean_steps=2.0, mean_elapsed_s=0.2,
                ),
            ]
        )
        self.assertAlmostEqual(report.pass_at_k, 1.0)
        self.assertAlmostEqual(report.pass_hat_k, 0.5)


if __name__ == "__main__":
    unittest.main()
