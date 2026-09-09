# Security and trust model

CLO MCP is a local development tool for a trusted single-user machine. `clo_run_python` intentionally executes Python inside CLO with the operating-system permissions of that application. Structured API tools can modify, delete, import, and save project content. The optional desktop tools can send input to CLO.

The TCP bridge binds only to `127.0.0.1`/`localhost` and rejects network hosts. It has **no authentication or encryption**. Other local processes, and potentially other users on the same machine, can connect to it. Loopback binding does not provide an authorization boundary. Do not port-forward, tunnel, expose it to a network, or use it on an untrusted shared host.

Use a trusted MCP client, retain its approval controls, review generated code, and run the bridge only when needed. This release is not sandboxed, multi-tenant, or suitable as a hosted service. Do not connect an untrusted automated agent.

The bridge/server communicate locally, but tool output, screenshots, file paths, and project data may be sent onward by your AI client according to that client's settings. Logs, caches, snapshots, and checkpoints are stored in `~/.clo3d-mcp` unless configured otherwise. Do not publish that directory.

Report vulnerabilities through the repository's private vulnerability reporting feature if the maintainer has enabled it. Do not put credentials, private files, or sensitive reproduction data into a public issue. There is no promised security response SLA for this experimental project.
