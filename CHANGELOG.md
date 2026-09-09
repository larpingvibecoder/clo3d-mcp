# Changelog

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
