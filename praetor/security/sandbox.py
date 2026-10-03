"""Sandboxed Python execution for untrusted agent code.

Threat model: agent-produced Python is untrusted input. This module is a
process-level barrier — isolation flags, scrubbed environment, rlimits,
wall-clock kill, bounded output — not a kernel container. For hostile
multi-tenant workloads, additionally use gVisor or Firecracker.

Platform notes: POSIX applies rlimits via preexec. Windows has no
rlimits, so it relies on isolation flags, the scrubbed environment,
bounded output, and the wall-clock kill. The Windows environment keeps
the non-secret system variables (SystemRoot and friends) because the
CryptoAPI requires them to seed Python hash randomization — without
them, every child Python dies before executing a single line.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

MAX_OUTPUT_BYTES = 8192
MAX_CODE_BYTES = 65536

# Non-secret Windows system variables a child process needs to boot.
# Everything else from the user environment stays scrubbed.
WINDOWS_SYSTEM_VARS = (
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
)


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


def _build_env(cwd: str) -> dict[str, str]:
    """Minimal deterministic environment; user secrets never cross the barrier."""
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": cwd,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }
    if os.name == "nt":
        for name in WINDOWS_SYSTEM_VARS:
            value = os.environ.get(name)
            if value:
                env[name] = value
        # Rebuild PATH from the interpreter location and the system dirs;
        # the user's PATH (which may point at wrappers or shims) stays out.
        system_root = env.get("SYSTEMROOT", "C:" + chr(92) + "Windows")
        env["PATH"] = os.pathsep.join(
            [
                os.path.dirname(sys.executable),
                os.path.join(system_root, "System32"),
                system_root,
            ]
        )
    return env


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
    env = _build_env(cwd)
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
