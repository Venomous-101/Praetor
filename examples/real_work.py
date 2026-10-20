"""A real multi-tool task: the model computes, then writes a report.

Prerequisites:
    1. Create a free key at https://openrouter.ai/keys
    2. Set it in your environment (Windows cmd):
           set PRAETOR_OPENROUTER_KEY=<your key>
       (bash):
           export PRAETOR_OPENROUTER_KEY=<your key>

Runs:  python examples/real_work.py

The task needs more than one tool: the model must compute with the
sandboxed python tool and then write a report into a real workspace
with the workspace-confined write_file tool. The model plans both
steps itself; Praetor supervises every call - allowlist policy, schema
validation, sandboxed execution, and a full audit trail.
"""
import os
import tempfile

from praetor.llm.openrouter import OpenRouterProvider
from praetor.runtime.agent import Agent, Budget
from praetor.security.policy import ToolPolicy
from praetor.tools.exec import PythonTool
from praetor.tools.fs import Workspace, WriteFileTool

TASK = (
    "Use the python tool to compute the 30th Fibonacci number, "
    "then use the write_file tool to save a short markdown report as "
    "report.md describing the result and how you computed it."
)


def main() -> None:
    if not os.environ.get("PRAETOR_OPENROUTER_KEY"):
        print("Set PRAETOR_OPENROUTER_KEY first (free key: https://openrouter.ai/keys)")
        return
    work_dir = tempfile.mkdtemp(prefix="praetor-work-")
    workspace = Workspace(work_dir)
    agent = Agent(
        OpenRouterProvider(),
        tools=[PythonTool(), WriteFileTool(workspace)],
        policy=ToolPolicy(allowed_tools=frozenset({"python", "write_file"})),
        budget=Budget(max_steps=12),
    )
    result = agent.run(TASK)
    print("status     :", result.status.value)
    print("answer     :", result.answer)
    print("workspace  :", work_dir)
    print("steps:")
    for step in result.steps:
        print(
            "  -",
            step.tool_call.name,
            "| ok:", step.result.ok,
            "| took", round(step.duration_s, 2), "s",
        )
    if result.errors:
        print("audit notes:", result.errors)
    if result.usage:
        print("token usage:", dict(result.usage))
    if result.status.value != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
