# Security Policy

## Threat model

Praetor treats **model output, tool arguments, and tool results as untrusted input.** The agent loop is designed so that nothing executes unless it passes validation, policy, and integrity checks first.

## What Praetor enforces

- Default-deny tool allowlists with per-tool and total call budgets
- Strict schema validation; unknown argument names are rejected
- Tool spec fingerprinting; tampered metadata aborts the run
- Workspace confinement for filesystem tools (no traversal, no absolute escapes)
- Sandboxed Python execution: isolation flags, scrubbed environment, rlimits, wall-clock kill, bounded output
- Untrusted-data envelope and injection-marker tripwires on tool observations
- Automatic, single bounded retry on upstream rate limits, with the upstream error body surfaced on failure
- API keys live only in the environment: never stored, logged, or handed to tools
- CI secret scan; zero runtime dependencies to reduce supply-chain risk

## Web Console security posture

The built-in console (`python -m praetor.server`) is a local tool, not a public service:

- Binds to 127.0.0.1 by default; never expose it to the internet
- Serves static files from a fixed whitelist — no filesystem browsing, no directory traversal
- Caps and validates every request body before any run
- Routes every run through the full security layer above
- The API key never reaches the browser: no storage, no logging, no echo in any response

## What Praetor does NOT claim

- The sandbox is process-level, not a kernel container; network egress is not blocked at syscall level yet.
- Injection detection is marker-based, not a classifier.
- The console has no authentication; anyone with access to the machine can start a run. That is acceptable only on a single-user machine.
- Defense in depth means untrusted code should still run inside an OS-level sandbox (gVisor, Firecracker) in hostile environments.

## Reporting a vulnerability

Do **not** open a public issue for vulnerabilities. Contact the maintainer through their GitHub profile (https://github.com/Venomous-101). Please include reproduction steps and, if possible, a failing test. Reports are acknowledged within 7 days.
