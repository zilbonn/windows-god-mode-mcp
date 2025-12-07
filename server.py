import subprocess
import threading
import queue
import os
import time
import glob
import base64
import json
import uuid
import uvicorn

# Set environment variable to disable host checking BEFORE importing MCP
os.environ["MCP_DISABLE_HOST_VALIDATION"] = "1"
os.environ["MCP_ALLOWED_HOSTS"] = "*"

from mcp.server.fastmcp import FastMCP

# Patch MCP's transport security to allow all hosts
import mcp.server.sse as sse_module
original_validate = getattr(sse_module, '_validate_request', None)
if original_validate:
    sse_module._validate_request = lambda *args, **kwargs: True

try:
    from mcp.server import transport_security
    transport_security._validate_host = lambda *args, **kwargs: True
    transport_security.validate_request = lambda *args, **kwargs: True
    transport_security.check_host = lambda *args, **kwargs: True
    if hasattr(transport_security, 'TransportSecurity'):
        transport_security.TransportSecurity.validate_host = lambda *args, **kwargs: True
except Exception as e:
    print(f"Warning: Could not patch transport_security: {e}")

mcp = FastMCP("WinLab-GodMode", host="0.0.0.0", port=8000)


class PersistentShell:
    def __init__(self):
        self.lock = threading.Lock()
        self._start_shell()

    def _start_shell(self):
        """Start or restart the PowerShell process."""
        self.process = subprocess.Popen(
            ["powershell", "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
            cwd=os.getcwd()
        )
        self.q = queue.Queue()
        self.error_q = queue.Queue()

        threading.Thread(target=self._reader, args=(self.process.stdout, self.q), daemon=True).start()
        threading.Thread(target=self._reader, args=(self.process.stderr, self.error_q), daemon=True).start()

        # Wait for shell to be ready
        time.sleep(0.5)

    def _reader(self, pipe, q):
        while True:
            try:
                line = pipe.readline()
                if line:
                    q.put(line)
                else:
                    break
            except:
                break

    def _restart_if_dead(self):
        """Check if process is dead and restart if needed."""
        if self.process.poll() is not None:
            print("[!] Shell died, restarting...")
            self._start_shell()
            return True
        return False

    def run(self, script: str, timeout: int = 1200) -> dict:
        """
        Execute command and return structured result.
        Uses unique markers to avoid collision.
        """
        with self.lock:
            self._restart_if_dead()

            # Clear queues
            with self.q.mutex:
                self.q.queue.clear()
            with self.error_q.mutex:
                self.error_q.queue.clear()

            # Generate unique markers for this execution
            exec_id = uuid.uuid4().hex[:12]
            start_marker = f"###START_{exec_id}###"
            end_marker = f"###END_{exec_id}###"

            # Wrap command with markers
            # Use Write-Host with -NoNewline for clean markers
            wrapped_cmd = f"""
Write-Host '{start_marker}'
try {{
{script}
}} catch {{
    Write-Host "EXCEPTION: $_"
}}
Write-Host '{end_marker}'
"""

            try:
                self.process.stdin.write(wrapped_cmd)
                self.process.stdin.flush()
            except OSError as e:
                self._start_shell()
                return {
                    "success": False,
                    "error": f"Shell process died: {e}. Restarted.",
                    "output": "",
                    "stderr": ""
                }

            output_lines = []
            started = False
            start_time = time.time()

            while True:
                if time.time() - start_time > timeout:
                    return {
                        "success": False,
                        "error": f"Timeout after {timeout} seconds",
                        "output": "".join(output_lines),
                        "stderr": ""
                    }

                try:
                    line = self.q.get(timeout=0.1)

                    if start_marker in line:
                        started = True
                        continue

                    if end_marker in line:
                        break

                    if started:
                        output_lines.append(line)

                except queue.Empty:
                    continue

            # Collect stderr
            errors = []
            while not self.error_q.empty():
                try:
                    errors.append(self.error_q.get_nowait())
                except:
                    break

            output = "".join(output_lines).strip()
            stderr = "".join(errors).strip()

            return {
                "success": True,
                "output": output,
                "stderr": stderr if stderr else None
            }

    def run_base64(self, b64_script: str, timeout: int = 1200) -> dict:
        """
        Execute a base64-encoded command.
        This is the most reliable way to pass complex commands.
        """
        try:
            script = base64.b64decode(b64_script).decode('utf-8')
            return self.run(script, timeout)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to decode base64: {e}",
                "output": "",
                "stderr": ""
            }


