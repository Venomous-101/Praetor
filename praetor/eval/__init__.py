"""Execution-based evaluation: harness, verifiers, and the built-in task pack."""
from praetor.eval.harness import EvalHarness, SuiteReport, Task, TaskOutcome, TaskReport
from praetor.eval.tasks import (
    DecoyTool,
    INJECTION_PAYLOAD,
    REPORT_TEXT,
    default_pack,
    task_compute_fib,
    task_fs_write,
    task_injection_resistant,
)

__all__ = [
    "DecoyTool",
    "EvalHarness",
    "INJECTION_PAYLOAD",
    "REPORT_TEXT",
    "SuiteReport",
    "Task",
    "TaskOutcome",
    "TaskReport",
    "default_pack",
    "task_compute_fib",
    "task_fs_write",
    "task_injection_resistant",
]
