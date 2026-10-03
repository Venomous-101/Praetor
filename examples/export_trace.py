"""Export an audited run as OTel GenAI-aligned JSONL spans.

Runs:  python examples/export_trace.py
"""
from praetor.llm.base import ModelTurn
from praetor.llm.scripted import ScriptedProvider
from praetor.observability import spans_from_result, summarize, write_jsonl
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
    spans = spans_from_result(result, model="scripted-demo")
    print("summary:", summarize(result))
    for span in spans:
        print("span:", span["name"], "->", span["context"]["span_id"])
    print("wrote", write_jsonl("trace.jsonl", spans), "spans to trace.jsonl")


if __name__ == "__main__":
    main()
