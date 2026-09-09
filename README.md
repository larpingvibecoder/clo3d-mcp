# CLO MCP

**Describe a garment change. Inspect the result in CLO. Keep editing.**

CLO MCP connects a local MCP-compatible AI assistant to CLO's Python API. It provides tools for inspecting a project, editing patterns, sewing, changing fabrics, simulating, taking snapshots, and saving checkpoints. It also includes an experimental parametric drafting engine for dresses, tops, and skirts.

**v0.1.0-alpha.1 · Experimental · macOS · MIT**

This is an independent community integration, not an official CLO product. You need your own licensed installation of CLO and a local MCP client. CLO, avatars, fabrics, commercial reference images, Blender, and inZOI assets are not included.

## Start here

- **Install and connect:** [Beginner setup guide](docs/INSTALLATION.md)
- **See what to ask:** [Example prompts](examples/PROMPTS.md)
- **Recover from errors:** [Troubleshooting](docs/TROUBLESHOOTING.md)
- **Understand the release:** [Release notes](docs/RELEASE_POST.md) and [validation record](docs/VALIDATION.md)
- **Publish your own copy:** [GitHub publishing guide](docs/GITHUB_GUIDE.md)

## What it can do

| Workflow | Tools / behavior |
| --- | --- |
| Inspect a project | Scene, pattern, fabric, avatar, sewing, and arrangement information |
| Edit garments | Create/delete patterns, edit points, configure supported pattern properties, sew pieces |
| Change materials | Apply locally installed fabrics, change color, assign texture maps |
| Review the result | Simulate, reset arrangement, export snapshots, inspect the 2D view |
| Save work | Save/open projects, export supported formats, save and restore checkpoints |
| Draft a starting point | Preview a dress/top/skirt plan offline, then build and refine it in CLO |
| Discover the installed API | Search live names and docstrings, inspect overloads, make structured API calls |
| Advanced operations | Execute Python inside CLO with `clo_run_python` |
| Optional Mac UI fallback | Accessibility inspection, screenshots, and input tools with separate permissions |

The drafting engine does **not** automatically recreate an arbitrary photograph, produce production-approved sewing patterns, or guarantee fit on every avatar. Its built-in garment categories are dresses, tops, and skirts; trousers/jorts need custom work. Mesh imports may appear in 3D without editable 2D sewing patterns. The UI fallback is experimental and has not received comprehensive live validation.

## Quick start for users familiar with Terminal

Download and extract the source release, open Terminal in its folder, then:

```sh
uv sync --no-editable --python 3.12 --locked
uv run --no-editable python scripts/print_setup.py
```

The helper prints the **correct paths for your machine**, a CLO registration command, a direct bridge-start command, a Codex CLI command, and generic MCP JSON. It does not edit settings or start applications. Follow [the full guide](docs/INSTALLATION.md) to use those outputs.

In CLO, start the bridge **once per session**. In the assistant, ask:

> Use `clo_status` and tell me whether the bridge is connected. Then inspect the current scene without changing it.

Start on a duplicate project. Keep tool approvals enabled in your MCP client. Read [the trust model](SECURITY.md): the bridge intentionally allows local code execution and is not a sandbox.

## Compatibility and evidence

The original integration has been used with **CLO 2026.1.224 on macOS**, whose embedded Python is 3.11. The release's external server is validated locally with Python 3.12. The package declares Python 3.11+; CI covers 3.11 and 3.12 on macOS and Linux for offline tests only. This is **not** a claim that CLO runs on Linux or that the bridge works on Windows.

The bridge pumps CLO's Qt event loop using native symbols. It now refuses to serve if it cannot find the event pump, rather than deliberately freezing the UI. Native CLO operations can still crash or hang the application. A failed or timed-out mutation may already have changed the scene: inspect before retrying.

See [VALIDATION.md](docs/VALIDATION.md) for what was actually checked and what remains unverified. This first release is a **pre-release**, not a stability guarantee.

## How it works

```text
Your local AI/MCP client
        | stdio (MCP)
        v
clo3d-mcp Python server
        | JSON lines over 127.0.0.1:5077
        v
Python bridge inside CLO, on its UI thread
        | CLO Python API
        v
Your CLO project
```

The client launches the server; you launch the bridge inside CLO. Both run on the same machine and account. No cloud bridge or public HTTP endpoint is provided. Tool responses and screenshots go to your MCP client, whose own AI-provider data policies still apply.

## Development

```sh
uv sync --no-editable --python 3.12 --locked
uv run --no-editable pytest -q
uv run --no-editable python tests/smoke_stdio.py
uv build
```

The smoke test initializes MCP and previews a garment without connecting to CLO. `tests/verify_live.py` is a separate, read-only API check requiring a running bridge. Do not run garment mutations against someone's active work as a test.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
