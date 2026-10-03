# Changelog

All notable changes to Praetor are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-10-03

### Added

- **OpenRouter provider** (`praetor.llm.openrouter`, stdlib-only): connect any cloud model through OpenRouter — including free endpoints — or any OpenAI-compatible API by pointing `PRAETOR_OPENROUTER_URL` at it. The API key is read from `PRAETOR_OPENROUTER_KEY` and never logged, stored, or handed to tools. Six unit tests cover the wire format with fully mocked HTTP (no network in CI).
- **`examples/security_drill.py`**: a live pentest of the security layer. Five drills attack the five guarantees (default-deny policy, sandbox containment, injection detection, workspace confinement, audit trail) and print PASS or FAIL from real executions on the host machine - no mocks, no scripted results.
- **`examples/ollama_agent.py`**: run Praetor against a real local model through Ollama; the model itself decides when to call the python tool, under full Praetor supervision.
- **`examples/openrouter_agent.py`**: same idea against a real cloud model via OpenRouter, free key included path.
- **PyPI publishing pipeline**: a trusted-publisher workflow (`.github/workflows/pypi-publish.yml`) builds and publishes the package to PyPI automatically whenever a GitHub release is published. No tokens in the repo; one-time setup is documented in `docs/PUBLISHING.md`.

### Fixed

- **Windows sandbox**: sandboxed Python execution crashed at startup with `Fatal Python error: _Py_HashRandomization_Init` because the scrubbed environment dropped `SystemRoot`, which the Windows CryptoAPI requires to seed hash randomization. The sandbox now preserves the non-secret Windows system variables (`SystemRoot`, `SystemDrive`, `windir`, `ComSpec`, `PathExt`, `Temp`, `Tmp`) and rebuilds `PATH` from the interpreter location instead of the POSIX default. POSIX behavior is unchanged.
- **compute_fib verifier**: the built-in eval accepted the scripted answer even when the sandboxed `python` step had failed, so a broken execution could still count as a pass. The verifier now additionally requires a successful `python` step in the run audit trail, keeping the suite execution-honest.
- **OpenRouter default model**: the default slug pointed at a free endpoint that no longer exists on OpenRouter, so every real request failed with a bare HTTP 404. The provider now defaults to a current free model, and on HTTP errors it raises the status code plus the first 200 bytes of the response body, so failures are diagnosable at a glance.

### Changed

- Version bumped to 0.3.0. The PyPI distribution name is `praetor-agent` (the `praetor` name is already taken on PyPI); the import name stays `praetor`. CI now runs 57 tests per matrix entry.

## [0.2.0] - 2026-10-03

### Added

- **Observability module** (`praetor.observability`, stdlib-only): traces shaped after the OpenTelemetry GenAI semantic conventions — an `invoke_agent` root span with one `execute_tool` child per executed step, carrying `gen_ai.*` attributes (system, request model, tool name, token usage) plus Praetor audit attributes.
  - `spans_from_result()`, `write_jsonl()` (JSONL export for any OTel-compatible backend), and `summarize()` (compact run health view).
  - Deterministic, content-addressed trace ids: identical runs produce identical ids, so traces replay and diff like any artifact.
  - The audit view deliberately excludes raw tool outputs and prompts — what was called and how it ended, never payload bytes.
- **Token usage aggregation** across provider turns, recorded on `AgentResult.usage` and mapped onto `gen_ai.usage.*` attributes; `AgentResult.started_at` recorded for real span timing.
- **Payload-free `AgentResult.to_dict()`** — a serializable audit view of any run.
- **Eval report serialization**: `TaskReport.to_dict()` and `SuiteReport.to_dict()` (pass^k, pass@k, per-task rates) so benchmark results can be stored, diffed, and tracked.
- **Adversarial stress suite** (12 tests): path-traversal fuzzing (escape chains, absolute paths, URL-encoded and backslash payloads, NUL bytes, deep nesting, symlink escapes), size-cap enforcement, budget exhaustion under adversarial loops, injection storms flagged every time, and determinism checks.
- **CI install-smoke job**: installs the built package into a clean virtualenv on Python 3.11 and runs an end-to-end agent task — proving any developer can install and run Praetor out of the box.
- **`examples/export_trace.py`**: end-to-end observability demo.
- **Global-standard README**: badges, architecture, usage guides, observability and evaluation sections, security-model table, roadmap, citation.

### Fixed

- Stress test `test_deeply_nested_paths_cannot_escape` asserted the wrong OS behavior: on POSIX a path with more `..` than depth resolves above the workspace root, and `Workspace.resolve` correctly rejects it. Split into two cases (escape rejected; exact return-to-root allowed). The runtime was correct — the test assumption was not.

### Changed

- Version bumped to 0.2.0; CI now runs 49 tests per matrix entry.

## [0.1.0] - 2026-10-03

### Added

- **Core runtime**: agent loop with bounded memory, step and wall-clock budgets; graceful degradation (tool failures become observations; policy violations abort loudly).
- **Security layer**: default-deny tool policy with per-tool and total budgets; strict JSON-schema validation of every tool call; tool-spec integrity fingerprints (tampered tools are quarantined); workspace realpath confinement; subprocess sandbox for untrusted code (rlimits, scrubbed environment, wall-clock kill, bounded output); untrusted-data envelope and injection-marker flagging on all observations.
- **Tools**: filesystem (read/write/list, workspace-confined), sandboxed Python execution, tool registry.
- **LLM providers**: provider protocol; Ollama (local, no cloud keys); deterministic scripted replay for reproducible tests and benchmarks.
- **Execution-based eval harness**: tasks pass only when executable verifiers say so; pass^k (all k trials) and pass@k (at least one) metrics; built-in CI-safe task pack (fs write, computation, injection resistance).
- **Tests and CI**: 30 tests; GitHub Actions matrix (Python 3.10 / 3.12), secret scan, failure-to-issue reporting.

[0.3.0]: https://github.com/Venomous-101/Praetor/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Venomous-101/Praetor/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Venomous-101/Praetor/releases/tag/v0.1.0
