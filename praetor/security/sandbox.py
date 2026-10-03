"""Sandboxed Python execution for untrusted agent code.

Threat model: agent-produced Python is untrusted input. This module is a
process-level barrier — isolation flags, scrubbed environment, rlimits,
wall-clock kill, bounded output — not a kernel container. For hostile
multi-tenant workloads, additionally use gVisor or Firecracker.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

MAX_OUTPUT_BYTES = 8192
MAX_CODE_BYTES = 65536


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool


def _clip(text: str) -> tuple[str, bool]:
    data = text.encode("utf-8", "replace")[:MAX_OUTPUT_BYTES]
    clipped = data.decode("utf-8", "ignore")
    return clipped, len(clipped) < len(text)


def _make_preexec(cpu_s: int, mem_mb: int):
    def _limits() -> None:  # pragma: no cover - runs in the child process
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
            mem_bytes = mem_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
            resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
        except Exception:
            os._exit(126)

    return _limits


def run_python_sandboxed(
    code: str,
    *,
    timeout_s: float = 10.0,
    cpu_s: int = 10,
    mem_mb: int = 512,
    workdir: str | None = None,
) -> SandboxResult:
    """Execute `code` with resource limits, a scrubbed env, and bounded output."""
    if not isinstance(code, str):
        raise TypeError("code must be a string")
    if len(code.encode("utf-8", "replace")) > MAX_CODE_BYTES:
        raise ValueError("source exceeds the maximum code size")

    cwd = workdir or tempfile.mkdtemp(prefix="praetor-sbx-")
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": cwd,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-"],
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=cwd,
            env=env,
            preexec_fn=_make_preexec(cpu_s, mem_mb) if os.name == "posix" else None,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, _ = _clip(exc.stdout or "")
        stderr, _ = _clip(exc.stderr or "")
        if not stderr:
            stderr = "sandbox: execution exceeded the wall-clock limit"
        return SandboxResult(False, -1, stdout, stderr, True, False)

    stdout, truncated_out = _clip(completed.stdout)
    stderr, truncated_err = _clip(completed.stderr)
    return SandboxResult(
        ok=completed.returncode == 0,
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
        truncated=truncated_out or truncated_err,
    )
