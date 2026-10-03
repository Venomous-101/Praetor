"""Run the built-in benchmark suite (deterministic, CI-safe).

Real-model benchmarking: point the agent factory at an OllamaProvider
instead; the tasks and verifiers are identical.

Runs:  python examples/run_benchmark.py
"""
import os
import tempfile

from praetor.eval.harness import EvalHarness
from praetor.eval.tasks import INJECTION_PAYLOAD, REPORT_TEXT, DecoyTool, default_pack
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


def make_agent(root: str) -> Agent:
    workspace = Workspace(root)
    turns = [
        ModelTurn(
            tool_calls=(
                ToolCall(id="c1", name="write_file", arguments={"path": "report.md", "content": REPORT_TEXT}),
                ToolCall(id="c2", name="read_file", arguments={"path": "doc.md"}),
                ToolCall(id="c3", name="python", arguments={"code": FIB_CODE}),
            )
        ),
        ModelTurn(content="6765"),
    ]
    return Agent(
        ScriptedProvider(turns),
        tools=[WriteFileTool(workspace), ReadFileTool(workspace), PythonTool()],
        policy=ToolPolicy(allowed_tools=frozenset({"write_file", "read_file", "python"})),
    )


def main() -> None:
    root = tempfile.mkdtemp(prefix="praetor-bench-")
    with open(os.path.join(root, "doc.md"), "w", encoding="utf-8") as handle:
        handle.write(INJECTION_PAYLOAD)
    decoy = DecoyTool()
    suite = default_pack(root, decoy)
    report = EvalHarness(trials=3).run_suite(lambda: make_agent(root), suite)
    print(report.table())
    print()
    print("decoy invocations (must be zero):", decoy.called)


if __name__ == "__main__":
    main()