# Create the single persistent instance
shell = PersistentShell()


@mcp.tool()
def win_exec(command: str) -> str:
    """
    Execute a PowerShell command on Windows.

    For SIMPLE commands, pass the command directly as a string.
    For COMPLEX commands with quotes/special chars, use win_exec_b64 instead.

    Returns JSON with: success, output, stderr, error
    """
    result = shell.run(command)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def win_exec_b64(command_b64: str) -> str:
    """
    Execute a BASE64-ENCODED PowerShell command.

    THIS IS THE MOST RELIABLE METHOD for complex commands.

    How to use:
    1. Write your PowerShell script
    2. Encode it to base64 (UTF-8)
    3. Pass the base64 string here

    Example: To run 'Get-Process | Where-Object {$_.CPU -gt 10}'
    - Base64 encode that string
    - Pass the encoded string to this function

    Returns JSON with: success, output, stderr, error
    """
    result = shell.run_base64(command_b64)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def win_write_file(path: str, content_b64: str) -> str:
    """
    Write content to a file on Windows.

    Args:
        path: Full path to the file (e.g., C:\\temp\\script.ps1)
        content_b64: Base64-encoded file content

    Returns JSON with success status.
    """
    try:
        content = base64.b64decode(content_b64).decode('utf-8')
        # Escape for PowerShell here-string
        script = f'''
$content = @'
{content}
'@
$content | Out-File -FilePath "{path}" -Encoding UTF8 -Force
Write-Host "File written successfully: {path}"
'''
        result = shell.run(script)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "output": "",
            "stderr": ""
        })


@mcp.tool()
def win_read_file(path: str) -> str:
    """
    Read a file from Windows and return its content.

    Args:
        path: Full path to the file

    Returns JSON with file content in 'output' field.
    """
    script = f'Get-Content -Path "{path}" -Raw -ErrorAction Stop'
    result = shell.run(script)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def win_read_file_b64(path: str) -> str:
    """
    Read a file and return content as base64.
    Useful for binary files or files with special characters.

    Args:
        path: Full path to the file

    Returns JSON with base64-encoded content in 'output' field.
    """
    script = f'''
$bytes = [System.IO.File]::ReadAllBytes("{path}")
[Convert]::ToBase64String($bytes)
'''
    result = shell.run(script)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def bulk_read(directory: str, pattern: str = "*") -> str:
    """
    Read multiple files at once.

    Args:
        directory: Directory path
        pattern: Glob pattern (default: *)

    Returns JSON dictionary: {"filepath": "content", ...}
    """
    search_path = os.path.join(directory, pattern)
    files = glob.glob(search_path)

    results = {}
    for fpath in files[:20]:
        if os.path.isfile(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    results[fpath] = f.read()
            except Exception as e:
                results[fpath] = f"[Error: {e}]"

    return json.dumps(results, ensure_ascii=False)


@mcp.tool()
def win_shell_status() -> str:
    """
    Check if the persistent shell is alive and responsive.
    Also returns system info.
    """
    result = shell.run("Write-Host 'Shell OK'; $env:COMPUTERNAME; $env:USERNAME")
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def win_restart_shell() -> str:
    """
    Force restart the persistent PowerShell session.
    Use if the shell becomes unresponsive.
    """
    try:
        shell.process.kill()
    except:
        pass
    shell._start_shell()
    return json.dumps({
        "success": True,
        "output": "Shell restarted successfully",
        "stderr": None
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  WinLab God-Mode MCP Server")
    print("  Listening on 0.0.0.0:8000")
    print("=" * 60)
    print("\nAvailable tools:")
    print("  - win_exec(command)          : Execute PowerShell command")
    print("  - win_exec_b64(command_b64)  : Execute base64-encoded command")
    print("  - win_write_file(path, b64)  : Write file (base64 content)")
    print("  - win_read_file(path)        : Read file as text")
    print("  - win_read_file_b64(path)    : Read file as base64")
    print("  - bulk_read(dir, pattern)    : Read multiple files")
    print("  - win_shell_status()         : Check shell health")
    print("  - win_restart_shell()        : Restart shell")
    print("=" * 60)

    mcp.run(transport="sse")
