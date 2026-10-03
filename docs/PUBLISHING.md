# Publishing praetor-agent to PyPI

Praetor publishes to PyPI automatically using **trusted publishing**: PyPI verifies the workflow's identity via OIDC, so there are no passwords, tokens, or secrets stored anywhere in this repository.

## One-time setup (about 5 minutes)

1. Create a PyPI account at <https://pypi.org/account/register/> and verify your email.
2. Enable two-factor authentication on the account (PyPI requires it for publishing).
3. Go to <https://pypi.org/manage/account/publishing/> and add a **pending publisher**:
   - PyPI project name: `praetor-agent`
   - Owner: `Venomous-101`
   - Repository: `Praetor`
   - Workflow name: `pypi-publish.yml`
   - Environment name: leave blank (this workflow does not use an environment)
4. Done. The name is now reserved for this repository.

## Publishing a release

1. Make sure `version` in `pyproject.toml` and `__version__` in `praetor/__init__.py` match.
2. Publish a GitHub release (for example tag `v0.3.0` on `main`).
3. The `Publish to PyPI` workflow builds the sdist and wheel and uploads them automatically.
4. Users can then install with:

```bash
pip install praetor-agent
```

## Notes

- The first publish creates the project on PyPI; after that, only strictly increasing versions are accepted.
- Publishing is tied to GitHub releases, so every PyPI version maps to a tagged, reviewed commit.
- If a release's publish fails, fix the workflow, delete the release (before the version is ever uploaded), and publish again. Once a version is live on PyPI it can never be reused.
