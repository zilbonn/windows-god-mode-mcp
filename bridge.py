import asyncio
import base64
import json
from datetime import timedelta
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# --- CONFIGURATION ---
WINDOWS_IP = "192.168.1.15"  # <--- CHANGE THIS to your Windows IP
PORT = 8000
TIMEOUT = 1200  # 20 minutes
# ---------------------

mcp = FastMCP("Mac-to-Windows-Bridge")


async def forward_request(tool_name: str, args: dict) -> str:
    """
    Forwards request to Windows with robust timeout handling.
    Returns raw string response.
    """
    url = f"http://{WINDOWS_IP}:{PORT}/sse"

    try:
        async with sse_client(url, timeout=TIMEOUT) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=TIMEOUT)) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)
                return result.content[0].text
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Connection failed: {str(e)}",
            "output": "",
            "stderr": ""
        })


def parse_response(response: str) -> dict:
    """Parse JSON response, handle errors gracefully."""
    try:
        return json.loads(response)
    except:
        return {
            "success": False,
            "error": "Failed to parse response",
            "output": response,
            "stderr": ""
        }


@mcp.tool()
async def win_exec(command: str) -> str:
    """
    Execute a PowerShell command on the remote Windows machine.

    For simple commands, pass directly.
    For complex commands with quotes/special chars, use win_exec_b64.

    Returns JSON: {"success": bool, "output": str, "stderr": str|null, "error": str|null}
    """
    return await forward_request("win_exec", {"command": command})


@mcp.tool()
async def win_exec_b64(command_b64: str) -> str:
    """
    Execute a BASE64-ENCODED PowerShell command on Windows.

    THIS IS THE MOST RELIABLE METHOD for complex commands with:
    - Quotes (single or double)
    - Special characters ($, `, {, }, etc.)
    - Multi-line scripts
    - Pipelines with complex filters

    Steps:
    1. Write your PowerShell command
    2. Encode to base64 (UTF-8)
    3. Pass the base64 string here

    Returns JSON: {"success": bool, "output": str, "stderr": str|null, "error": str|null}
    """
    return await forward_request("win_exec_b64", {"command_b64": command_b64})


@mcp.tool()
async def win_exec_complex(command: str) -> str:
    """
    Execute a complex PowerShell command by auto-encoding to base64.

    Use this for commands that have:
    - Quotes
    - Special characters
    - Multi-line content
    - Complex pipelines

    The command is automatically base64-encoded before sending.

    Returns JSON: {"success": bool, "output": str, "stderr": str|null, "error": str|null}
    """
    # Auto-encode to base64 for reliability
    command_b64 = base64.b64encode(command.encode('utf-8')).decode('ascii')
    return await forward_request("win_exec_b64", {"command_b64": command_b64})


@mcp.tool()
async def win_write_file(path: str, content: str) -> str:
    """
    Write content to a file on Windows.

    Args:
        path: Full Windows path (e.g., C:\\temp\\script.ps1)
        content: File content as plain text (will be auto-encoded)

    Returns JSON with success status.
    """
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
    return await forward_request("win_write_file", {"path": path, "content_b64": content_b64})


@mcp.tool()
async def win_read_file(path: str) -> str:
    """
    Read a text file from Windows.

    Args:
        path: Full Windows path

    Returns JSON with file content in 'output' field.
    """
    return await forward_request("win_read_file", {"path": path})


@mcp.tool()
async def win_read_file_b64(path: str) -> str:
    """
    Read a file from Windows as base64.
    Use for binary files or files with special characters.

    Args:
        path: Full Windows path

    Returns JSON with base64 content in 'output' field.
    """
    return await forward_request("win_read_file_b64", {"path": path})


@mcp.tool()
async def win_read(directory: str, pattern: str = "*") -> str:
    """
    Read multiple files from a Windows directory.

    Args:
        directory: Directory path
        pattern: Glob pattern (default: *)

    Returns JSON dictionary: {"filepath": "content", ...}
    """
    return await forward_request("bulk_read", {"directory": directory, "pattern": pattern})


@mcp.tool()
async def win_shell_status() -> str:
    """
    Check if the Windows shell is alive and responsive.
    Returns computer name and username.
    """
    return await forward_request("win_shell_status", {})


@mcp.tool()
async def win_restart_shell() -> str:
    """
    Force restart the PowerShell session on Windows.
    Use if commands are hanging or shell becomes unresponsive.
    """
    return await forward_request("win_restart_shell", {})


if __name__ == "__main__":
    print("=" * 60)
    print("  Mac-to-Windows Bridge")
    print(f"  Forwarding to: {WINDOWS_IP}:{PORT}")
    print("=" * 60)
    print("\nTools available:")
    print("  - win_exec(command)         : Simple commands")
    print("  - win_exec_b64(command_b64) : Base64-encoded commands")
    print("  - win_exec_complex(command) : Auto-encode complex commands")
    print("  - win_write_file(path, content)")
    print("  - win_read_file(path)")
    print("  - win_read_file_b64(path)")
    print("  - win_read(directory, pattern)")
    print("  - win_shell_status()")
    print("  - win_restart_shell()")
    print("=" * 60)
    mcp.run()
