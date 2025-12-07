#!/usr/bin/env python3
"""
Windows MCP Server - Run on Windows machine
Usage: python server.py [port]
Default port: 8000
"""

import subprocess
import json
import base64
import os
import sys
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler

HOST = "0.0.0.0"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        if self.path == "/health":
            self.send_json({
                "status": "ok",
                "hostname": os.environ.get("COMPUTERNAME", "unknown"),
                "user": os.environ.get("USERNAME", "unknown")
            })
        elif self.path == "/info":
            self.send_json({
                "hostname": os.environ.get("COMPUTERNAME", "unknown"),
                "user": os.environ.get("USERNAME", "unknown"),
                "cwd": os.getcwd(),
                "platform": sys.platform
            })
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode() if length > 0 else "{}"
            data = json.loads(body)
        except Exception as e:
            self.send_json({"error": f"Invalid JSON: {e}"}, 400)
            return

        # Execute shell command (cmd.exe)
        if self.path == "/exec":
            cmd = data.get("cmd", "")
            timeout = data.get("timeout", 300)
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
                self.send_json({
                    "success": r.returncode == 0,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                    "returncode": r.returncode
                })
            except subprocess.TimeoutExpired:
                self.send_json({"success": False, "error": f"Timeout after {timeout}s"}, 408)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # Execute PowerShell command
        elif self.path == "/powershell":
            cmd = data.get("cmd", "")
            timeout = data.get("timeout", 300)
            try:
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                    capture_output=True, text=True, timeout=timeout
                )
                self.send_json({
                    "success": r.returncode == 0,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                    "returncode": r.returncode
                })
            except subprocess.TimeoutExpired:
                self.send_json({"success": False, "error": f"Timeout after {timeout}s"}, 408)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # Read file
        elif self.path == "/read":
            path = data.get("path", "")
            try:
                if data.get("binary"):
                    with open(path, "rb") as f:
                        content = base64.b64encode(f.read()).decode()
                    self.send_json({"success": True, "content": content, "path": path, "binary": True})
                else:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    self.send_json({"success": True, "content": content, "path": path})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # Write file
        elif self.path == "/write":
            path = data.get("path", "")
            content = data.get("content", "")
            try:
                # Create parent directories if needed
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)

                if data.get("binary"):
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(content))
                else:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                self.send_json({"success": True, "path": path})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # List directory
        elif self.path == "/ls":
            path = data.get("path", ".")
            try:
                items = []
                for name in os.listdir(path):
                    full_path = os.path.join(path, name)
                    item = {
                        "name": name,
                        "type": "dir" if os.path.isdir(full_path) else "file"
                    }
                    try:
                        item["size"] = os.path.getsize(full_path)
                    except:
                        pass
                    items.append(item)
                self.send_json({"success": True, "path": path, "items": items})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # Download file from URL
        elif self.path == "/download":
            url = data.get("url", "")
            dst = data.get("dst", "")
            try:
                import urllib.request
                parent = os.path.dirname(dst)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                urllib.request.urlretrieve(url, dst)
                self.send_json({"success": True, "dst": dst, "size": os.path.getsize(dst)})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # Delete file/directory
        elif self.path == "/delete":
            path = data.get("path", "")
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.send_json({"success": True, "path": path})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # Copy file/directory
        elif self.path == "/copy":
            src = data.get("src", "")
            dst = data.get("dst", "")
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                self.send_json({"success": True, "src": src, "dst": dst})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # Move file/directory
        elif self.path == "/move":
            src = data.get("src", "")
            dst = data.get("dst", "")
            try:
                shutil.move(src, dst)
                self.send_json({"success": True, "src": src, "dst": dst})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        # Check if path exists
        elif self.path == "/exists":
            path = data.get("path", "")
            self.send_json({
                "success": True,
                "exists": os.path.exists(path),
                "isfile": os.path.isfile(path),
                "isdir": os.path.isdir(path),
                "path": path
            })

        else:
            self.send_json({"error": f"Unknown endpoint: {self.path}"}, 404)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}")


if __name__ == "__main__":
    print("=" * 60)
    print("  Windows God-Mode MCP Server")
    print(f"  Listening on {HOST}:{PORT}")
    print("=" * 60)
    print(f"  Hostname: {os.environ.get('COMPUTERNAME', 'unknown')}")
    print(f"  User: {os.environ.get('USERNAME', 'unknown')}")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /health          - Server health check")
    print("  GET  /info            - System information")
    print("  POST /exec            - Execute shell command")
    print("  POST /powershell      - Execute PowerShell command")
    print("  POST /read            - Read file")
    print("  POST /write           - Write file")
    print("  POST /ls              - List directory")
    print("  POST /download        - Download file from URL")
    print("  POST /delete          - Delete file/directory")
    print("  POST /copy            - Copy file/directory")
    print("  POST /move            - Move file/directory")
    print("  POST /exists          - Check if path exists")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")

    try:
        HTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
