"""Execution-based evaluation harness.

A benchmark score in Praetor is never a model's opinion. A task passes
only if its verifier, executing real code against real state, says so.
pass^k requires all k trials to succeed (reliability, the tau-bench
notion); pass@k requires at least one success.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from praetor.runtime.agent import Agent
from praetor.types import AgentResult, RunStatus


@dataclass
class TaskOutcome:
    """Everything a verifier needs to judge one trial."""

    task: "Task"
    result: AgentResult
    env: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    name: str
    prompt: str
    verify: Callable[[TaskOutcome], bool]
    description: str = ""


@dataclass
class TaskReport:
    task: str
    trials: int
    successes: int
    pass_all: bool
    pass_any: bool
    mean_steps: float
    mean_elapsed_s: float
    failures: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serializable report for storage, comparison, and CI artifacts."""
        return {
            "task": self.task,
            "trials": self.trials,
            "successes": self.successes,
            "pass_all": self.pass_all,
            "pass_any": self.pass_any,
            "pass_rate": self.pass_rate,
            "mean_steps": self.mean_steps,
            "mean_elapsed_s": self.mean_elapsed_s,
            "failures": list(self.failures),
        }


@dataclass
class SuiteReport:
    tasks: list[TaskReport] = field(default_factory=list)

    @property
    def pass_hat_k(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(1 for t in self.tasks if t.pass_all) / len(self.tasks)

    @property
    def pass_at_k(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(1 for t in self.tasks if t.pass_any) / len(self.tasks)

    def to_dict(self) -> dict[str, Any]:
        """Serializable suite verdicts (pass^k and pass@k included)."""
        return {
            "tasks": [task.to_dict() for task in self.tasks],
            "pass^k": self.pass_hat_k,
            "pass@k": self.pass_at_k,
        }

    def table(self) -> str:
        header = f"{'task':<22}{'trials':>7}{'pass':>6}{'pass^k':>8}{'mean steps':>12}"
        lines = [header, "-" * len(header)]
        for t in self.tasks:
            lines.append(
                f"{t.task:<22}{t.trials:>7}{t.successes:>6}"
                f"{'yes' if t.pass_all else 'no':>8}{t.mean_steps:>12.1f}"
            )
        lines.append("")
        lines.append("suite pass^k: " + format(self.pass_hat_k, ".0%") + "   pass@k: " + format(self.pass_at_k, ".0%"))
        return chr(10).join(lines)


class EvalHarness:
    """Runs tasks k times against fresh agents; verdicts come from verifiers."""

    def __init__(self, trials: int = 3) -> None:
        if trials < 1:
            raise ValueError("trials must be >= 1")
        self.trials = trials

    def run_task(
        self,
        make_agent: Callable[[], Agent],
        task: Task,
        env: dict[str, Any] | None = None,
    ) -> TaskReport:
        successes = 0
        steps: list[int] = []
        elapsed: list[float] = []
        failures: list[str] = []
        for _ in range(self.trials):
            result = make_agent().run(task.prompt)
            outcome = TaskOutcome(task=task, result=result, env=env or {})
            if result.status == RunStatus.OK and task.verify(outcome):
                successes += 1
            else:
                failures.append(result.status.value)
            steps.append(result.tool_calls)
            elapsed.append(result.elapsed_s)
        return TaskReport(
            task=task.name,
            trials=self.trials,
            successes=successes,
            pass_all=successes == self.trials,
            pass_any=successes > 0,
            mean_steps=sum(steps) / self.trials,
            mean_elapsed_s=sum(elapsed) / self.trials,
            failures=failures,
        )

    def run_suite(self, make_agent: Callable[[], Agent], tasks: list[Task]) -> SuiteReport:
        reports = [self.run_task(make_agent, task) for task in tasks]
        return SuiteReport(tasks=reports)
