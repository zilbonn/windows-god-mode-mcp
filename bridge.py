#!/usr/bin/env python3
"""
Windows MCP Bridge - Stdio MCP client that forwards to Windows HTTP server
This runs on Mac and communicates with Claude Code via stdio MCP protocol.
"""

import json
import sys
import urllib.request
import urllib.error

# ============== CONFIGURATION ==============
WINDOWS_IP = "192.168.2.205"
WINDOWS_PORT = 8000
TIMEOUT = 300  # seconds
# ===========================================

WINDOWS_SERVER = f"http://{WINDOWS_IP}:{WINDOWS_PORT}"


def send_request(endpoint, method="GET", data=None):
    """Send HTTP request to Windows server"""
    url = f"{WINDOWS_SERVER}{endpoint}"
    try:
        if method == "POST" and data is not None:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
        else:
            req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Connection failed: {e}"}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_tool_call(tool_name, arguments):
    """Handle MCP tool calls by forwarding to Windows server"""

    if tool_name == "win_exec":
        cmd = arguments.get("command", "")
        timeout = arguments.get("timeout", 300)
        return send_request("/exec", "POST", {"cmd": cmd, "timeout": timeout})

    elif tool_name == "win_exec_b64":
        # Decode base64 command and execute
        import base64
        try:
            cmd = base64.b64decode(arguments.get("command_b64", "")).decode("utf-8")
            timeout = arguments.get("timeout", 300)
            return send_request("/exec", "POST", {"cmd": cmd, "timeout": timeout})
        except Exception as e:
            return {"success": False, "error": f"Base64 decode failed: {e}"}

    elif tool_name == "win_exec_complex":
        # Same as win_exec, for complex commands
        cmd = arguments.get("command", "")
        timeout = arguments.get("timeout", 300)
        return send_request("/exec", "POST", {"cmd": cmd, "timeout": timeout})

    elif tool_name == "win_powershell":
        cmd = arguments.get("command", "")
        timeout = arguments.get("timeout", 300)
        return send_request("/powershell", "POST", {"cmd": cmd, "timeout": timeout})

    elif tool_name == "win_read_file":
        path = arguments.get("path", "")
        binary = arguments.get("binary", False)
        return send_request("/read", "POST", {"path": path, "binary": binary})

    elif tool_name == "win_read_file_b64":
        path = arguments.get("path", "")
        return send_request("/read", "POST", {"path": path, "binary": True})

    elif tool_name == "win_write_file":
        path = arguments.get("path", "")
        content = arguments.get("content", "")
        binary = arguments.get("binary", False)
        return send_request("/write", "POST", {"path": path, "content": content, "binary": binary})

    elif tool_name == "win_read":
        directory = arguments.get("directory", ".")
        pattern = arguments.get("pattern", "*")
        # List directory, then read matching files
        ls_result = send_request("/ls", "POST", {"path": directory})
        if not ls_result.get("success"):
            return ls_result

        import fnmatch
        files = {}
        for item in ls_result.get("items", []):
            if item["type"] == "file" and fnmatch.fnmatch(item["name"], pattern):
                file_path = f"{directory}\\{item['name']}"
                read_result = send_request("/read", "POST", {"path": file_path})
                if read_result.get("success"):
                    files[file_path] = read_result.get("content", "")
                else:
                    files[file_path] = f"[Error: {read_result.get('error', 'unknown')}]"
        return {"success": True, "files": files}

    elif tool_name == "win_list_directory":
        path = arguments.get("path", ".")
        return send_request("/ls", "POST", {"path": path})

    elif tool_name == "win_download_file":
        url = arguments.get("url", "")
        dst = arguments.get("dst", "")
        return send_request("/download", "POST", {"url": url, "dst": dst})

    elif tool_name == "win_delete":
        path = arguments.get("path", "")
        return send_request("/delete", "POST", {"path": path})

    elif tool_name == "win_copy":
        src = arguments.get("src", "")
        dst = arguments.get("dst", "")
        return send_request("/copy", "POST", {"src": src, "dst": dst})

    elif tool_name == "win_move":
        src = arguments.get("src", "")
        dst = arguments.get("dst", "")
        return send_request("/move", "POST", {"src": src, "dst": dst})

    elif tool_name == "win_exists":
        path = arguments.get("path", "")
        return send_request("/exists", "POST", {"path": path})

    elif tool_name == "win_shell_status":
        return send_request("/health")

    elif tool_name == "win_restart_shell":
        # No actual restart needed for HTTP server
        return {"success": True, "message": "HTTP server does not require restart"}

    elif tool_name == "win_server_info":
        return send_request("/info")

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def get_tools():
    """Return available MCP tools"""
    return {
        "tools": [
            {
                "name": "win_exec",
                "description": "Execute a shell command (cmd.exe) on the remote Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "win_exec_b64",
                "description": "Execute a base64-encoded command on Windows. Use for commands with special characters.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command_b64": {"type": "string", "description": "Base64-encoded command"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300}
                    },
                    "required": ["command_b64"]
                }
            },
            {
                "name": "win_exec_complex",
                "description": "Execute a complex shell command on Windows. Same as win_exec but named for clarity.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "win_powershell",
                "description": "Execute a PowerShell command on the remote Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "PowerShell command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "win_read_file",
                "description": "Read a text file from the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Full Windows path to the file"},
                        "binary": {"type": "boolean", "description": "Read as binary (base64)", "default": False}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "win_read_file_b64",
                "description": "Read a file from Windows as base64. Use for binary files.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Full Windows path to the file"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "win_write_file",
                "description": "Write content to a file on the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Full Windows path for the file"},
                        "content": {"type": "string", "description": "Content to write"},
                        "binary": {"type": "boolean", "description": "Write as binary (content is base64)", "default": False}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "win_read",
                "description": "Read multiple files from a Windows directory matching a pattern",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Directory path"},
                        "pattern": {"type": "string", "description": "Glob pattern (e.g., *.txt)", "default": "*"}
                    },
                    "required": ["directory"]
                }
            },
            {
                "name": "win_list_directory",
                "description": "List directory contents on the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path", "default": "."}
                    }
                }
            },
            {
                "name": "win_download_file",
                "description": "Download a file from URL to the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to download from"},
                        "dst": {"type": "string", "description": "Destination path on Windows"}
                    },
                    "required": ["url", "dst"]
                }
            },
            {
                "name": "win_delete",
                "description": "Delete a file or directory on the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to delete"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "win_copy",
                "description": "Copy a file or directory on the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "src": {"type": "string", "description": "Source path"},
                        "dst": {"type": "string", "description": "Destination path"}
                    },
                    "required": ["src", "dst"]
                }
            },
            {
                "name": "win_move",
                "description": "Move a file or directory on the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "src": {"type": "string", "description": "Source path"},
                        "dst": {"type": "string", "description": "Destination path"}
                    },
                    "required": ["src", "dst"]
                }
            },
            {
                "name": "win_exists",
                "description": "Check if a path exists on the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to check"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "win_shell_status",
                "description": "Check the health of the Windows server connection",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "win_server_info",
                "description": "Get system information from the Windows machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "win_restart_shell",
                "description": "Placeholder for compatibility. HTTP server doesn't need restart.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    }


def main():
    """Main MCP server loop using stdio"""
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            method = request.get("method", "")
            req_id = request.get("id")
            params = request.get("params", {})

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "windows-god-mode", "version": "1.0.0"}
                    }
                }

            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": get_tools()
                }

            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = handle_tool_call(tool_name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                    }
                }

            elif method == "notifications/initialized":
                # No response needed for notifications
                continue

            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

            print(json.dumps(response), flush=True)

        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)}
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
