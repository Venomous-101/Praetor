# Security Policy

## Threat model

Praetor treats **model output, tool arguments, and tool results as untrusted input.** The agent loop is designed so that nothing executes unless it passes validation, policy, and integrity checks first.

## What v0.1 enforces

- Default-deny tool allowlists with per-tool and total call budgets
- Strict schema validation; unknown argument names are rejected
- Tool spec fingerprinting; tampered metadata aborts the run
- Workspace confinement for filesystem tools (no traversal, no absolute escapes)
- Sandboxed Python execution: isolation flags, scrubbed environment, rlimits, wall-clock kill, bounded output
- Untrusted-data envelope and injection-marker tripwires on tool observations
- CI secret scan; zero runtime dependencies to reduce supply-chain risk

## What v0.1 does NOT claim

- The sandbox is process-level, not a kernel container; network egress is not blocked at syscall level yet.
- Injection detection is marker-based, not a classifier.
- Defense in depth means untrusted code should still run inside an OS-level sandbox (gVisor, Firecracker) in hostile environments.

## Reporting a vulnerability

Do **not** open a public issue for vulnerabilities. Contact the maintainer through their GitHub profile (https://github.com/Venomous-101). Please include reproduction steps and, if possible, a failing test. Reports are acknowledged within 7 days.
