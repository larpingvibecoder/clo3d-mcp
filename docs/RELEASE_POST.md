# CLO MCP v0.1.0-alpha.1 — a local AI-assisted garment workflow for CLO

I'm sharing the first experimental release of **CLO MCP**, an independent integration that lets a local MCP-compatible AI assistant work with CLO through its Python API.

The idea is to make it easier to move between a design request and a result you can inspect: describe a change, let the assistant inspect the project and use the relevant tools, review the garment in CLO, and refine it. This can help with repetitive setup and edits while keeping the garment visible in the application where it is being made.

This release is **CLO-only**, uses the **MIT license**, and is intended for early testers on macOS. It requires your own CLO installation and an assistant that can run a local MCP server.

## What is included

The server exposes **48 MCP tools** across several workflows:

- **Project inspection:** examine the current scene, pattern pieces, avatars, fabrics, sewing information, and arrangement points.
- **Garment editing:** create or delete patterns, edit supported points/properties, sew pieces, apply fabrics, change colors, and assign texture maps.
- **Iteration:** simulate, inspect snapshots, save a checkpoint before a change, and restore a saved checkpoint when needed.
- **Drafting:** preview parametric patterns for dresses, tops, and skirts, then build a starting garment in CLO and refine it.
- **Live API discovery:** search the API exposed by the installed CLO version, inspect function documentation, and invoke supported functions with structured arguments.
- **Advanced control:** run Python inside CLO for operations that do not have a dedicated wrapper.
- **Optional macOS desktop fallback:** inspect accessibility controls, capture the CLO window, and perform UI actions where the API is insufficient. This part is especially experimental.

For example, you can ask the assistant to inspect the current project without changing it, preview a knee-length A-line dress, or save a checkpoint before changing a garment's fabric and showing front/back snapshots.

## How the connection works

There are two pieces. A Python MCP server runs on your Mac and communicates with your assistant over stdio. A separate bridge runs inside CLO and receives local commands on `127.0.0.1:5077`.

The bridge runs CLO API operations on the application's main thread and pumps its Qt event loop between requests. You start that bridge once per CLO session. The assistant's server and the bridge need to run on the same machine and account.

This is not a cloud rendering service or a standalone clothing generator. CLO remains responsible for its simulation, project data, and native API behavior.

## What changed for this first packaged release

The release preparation focused on making the existing integration usable outside the original development machine:

- The launcher no longer points to a personal folder.
- Bridge files are included in the installable Python package.
- A setup helper prints the actual paths and client configuration for your installation.
- Garment preview is offline by default, using clearly identified standard measurements. Measuring a live avatar is an explicit option.
- API reference lookup uses the running CLO installation instead of shipping a copied vendor documentation dump.
- Startup checks avoid a second launcher entry and refuse to start when the expected Qt event pump is unavailable.
- The bridge rejects non-loopback hosts, invalid request shapes, and oversized request buffers; socket writes have a timeout.
- Installation instructions, troubleshooting, beginner GitHub publishing steps, regression tests, and CI configuration are included.

## What has been tested

The release package has local automated regression checks, a real MCP stdio startup/preview test, and an isolated wheel installation check. A read-only integration check reached a running **CLO 2026.1.224** session and discovered **964 public API entries across seven modules**.

That inventory shows what the application exposes; it does not mean every function or overload has been exercised. The live check used the existing bridge session. Fresh launch of the revised bridge and comprehensive native UI testing remain unverified. The [validation record](VALIDATION.md) separates completed checks from remaining work.

## Please treat this as an alpha

CLO native calls can fail, hang, or crash the application. The safeguards added here do not fix every crash observed during development. Start on a duplicate project, keep checkpoints, and inspect the scene before retrying a timed-out change.

The drafting engine creates starting patterns. It does not guarantee exact reproduction from a photograph, production-ready construction, or a perfect fit on every avatar. Built-in drafting currently covers dresses, tops, and skirts. Imported mesh garments may have no editable 2D sewing patterns. Blender integration and automatic game-ready exports are outside this release.

The local bridge intentionally allows Python execution and has no authentication. Use it only with trusted local clients on a trusted machine; do not expose or tunnel its port. Your assistant may send tool outputs and screenshots to its AI provider under its own data settings.

## Try it and share useful feedback

Download `clo3d-mcp-v0.1.0-alpha.1.zip` from this release, extract it, and follow `docs/INSTALLATION.md`. The ZIP is the easiest starting point; the wheel and source archive are also provided for Python users.

Feedback on setup, specific CLO versions, pattern behavior, and reproducible failures is welcome. When reporting a bug, include your release version, macOS version/chip, CLO build, client, tool call, and a short redacted log excerpt. Please remove private paths and project information first.

CLO MCP is a community project, not an official CLO product. CLO software, avatars, fabrics, and other commercial assets are not bundled. The integration code is available under MIT so others can inspect it, adapt it, and contribute improvements.
