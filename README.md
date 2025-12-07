# Windows God Mode MCP

A high-performance, persistent Model Context Protocol (MCP) server that bridges **Claude Code (CLI)** to a **Windows Lab Machine**.

Designed for offensive security labs and red team workflows, this tool provides **raw, unrestricted shell access** with state persistence (variables are saved between commands) and a 20-minute timeout for long-running tools (Nmap, BloodHound, etc.).

## Architecture

* **Server (Windows):** Runs a persistent PowerShell session and listens on Port 8000 (SSE).
* **Bridge (Mac):** Acts as a local MCP proxy. It receives commands from Claude Code via stdio, forwards them over HTTP to Windows, and returns the output.

## Prerequisites

* **Windows Machine:** Python 3.10+, PowerShell 5.1+
* **Mac Machine:** Python 3.10+, Claude Code CLI
* **Network:** Both machines must be on the same LAN/VPN. Port 8000 must be open on Windows.

---

## Installation

### 1. Windows Side (The Server)

1.  Install Python dependencies:
    ```powershell
    pip install "mcp[cli]" psutil uvicorn
    ```
2.  Save `server.py` to `C:\MCP\WinLab\server.py`.
3.  Allow Port 8000 in Firewall:
    ```powershell
    New-NetFirewallRule -DisplayName "MCP-Server" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
    ```
4.  Run the server:
    ```powershell
    python server.py
    ```

### 2. Mac Side (The Bridge)

1.  Install Python dependencies:
    ```bash
    pip install "mcp[cli]" httpx
    ```
2.  Create the directory:
    ```bash
    mkdir -p ~/mcp/win-bridge
    ```
3.  Save `bridge.py` to `~/mcp/win-bridge/bridge.py`.
4.  **Edit `bridge.py`** and update the `WINDOWS_IP` variable to your Windows LAN IP.

### 3. Connect Claude Code (Mac)

1.  Locate your MCP configuration file.
    * Standard path: `~/Library/Application Support/Claude/claude_desktop_config.json`
    * *Note: Claude Code often shares this config file with the desktop app. If you use a custom config path flag, ensure this JSON is referenced.*
2.  Add the bridge configuration:
    ```json
    {
      "mcpServers": {
        "win-god-mode": {
          "command": "python",
          "args": ["/Users/YOUR_USER/mcp/win-bridge/bridge.py"]
        }
      }
    }
    ```

---

## Usage & Verification

Since there is no GUI, follow this verification loop in your terminal.

1.  **Start the Server:** Ensure `python server.py` is running on Windows.
2.  **Start Claude Code:** Run `claude` in your Mac terminal.
3.  **Verify Connection:**
    Type the following prompt:
    > "List your available tools. Do you see `win_exec` and `win_read`?"

    * **Success:** Claude will list the tools.
    * **Failure:** Claude will say it has no external tools. Check the bridge logs.

### Example CLI Prompts

**1. Reconnaissance**
> "Use `win_exec` to get the current user and IP address."

**2. Persistence Test**
> "Set a variable `$target = '192.168.1.5'`. Then, run `ping $target` to confirm it remembers the IP."

**3. Bulk Reading**
> "Read all `.xml` files in `C:\ProgramData\App\Config` using `win_read`."

### Important Notes

* **Interactive Tools:** Do **not** run commands that require user input (e.g., `runas`, `copy` without `/Y`). The shell will hang waiting for a keypress. Always use force flags (e.g., `rm -Force`).
* **Security:** This tool exposes a raw shell over HTTP (Port 8000) **without encryption**. Only run this on a trusted, private lab network.

---

## License
MIT
