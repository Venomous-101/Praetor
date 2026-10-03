"""OpenTelemetry GenAI-aligned trace export (stdlib only).

Praetor emits structured span records whose names and attributes follow
the OpenTelemetry GenAI semantic conventions — an `invoke_agent` root
span with one `execute_tool` child per executed step, carrying
`gen_ai.*` attributes. Traces export as JSONL and can be ingested by any
OTel-compatible backend (Langfuse, Arize Phoenix, SigNoz, ...) after a
trivial JSON -> OTLP conversion step. Trace ids are content-addressed:
identical runs produce identical ids, which keeps traces as reproducible
as the runs themselves.

Deliberately NOT included: raw tool outputs and prompts. The audit view
records what was called and how it ended — never payload bytes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from praetor.types import AgentResult

GEN_AI_SYSTEM = "praetor"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(result: AgentResult) -> dict[str, Any]:
    """Timing-free canonical form: two identical runs hash identically."""
    return {
        "status": result.status.value,
        "answer": result.answer,
        "tool_calls": result.tool_calls,
        "steps": [
            {
                "index": step.index,
                "tool": step.tool_call.name,
                "arguments": dict(step.tool_call.arguments),
                "ok": step.result.ok,
                "error": step.result.error,
            }
            for step in result.steps
        ],
        "usage": dict(result.usage) if result.usage else None,
        "errors": list(result.errors),
    }


def trace_id(result: AgentResult) -> str:
    """Deterministic, content-addressed trace id (32 hex chars)."""
    return _sha(json.dumps(_canonical(result), sort_keys=True))[:32]


def spans_from_result(
    result: AgentResult, *, model: str | None = None
) -> list[dict[str, Any]]:
    """Build an OTel GenAI-shaped span tree from one audited run."""
    tid = trace_id(result)
    root_span_id = _sha(tid + ":root")[:16]
    base_nano = int((result.started_at or 0.0) * 1_000_000_000)

    root_attributes: dict[str, Any] = {
        "gen_ai.system": GEN_AI_SYSTEM,
        "gen_ai.operation.name": "invoke_agent",
        "praetor.run.status": result.status.value,
        "praetor.tool_calls": result.tool_calls,
        "praetor.audit_events": len(result.errors),
    }
    if model is not None:
        root_attributes["gen_ai.request.model"] = model
    if result.usage:
        for key, value in result.usage.items():
            root_attributes["gen_ai.usage." + str(key)] = value

    spans: list[dict[str, Any]] = [
        {
            "name": "invoke_agent",
            "context": {"trace_id": tid, "span_id": root_span_id},
            "parent_id": None,
            "start_time_unix_nano": base_nano,
            "end_time_unix_nano": base_nano + int(result.elapsed_s * 1_000_000_000),
            "attributes": root_attributes,
        }
    ]

    offset_nano = 0
    for step in result.steps:
        span_id = _sha(tid + ":step:" + str(step.index))[:16]
        duration_nano = int(step.duration_s * 1_000_000_000)
        attributes: dict[str, Any] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": step.tool_call.name,
            "praetor.step.ok": step.result.ok,
            "praetor.step.output_chars": len(step.result.output),
        }
        if step.result.error is not None:
            attributes["praetor.step.error"] = step.result.error
        spans.append(
            {
                "name": "execute_tool",
                "context": {"trace_id": tid, "span_id": span_id},
                "parent_id": root_span_id,
                "start_time_unix_nano": base_nano + offset_nano,
                "end_time_unix_nano": base_nano + offset_nano + duration_nano,
                "attributes": attributes,
            }
        )
        offset_nano += duration_nano
    return spans


def write_jsonl(path: str, spans: list[dict[str, Any]]) -> int:
    """Write one span per line; returns the number of spans written."""
    with open(path, "w", encoding="utf-8") as handle:
        for span in spans:
            handle.write(json.dumps(span, sort_keys=True) + chr(10))
    return len(spans)


def summarize(result: AgentResult) -> dict[str, Any]:
    """Compact health summary of one run."""
    ok_steps = sum(1 for step in result.steps if step.result.ok)
    return {
        "status": result.status.value,
        "tool_calls": result.tool_calls,
        "steps": len(result.steps),
        "ok_steps": ok_steps,
        "failed_steps": len(result.steps) - ok_steps,
        "elapsed_s": round(result.elapsed_s, 6),
        "audit_events": len(result.errors),
        "usage": dict(result.usage) if result.usage else None,
    }
