"""Run Praetor against a real cloud model via OpenRouter (free keys work).

Prerequisites:
    1. Create a free key at https://openrouter.ai/keys
    2. Set it in your environment (Windows cmd):
           set PRAETOR_OPENROUTER_KEY=<your key>
       (bash):
           export PRAETOR_OPENROUTER_KEY=<your key>

Runs:  python examples/openrouter_agent.py

No scripted provider: the real model decides on its own whether to
call the python tool, under full Praetor supervision. The default model
is a current free OpenRouter model; pass model= to choose any other.
"""
import os

from praetor.llm.openrouter import OpenRouterProvider
from praetor.runtime.agent import Agent
from praetor.tools.exec import PythonTool


def main() -> None:
    if not os.environ.get("PRAETOR_OPENROUTER_KEY"):
        print("Set PRAETOR_OPENROUTER_KEY first (free key: https://openrouter.ai/keys)")
        return
    provider = OpenRouterProvider()  # defaults to a current free model
    agent = Agent(provider, tools=[PythonTool()])
    result = agent.run(
        "Use the python tool to compute the 20th Fibonacci number, "
        "then reply with only the number."
    )
    print("status     :", result.status.value)
    print("answer     :", result.answer)
    print("tool calls :", result.tool_calls)
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


if __name__ == "__main__":
    main()
