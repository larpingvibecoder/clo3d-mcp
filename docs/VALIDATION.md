# Validation record — v0.1.0-alpha.1

Prepared on 2026-09-09. This record distinguishes code/package checks from behavior inside a native CLO session.

## Completed locally

- Regression suite: **20 tests passed**, including the existing drafting, client, runtime API, and desktop unit checks plus release regressions for offline preview, missing-avatar handling, portable/duplicate launcher behavior, malformed requests, loopback host restrictions, refusal to start without a Qt event pump, and preventing repeated execution after a runtime SyntaxError.
- Real MCP stdio initialization and tool listing: **48 tools**. Default offline garment preview returned a plan without contacting CLO.
- Read-only live API check reached the existing bridge in **CLO 2026.1.224**, embedded Python **3.11.8**; catalogued **964 public entries** across seven modules; read `pattern_api.GetPatternCount` and its documentation.
- Release server environment: macOS arm64, external Python **3.12.13**, MCP SDK **2.2.0**.

## Distribution checks

Completed locally: the release workflow built a source distribution and a wheel, then ran `scripts/check_wheel.py`. That script verifies bridge resources and MIT licensing are in the wheel and installs the wheel into a fresh environment in a directory containing spaces. It then initializes MCP and runs the offline preview from outside the source checkout.

A package-content scan excludes local environments, runtime state, proprietary assets, copied vendor reference data, and the original machine-specific launch paths. The ZIP is assembled from a source allowlist rather than copying the whole workspace.

## Not verified / not implied

- The live check used the **already-running development bridge**, not a fresh launch of this revised release bridge. The new startup safeguards have automated tests but need an additional fresh-session CLO check.
- No live garment mutation was performed as part of release validation. The current garment project was preserved.
- Native macOS UI tools have unit coverage but no comprehensive end-to-end validation here.
- CI configuration is supplied; a GitHub-hosted CI run cannot be claimed until the repository is pushed and that run finishes.
- Other CLO builds, Windows bridge behavior, and exhaustive API overloads are unverified.
- No production-pattern, fit, stability, or game-export certification is implied.

## Reproduce checks

```sh
uv sync --no-editable --python 3.12 --locked
uv run --no-editable pytest -q
uv run --no-editable python tests/smoke_stdio.py
uv build
uv run --no-editable python scripts/check_wheel.py
```

For a separate read-only integration check with CLO and a bridge already running:

```sh
uv run --no-editable python tests/verify_live.py
```

This writes a local API inventory to `reports/`, which is ignored by Git and excluded from the release. Do not publish raw logs or inventories without reviewing their contents.
