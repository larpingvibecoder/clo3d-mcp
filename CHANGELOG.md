# Changelog

## Unreleased

### Windows support

- Bridge: locate `QCoreApplication::processEvents` in the already-loaded `Qt6Core.dll`/`Qt5Core.dll` using MSVC symbol names (macOS/Linux lookup unchanged).
- Bridge: call Qt through `ctypes.PyDLL` on Windows so the GIL stays held. CLO runs Python inside Qt event handlers, and with the GIL released (`CDLL`) the first live test crashed with an access violation reading `0x10` after about 20 s of serving.
- Bridge: if the event pump raises (native fault), log it, record `pump_error` in the status file and stop instead of pumping again.
- Bridge: bind the port with `SO_EXCLUSIVEADDRUSE` on Windows so a second bridge or another program cannot share it.
- Server: Windows defaults for `CLO_APP_PATH` (`Program Files\CLO*\CLO_Standalone*.exe`) and `CLO_MCP_ASSETS` (`C:\Users\Public\Documents\CLO\CLO Assets`); `tasklist` instead of `pgrep`; `clo_launch` starts the CLO executable detached from the MCP stdio pipes.
- Desktop `clo_ui_*` tools remain macOS only and return a clear error on Windows.
- Setup helper prints Windows-quoted commands; CI runs offline tests on `windows-latest`; documentation covers Windows setup.

## 0.1.0-alpha.1 — 2026-09-09

First packaged public pre-release of the CLO-only integration. Python package version: `0.1.0a1`.

### Included

- 48 MCP tools covering scene inspection, patterns, sewing, fabrics, simulation, snapshots, checkpoints, drafting, live API access, and optional macOS UI control.
- Parametric starting patterns for dresses, tops, and skirts.
- Local stdio MCP server with a bridge running on CLO's main thread.
- MIT license, setup helper, beginner installation/publishing guides, issue templates, CI checks, and release packaging.

### Release preparation fixes

- Removed the creator's hard-coded launcher and test paths.
- Included bridge resources in the wheel; supported source and installed package layouts.
- Made default garment preview offline; live measurements require an explicit option and an existing avatar.
- Replaced copied API reference data with live search and documentation lookup.
- Matched configurable state directory between server and bridge; honored custom app path in desktop discovery.
- Rejected non-loopback network hosts, malformed request shapes, and oversized buffered requests.
- Added a duplicate-start launcher check, bounded socket writes, and refusal to start without the Qt event pump.
- Prevented raw Python expressions from being retried when the called function itself raises SyntaxError.
- Added regression tests and isolated wheel/MCP startup verification.

### Known limits

- Alpha software: native CLO functions may crash or hang; no claim that all historical crashes are fixed.
- Live development baseline is CLO 2026.1.224/macOS. Windows and other CLO builds are unverified.
- Optional desktop fallback is not comprehensively validated live.
- No authentication on the local bridge; trusted local single-user use only.
- No bundled CLO assets, Blender extension, inZOI assets, automatic game-ready exports, or production-fit guarantee.
