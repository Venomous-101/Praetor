"""Run Praetor against a real local model via Ollama.

Prerequisites:
    1. Install Ollama from https://ollama.com
    2. Download a model:   ollama pull llama3.2:3b
       (use llama3.1 if your machine has 16 GB+ RAM)

Runs:  python examples/ollama_agent.py

This is the no-script test: there is no scripted provider here. The
real model reads the task, decides on its own whether to call the
python tool, and Praetor's security layer watches every step.
"""
from praetor.llm.ollama import OllamaProvider
from praetor.runtime.agent import Agent
from praetor.tools.exec import PythonTool


def main() -> None:
    provider = OllamaProvider(model="llama3.2:3b")
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


if __name__ == "__main__":
    main()
