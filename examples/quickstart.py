"""Minimal end-to-end example with the deterministic scripted provider.

Runs:  python examples/quickstart.py
"""
from praetor.llm.base import ModelTurn
from praetor.llm.scripted import ScriptedProvider
from praetor.runtime.agent import Agent
from praetor.tools.exec import PythonTool
from praetor.types import ToolCall

CODE = """
a, b = 0, 1
for _ in range(20):
    a, b = b, a + b
print(a)
"""


def main() -> None:
    script = [
        ModelTurn(tool_calls=(ToolCall(id="c1", name="python", arguments={"code": CODE}),)),
        ModelTurn(content="6765"),
    ]
    agent = Agent(ScriptedProvider(script), tools=[PythonTool()])
    result = agent.run("Compute the 20th Fibonacci number, then reply with only the number.")
    print("status     :", result.status.value)
    print("answer     :", result.answer)
    print("tool calls :", result.tool_calls)
    print("elapsed    :", round(result.elapsed_s, 3), "s")
    print("steps:")
    for step in result.steps:
        print("  -", step.tool_call.name, "->", step.result.output.split(chr(10))[0])
    if result.errors:
        print("audit notes:", result.errors)


if __name__ == "__main__":
    main()
