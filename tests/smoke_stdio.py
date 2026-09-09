"""Offline MCP handshake and preview. Does not contact the live CLO bridge."""
import asyncio
import os
import sys
from pathlib import Path
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def main():
    env = dict(os.environ)
    params = StdioServerParameters(command=sys.executable, args=["-m", "clo3d_mcp.server"], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            registered = await s.list_tools()
            names = {t.name for t in registered.tools}
            assert {"clo_status", "garment_plan_preview", "clo_api_catalog", "clo_ui_state"} <= names
            res = await s.call_tool("garment_plan_preview", {"spec": {"silhouette": "slip", "length": "maxi"}})
            assert not res.is_error, res.content
            print(f"PASS: {len(names)} registered tools; offline garment preview succeeded")

if __name__ == "__main__":
    asyncio.run(main())
