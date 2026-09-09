# Troubleshooting and crash recovery

## Bridge down

CLO must be open, logged in, and running the bridge once. Restarting the assistant only restarts the external MCP server. Ask `clo_status` for the current launch path. Check that the path exists and points to this installation.

## CLO crashes when I start the bridge

Repeatedly running scripts while CLO's Python event loop is already serving has caused crashes during development. Save work, restart CLO, and launch the bridge once. Do not press Run again because the script appears busy. After a crash, inspect status and logs before retrying any edit.

The release adds duplicate-launch protection and refuses startup when the Qt event pump is unavailable. These are safeguards, **not a fix for all observed CLO crashes**. Native API calls can terminate the application without a Python traceback.

## CLO freezes or a command times out

Do not immediately repeat the command. It may have completed, partially changed the project, or still be running. If CLO responds, inspect the scene and save a separate copy or restore a checkpoint. A stop request cannot pre-empt a native API function that is hung. If CLO must be force-quit, unsaved work may be lost; reopen the latest saved project/checkpoint after restarting.

## Qt event pump not found

The bridge now logs `unsupported_qt` and stops instead of starting a loop that freezes the UI. This means the native Qt symbols expected by this bridge are absent in that CLO build/platform. Report the CLO build and macOS version. Do not remove this check as an installation workaround.

## Address already in use

Another bridge or process is using port 5077. Do not repeatedly launch a second bridge. Use `clo_status`, stop the existing bridge if it belongs to your session, and check the log. Advanced users can choose another port, but must configure both ends identically.

## No matching avatar / no fabric found

Library aliases like Mia and Luka refer to files that may not be installed on another user's machine. Use `avatar_list` or `fabric_library` to inspect the installed assets. Load your own licensed avatar/fabric in CLO, or provide its absolute path. inZOI bodies and CLO assets are not shipped here.

## My garment is translucent / colors differ

Fabric presets may carry texture and opacity maps that affect the final appearance. Inspect the actual material and its maps. The high-level fabric workflow clears some unintended maps, but raw API calls and imported materials can differ. Lighting, colorways, texture maps, and display mode all affect the result. Do not assume that a successful color call guarantees the desired rendered material.

## Fit, clipping, or unexpected drape

Preview uses standard default measurements unless `use_scene_measurements=True`. The live builder may fall back to approximate or default measurements if avatar measurement fails. Check its reported measurement source. Drafting, arrangement points, and seam operations are version-sensitive. Manual fitting and visual checks remain necessary. A 3D mesh import can have no editable 2D patterns.

## Optional desktop tools fail

Install the `macos` extra, grant the required macOS permissions to the correct host, and obtain a fresh `clo_ui_state` before an action. UI snapshot tokens expire and are consumed by an action. On Retina displays, screen points and screenshot pixels can differ. Do not guess canvas coordinates.

## Useful local files

Default location: `~/.clo3d-mcp/`.

- `bridge.log`: bridge startup, command loading, and other diagnostic messages.
- `bridge_status.json`: last reported state; a file left after a crash may be stale.
- `checkpoints/`: saved CLO project checkpoints.
- `snapshots/`: exported preview images.
- `measurements/` and `calibration/`: cached avatar data.

On macOS, application crash reports can be found through Console or `~/Library/Logs/DiagnosticReports/`. Logs and reports may contain usernames, project paths, or garment details. Redact those before attaching them to a public issue.

## A useful bug report

Include the release version, macOS version/chip, CLO exact build, external Python version, client name, the tool and arguments used, expected vs actual behavior, and a short redacted log excerpt. State whether CLO crashed, froze, returned an error, or changed the scene despite reporting failure. Start with the smallest reproducible example on a disposable project.
