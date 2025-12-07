import asyncio
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# --- CONFIGURATION ---
WINDOWS_IP = "192.168.1.15"  # <--- CHANGE THIS to your Windows IP
PORT = 8000
# ---------------------

mcp = FastMCP("Mac-to-Windows-Bridge")

async def forward_request(tool_name: str, args: dict) -> Any:
    """
    Forwards request to Windows with a 20-minute timeout.
    """
    url = f"http://{WINDOWS_IP}:{PORT}/sse"
    
    # Set connect and read timeouts to 1200s (20 mins)
    async with sse_client(url, timeout=1200) as (read, write):
        async with ClientSession(read, write, read_timeout=1200) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=args)
            return result.content[0].text

@mcp.tool()
async def win_exec(command: str) -> str:
    """Executes a command on the remote Windows Machine."""
    try:
        return await forward_request("exec_persistent", {"command": command})
    except Exception as e:
        return f"Connection Failed: {str(e)}"

@mcp.tool()
async def win_read(directory: str, pattern: str = "*") -> Dict[str, str]:
    """Reads files on the remote Windows Machine."""
    try:
        # We need to manually parse the JSON result from the string response
        import json
        res = await forward_request("bulk_read", {"directory": directory, "pattern": pattern})
        
        # If server returns a stringified dict, parse it
        if isinstance(res, str):
            try: 
                return json.loads(res)
            except: 
                return {"error": "Failed to parse JSON", "raw": res}
        return res
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run()
