import subprocess
import threading
import queue
import os
import time
import glob
import uvicorn
from mcp.server.fastmcp import FastMCP

# Initialize Server
mcp = FastMCP("WinLab-GodMode")

class PersistentShell:
    def __init__(self):
        # Unique marker to identify end of command output
        self.marker = "###MCP_END_MARKER###"
        
        # Start PowerShell in the background. 
        # -NoExit keeps variables alive ($x=1 persists).
        # bufsize=0 ensures we get output instantly.
        self.process = subprocess.Popen(
            ["powershell", "-NoExit", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0, 
            cwd=os.getcwd()
        )
        self.q = queue.Queue()
        self.error_q = queue.Queue()
        
        # Threads to constantly read stdout/stderr without blocking
        threading.Thread(target=self._reader, args=(self.process.stdout, self.q), daemon=True).start()
        threading.Thread(target=self._reader, args=(self.process.stderr, self.error_q), daemon=True).start()

    def _reader(self, pipe, q):
        while True:
            line = pipe.readline()
            if line: q.put(line)
            else: break

    def run(self, script: str, timeout: int = 1200) -> str:
        """
        Runs the command with a 20-minute (1200s) timeout.
        """
        with self.q.mutex: self.q.queue.clear()
        with self.error_q.mutex: self.error_q.queue.clear()
        
        # Wrap the command to print our marker when done
        wrapped_cmd = f"{script}\nWrite-Host '{self.marker}'\n"
        
        try:
            self.process.stdin.write(wrapped_cmd)
            self.process.stdin.flush()
        except OSError:
            return "Error: Shell process died. Restart server."

        output_buffer = []
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                return f"Error: Timeout after {timeout} seconds."
            try:
                # Check for output every 0.1s
                line = self.q.get(timeout=0.1)
                if self.marker in line: 
                    break
                output_buffer.append(line)
            except queue.Empty:
                continue
        
        # Collect errors if any
        errors = []
        while not self.error_q.empty(): 
            errors.append(self.error_q.get())
        
        full_output = "".join(output_buffer).strip()
        if errors: 
            full_output += f"\n[STDERR]:\n{''.join(errors)}"
            
        return full_output

# Create the single persistent instance
shell = PersistentShell()

@mcp.tool()
def exec_persistent(command: str) -> str:
    """
    Executes a PowerShell command in the PERSISTENT session.
    Variables ($x=1) are saved between calls.
    Returns RAW TEXT. 
    """
    return shell.run(command)

@mcp.tool()
def bulk_read(directory: str, pattern: str = "*") -> dict:
    """
    Reads multiple files at once.
    Returns a JSON Dictionary: {"filename": "content..."}
    """
    search_path = os.path.join(directory, pattern)
    files = glob.glob(search_path)
    
    results = {}
    # Limit to 20 files to prevent crashing Claude with too much text
    for fpath in files[:20]: 
        if os.path.isfile(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    results[fpath] = f.read()
            except Exception as e:
                results[fpath] = f"[Error reading file: {e}]"
    
    return results

if __name__ == "__main__":
    print("📢 WinLab God-Mode Listening on 0.0.0.0:8000")

    # CRITICAL FIX: We call the sse_app method to get the ASGI application object
    app = mcp.sse_app()

    # We pass the application object to uvicorn, which will run the server
    # Added forwarded_allow_ips and proxy_headers to fix "Invalid Host header" error
    uvicorn.run(app, host="0.0.0.0", port=8000, forwarded_allow_ips="*", proxy_headers=True)
