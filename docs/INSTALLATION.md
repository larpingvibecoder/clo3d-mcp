# Install CLO MCP on a Mac

This guide uses the source release and `uv`, a tool that installs Python and the package dependencies for you. You do not need to understand Python to follow the setup. Instructions were prepared for the experimental v0.1.0-alpha.1 release.

## 1. Check what you need

- A Mac with a licensed, working CLO installation. The development environment used CLO 2026.1.224. Other CLO versions are unverified.
- A local MCP-compatible assistant, such as Codex, able to launch a command on this Mac.
- An internet connection for the initial Python/dependency installation.
- Your own CLO avatar/fabric library for workflows using those assets.

The server needs an external Python 3.11+ environment. CLO has its own embedded Python; **do not install the server dependencies into CLO's embedded Python**.

## 2. Download the code

On the project's GitHub page, open **Releases**, choose `v0.1.0-alpha.1`, and download `clo3d-mcp-v0.1.0-alpha.1.zip`. Double-click it in Finder. The extracted folder contains `README.md`, `pyproject.toml`, `src`, `bridge`, and other folders.

Move it somewhere permanent, for example a `Developer` folder inside your home folder. Avoid moving it after configuring your assistant: the configuration refers to this location.

The `.whl` and `.tar.gz` files are for Python packaging workflows. Beginners should use the ZIP above. Downloading a ZIP from the main branch is also possible, but the main branch can change after a release.

## 3. Install uv

Open **Terminal** using Spotlight. If you already use Homebrew, run:

```sh
brew install uv
```

Otherwise follow the [official uv installation page](https://docs.astral.sh/uv/getting-started/installation/). Its macOS installer command is:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen Terminal, then run `uv --version`. A version number means uv is available. If the command is not found, finish the PATH instructions shown by its installer.

## 4. Open the project folder in Terminal

Type `cd ` with a space after it. Drag the extracted `clo3d-mcp` folder from Finder into Terminal, then press Return. This inserts the actual path, including escaped spaces.

Run these commands one at a time:

```sh
uv sync --no-editable --python 3.12 --locked
uv run --no-editable python scripts/print_setup.py
```

The first command creates a `.venv` folder and installs the locked dependencies plus a normal copy of this package. `--no-editable` makes startup independent of development path hooks. Use it on the `uv run` commands too. After editing source code, rerun sync with `--reinstall-package clo3d-mcp`. The second prints setup instructions tailored to this exact installation. Keep that Terminal output available for the next two steps.

Do not use `pip install clo3d-mcp` as a substitute: this release does not claim ownership of, or publication to, a PyPI project with that name. Install from this source checkout or its attached wheel.

## 5. Register the launcher inside CLO

1. Open CLO and log in. Save your current project.
2. If an older bridge is running, stop it using `clo_stop_bridge` first. Wait for its script to finish. Do not launch a second Python script while a bridge is serving.
3. Open CLO's **Edit > Python Script** editor.
4. Copy the one-line command printed under **CLO registration** in Step 4 into the editor and run it. It starts with `import utility_api; utility_api.RegisterPythonScript(...)`.
5. Look for **Plugins > start_bridge**. Menu naming can vary with the CLO version. If registration is unavailable, the helper's **Direct CLO startup alternative** runs the launcher from the editor instead.
6. Start the bridge **once**. Either click that registered menu item or run the direct-start line; do not do both.

The bridge is a running Python loop, not a script that exits immediately. That is expected. CLO should remain interactive while waiting for commands. **Do not press Run repeatedly.** The launcher has a duplicate-start check, but that cannot guarantee protection against every native CLO re-entry crash.

If CLO reports `QCoreApplication::processEvents not found`, this version's Qt event pump is unsupported. The bridge deliberately stops; see troubleshooting.

## 6. Connect your assistant

### Codex CLI

Copy and run the exact command printed under **Codex CLI registration** by the helper in Step 4. It has this shape:

```sh
codex mcp add clo3d -- "/absolute/path/to/clo3d-mcp/.venv/bin/python" -m clo3d_mcp.server
```

The path above is illustrative; use your generated command. Then run `codex mcp list` and restart/reconnect the client if necessary. If `codex` is not on your PATH, use your local client's MCP configuration UI or follow the official [Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). Codex supports local stdio server configuration; the generated command uses that connection type.

For long simulations, the client may time out before CLO finishes. In the existing `[mcp_servers.clo3d]` section of `~/.codex/config.toml`, `tool_timeout_sec = 600` can allow more time. This does not cancel a stuck native call. See the same official MCP guide for configuration details.

Do not register a second server under the same name if you already have `clo3d`. Inspect the existing entry and update it deliberately. A saved setup for a different checkout may otherwise keep using old code.

### Other clients with MCP JSON configuration

Copy the helper's **Generic MCP JSON** into the MCP configuration your client documents. Merge the `clo3d` entry into an existing `mcpServers` object instead of replacing the whole file. Do not paste shell quotes inside the JSON `command` value.

```json
{
  "mcpServers": {
    "clo3d": {
      "command": "/absolute/path/to/clo3d-mcp/.venv/bin/python",
      "args": ["-m", "clo3d_mcp.server"]
    }
  }
}
```

Restart/reconnect that client. A browser-only or remotely hosted assistant cannot reach this local bridge just by being given `localhost:5077`; the MCP process must run on your Mac.

## 7. Verify the connection without changing a garment

Ask the assistant:

> Call `clo_status`. If connected, call `scene_info`. Report the CLO version and current project without modifying anything.

Success means `bridge: up`, your CLO version, and sensible scene information. Seeing a list of tools alone only confirms that the MCP server starts; it does not prove the bridge is connected.

Try an offline preview next:

> Use `garment_plan_preview` for a knee-length A-line dress. Keep `use_scene_measurements` false and show the plan without building it.

For a first live edit, work on a duplicate project and ask for a checkpoint first. Review the returned snapshots after simulation.

## 8. Optional desktop tools

The main API workflow does not require this extra. To enable the experimental native macOS UI tools:

```sh
uv sync --no-editable --python 3.12 --locked --extra macos
```

macOS may require Accessibility and Screen Recording permission for the process/application hosting the server. The package does not grant those permissions automatically. This backend is not comprehensively tested; use API tools first.

## Every session / stopping / upgrading

Open CLO, start the bridge once, and verify `clo_status`. To stop it, ask for `clo_stop_bridge`. This should free the Python editor while leaving CLO open. If the bridge is idle but unreachable, creating `~/.clo3d-mcp/bridge.stop` requests a graceful stop; it cannot interrupt a hung native call.

Before upgrading: save the CLO project, stop the old bridge, update this checkout or extract the new release, run `uv sync --no-editable --python 3.12 --locked`, regenerate setup, and update any changed paths. Restart the assistant and start the new bridge once.

## Advanced configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `CLO_MCP_HOST` | `127.0.0.1` | Local loopback only; network hosts are rejected |
| `CLO_MCP_PORT` | `5077` | Must match in the external server and embedded bridge |
| `CLO_MCP_STATE` | `~/.clo3d-mcp` | Status, log, snapshots, caches, checkpoints; use the same absolute path on both sides |
| `CLO_APP_PATH` | `/Applications/CLO.app` | App launch and optional desktop targeting |
| `CLO_MCP_ASSETS` | `~/Documents/clo/CLO Assets` | Fallback asset folder; the live CLO asset folder is preferred |

Environment variables in your assistant configuration affect the external server only. For bridge variables, set `os.environ[...]` in CLO's Python editor before the launch line. Leave defaults alone for a normal single-instance installation.
