"""Read-only end-to-end validation against running CLO; saves discovered inventory."""
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def main():
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    params = StdioServerParameters(command=sys.executable,args=['-m','clo3d_mcp.server'],env=env)
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as session:
            await session.initialize()
            result = await session.list_tools()
            print('MCP tools:',len(result.tools))
            async def call(name,args):
                res=await session.call_tool(name,args)
                if res.is_error: raise RuntimeError(str(res.content))
                return json.loads(res.content[0].text)
            print('Status:',await call('clo_status',{}))
            entries=[]
            offset=0
            while True:
                page=await call('clo_api_catalog',{'offset':offset,'limit':500})
                entries.extend(page['entries'])
                if page['next_offset'] is None: break
                offset=page['next_offset']
            out=root/'reports'
            out.mkdir(exist_ok=True)
            (out/'live-api-catalog.json').write_text(json.dumps({'entries':entries,'unavailable_modules':page['unavailable_modules']},indent=2))
            print('Live API entries:',len(entries),'unavailable:',page['unavailable_modules'])
            matches=[e['name'] for e in entries if e['name'].endswith('.GetPatternCount')]
            if matches:
                print('Read-only API call:',await call('clo_api_call',{'name':matches[0]}))
                print('Live doc:',str(await call('clo_api_describe',{'name':matches[0]}))[:500])
            print('Control guide:',bool(await call('clo_control_guide',{})))
asyncio.run(main())
