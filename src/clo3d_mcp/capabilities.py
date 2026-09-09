"""Additional MCP tools for complete live API discovery and desktop fallback."""
import json
from pathlib import Path
import anyio


async def runtime_call(call, bridge_dir, operation, **params):
    source = (
        'import sys, importlib\n'
        f'p = {str(bridge_dir)!r}\n'
        'if p not in sys.path: sys.path.insert(0, p)\n'
        'import runtime_api\n'
        f'result = runtime_api.{operation}(**json.loads({json.dumps(params)!r}))'
    )
    result = await call('exec', {'code': source})
    return result['value']


def register(server, call, bridge_dir):
    async def runtime(operation, **params):
        return await runtime_call(call, bridge_dir, operation, **params)

    @server.tool()
    async def clo_api_catalog(query: str = '', module: str = '', offset: int = 0, limit: int = 100) -> dict:
        """Discover functions, types and constants in the RUNNING CLO version. Paged; no API functions are executed. Search names and docstrings. Modules include rest_api and ApiTypes. Follow next_offset for full coverage."""
        return await runtime('catalog', query=query, module=module, offset=offset, limit=limit)

    @server.tool()
    async def clo_api_describe(name: str) -> dict:
        """Live docstring/overloads and class fields for a qualified name, e.g. pattern_api.GetPatternCount or ApiTypes.ImportExportOption. Documents the running version."""
        return await runtime('describe', name=name)

    @server.tool()
    async def clo_api_call(name: str, args: list | None = None, kwargs: dict | None = None) -> dict:
        """Call any public function discovered in clo_api_catalog, or read a constant. Read its live documentation first. JSON supports {$type:'ApiTypes.TypeName',args:[],fields:{...}}, {$enum:'ApiTypes.Enum.Member'}, and {$handle:'id'}. Non-JSON return objects get session handles. A false result is NOT success. Never retry a timed-out mutation blindly; inspect scene/UI first. Use checkpoint_save before risky scene edits."""
        return {'name': name, 'value': await runtime('invoke', name=name, args=args, kwargs=kwargs)}

    @server.tool()
    async def clo_api_release(handles: list[str]) -> dict:
        """Release native API object handles when finished; handles expire when CLO restarts."""
        return await runtime('release', handles=handles)

    @server.tool()
    async def clo_control_guide() -> dict:
        """Routing guide for CLO functions absent from the API, including desktop prerequisites and verification."""
        return {
            'route': ['Search clo_api_catalog and inspect clo_api_describe.', 'Use a high-level tool or clo_api_call for supported operations.', 'For UI-only features, inspect clo_ui_state and clo_ui_screenshot, then use clo_ui_action.', 'Inspect the new state after EACH UI action and verify the intended result. Never infer success from input delivery.'],
            'codex_desktop': 'The connected Computer Use tool can control /Applications/CLO.app directly, with accessibility elements, screenshots, click, drag, scroll, text and keyboard shortcuts. Prefer it when available.',
            'standalone_mcp': 'Install the macos extra for native accessibility and input. Grant Accessibility and Screen Recording to the MCP host in macOS settings. UI tools run locally on the Mac hosting this server; they do not expose a network listener.',
            'limits': 'API presence is not proof that every overload works. UI availability depends on selection, mode, dialogs and license. No exhaustive guarantee of every CLO function. Do not replay an API failure through UI without checking whether it already changed the scene.',
        }

    from .desktop import Desktop
    desktop = Desktop()
    ui_lock = anyio.Lock()

    @server.tool()
    async def clo_ui_state(max_nodes: int = 1500, max_depth: int = 16) -> dict:
        """Inspect CLO accessibility hierarchy, menus, dialogs, values and supported actions. Returns a snapshot token; use it for the next UI action. No bridge needed. Requires macos extra and Accessibility permission."""
        async with ui_lock:
            return await anyio.to_thread.run_sync(lambda: desktop.state(max_nodes, max_depth))

    @server.tool()
    async def clo_ui_action(snapshot: str, action: str, element: int | None = None, value: str = '', x: float = 0, y: float = 0, end_x: float = 0, end_y: float = 0, keycode: int = 0, modifiers: list[str] | None = None) -> dict:
        """One CLO-only UI action followed by fresh state. action: press, set_value, ax_action (value must be an exposed action), click, right_click, double_click, drag, key, text, scroll (y is vertical wheel delta). Use observed element IDs or SCREEN coordinates from screenshot; key uses macOS virtual keycodes. modifiers: command,shift,option,control. Requires current snapshot token; state is consumed by an action. Never guess coordinates or perform blind action sequences."""
        async with ui_lock:
            return await anyio.to_thread.run_sync(lambda: desktop.action(snapshot, action, element, value, x, y, end_x, end_y, keycode, modifiers or []))

    @server.tool()
    async def clo_ui_screenshot() -> list:
        """Capture CLO's window as an image, including UI-only tools and dialogs; independent of API snapshots. Requires Screen Recording. Coordinates in clo_ui_state are screen points, not image pixels."""
        from mcp.server.mcpserver.utilities.types import Image
        async with ui_lock:
            data = await anyio.to_thread.run_sync(desktop.screenshot)
        return [Image(data=data, format='png').to_image_content()]
