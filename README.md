# Windows God Mode MCP

A simple MCP bridge that connects Claude Code to a remote Windows machine over HTTP.

Designed for security labs and red team workflows, this tool provides shell access to Windows from Claude Code with support for long-running commands (5 minute default timeout).

## Architecture

```
Claude Code (Mac/Linux)  <--stdio-->  bridge.py  <--HTTP-->  server.py (Windows)
```

- **server.py (Windows):** Simple HTTP server that executes commands and file operations.
- **bridge.py (Mac/Linux):** Stdio MCP client that forwards tool calls to the Windows server.

## Prerequisites

- **Windows Machine:** Python 3.8+
- **Mac/Linux Machine:** Python 3.8+, Claude Code CLI
- **Network:** Both machines on the same LAN. Port 8000 open on Windows.

## Installation

### 1. Windows Side

1. Copy `server.py` to the Windows machine.

2. Allow Port 8000 in Windows Firewall:
   ```powershell
   New-NetFirewallRule -DisplayName "MCP-Server" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```

3. Run the server:
   ```powershell
   python server.py
   ```

   You should see:
   ```
   ============================================================
     Windows God-Mode MCP Server
     Listening on 0.0.0.0:8000
   ============================================================
   ```

### 2. Mac/Linux Side (Bridge)

1. Edit `bridge.py` and set your Windows IP:
   ```python
   WINDOWS_IP = "192.168.x.x"  # Your Windows machine IP
   WINDOWS_PORT = 8000
   ```

2. Test connectivity:
   ```bash
   curl http://192.168.x.x:8000/health
   ```

### 3. Configure Claude Code

Add the bridge to your Claude Code MCP config (`~/.claude.json`):

```json
{
  "mcpServers": {
    "windows-dev": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/bridge.py"]
    }
  }
}
```

Or use the CLI:
```bash
claude mcp add windows-dev python3 /path/to/bridge.py
```

Restart Claude Code after adding the configuration.

## Available Tools

| Tool | Description |
|------|-------------|
| `win_exec` | Execute shell command (cmd.exe) |
| `win_powershell` | Execute PowerShell command |
| `win_read_file` | Read a text file |
| `win_read_file_b64` | Read a file as base64 (for binaries) |
| `win_write_file` | Write content to a file |
| `win_list_directory` | List directory contents |
| `win_download_file` | Download a file from URL |
| `win_delete` | Delete a file or directory |
| `win_copy` | Copy a file or directory |
| `win_move` | Move a file or directory |
| `win_exists` | Check if a path exists |
| `win_shell_status` | Check server health |
| `win_server_info` | Get system information |

## Usage

Once configured, Claude Code can execute commands on Windows:

```
You: Run ipconfig on the Windows machine
Claude: [uses win_exec with command "ipconfig"]
```

### Verification

1. Start the server on Windows: `python server.py`
2. Start Claude Code on Mac: `claude`
3. Ask Claude: "Check the Windows server status"

If working, Claude will return the hostname and user from the Windows machine.

### Example Prompts

- "Run `whoami` on the Windows machine"
- "List the contents of C:\Users"
- "Read the file C:\Windows\System32\drivers\etc\hosts"
- "Download a file from URL to C:\Temp\file.exe"

## HTTP Endpoints (server.py)

For debugging, you can call the server directly:

```bash
# Health check
curl http://192.168.x.x:8000/health

# System info
curl http://192.168.x.x:8000/info

# Execute command
curl -X POST http://192.168.x.x:8000/exec \
  -H "Content-Type: application/json" \
  -d '{"cmd": "whoami"}'

# Execute PowerShell
curl -X POST http://192.168.x.x:8000/powershell \
  -H "Content-Type: application/json" \
  -d '{"cmd": "Get-Process | Select-Object -First 5"}'

# List directory
curl -X POST http://192.168.x.x:8000/ls \
  -H "Content-Type: application/json" \
  -d '{"path": "C:\\Users"}'
```

## Security Notes

- This tool exposes a shell over HTTP without authentication or encryption.
- Only run on trusted, private lab networks.
- Do not expose port 8000 to the internet.
- Avoid running interactive commands that require user input.

## Troubleshooting

**Claude Code says no tools available:**
- Restart Claude Code after adding MCP config
- Check that `bridge.py` path is correct in config
- Verify Python 3 is available as `python3`

**Connection refused:**
- Verify Windows server is running
- Check Windows firewall allows port 8000
- Confirm IP address is correct in `bridge.py`

**Commands timeout:**
- Default timeout is 300 seconds (5 minutes)
- Increase `TIMEOUT` in `bridge.py` for longer operations

## License

MIT
