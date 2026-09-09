# Contributing

This is an experimental macOS integration. Small, reproducible improvements to portability, error reporting, fitting, and stability are welcome.

1. Fork and clone the repository, create a branch, then run `uv sync --no-editable --python 3.12 --locked`.
2. Run `uv run --no-editable pytest -q` and `uv run --no-editable python tests/smoke_stdio.py` before and after the change.
3. For packaging changes, run `uv build` and verify a clean wheel install using `scripts/check_wheel.py` (see validation).
4. Keep tests that need CLO separate from offline tests. Never mutate a real user's current garment for automated testing.
5. Document the exact CLO version for any live check. API presence is not equivalent to successful behavior.
6. Open a pull request explaining the problem, behavior change, validation, and remaining limitations.

Do not commit a virtual environment, personal MCP configuration, logs, crash reports, generated projects, proprietary assets, or copied vendor documentation. The issue templates request environment details and redacted logs. A change to native event-loop integration needs live review in a disposable CLO session before being described as stable.

Keep the package version, `src/clo3d_mcp/__init__.py`, bridge version, release tag, changelog, and release instructions consistent. `0.1.0a1` is the Python package spelling; `v0.1.0-alpha.1` is the human-readable Git tag for this first pre-release.
