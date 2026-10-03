# Contributing

Praetor values small, auditable diffs over feature velocity.

- Every behavior change ships with a test. Security-sensitive changes must include a test that fails without the defense and passes with it.
- Keep the runtime dependency-free; anything that needs a third-party package belongs in an optional extra.
- Benchmark claims must be reproducible: include the exact command, environment, and model. No fabricated numbers.
- Run the suite before pushing:

```bash
python -m unittest discover -s tests -v
```

Security reports go through [SECURITY.md](SECURITY.md), not public issues.
