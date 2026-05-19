"""Server lifecycle backend — start/stop/status for the FastAPI web server."""
import os
import sys
import time
import signal
import socket
import subprocess
import json

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from graincounter.config import load_config, get_config

PID_FILE = os.path.join(_PROJECT_ROOT, ".server_pid")
URLS_FILE = os.path.join(_PROJECT_ROOT, ".server_urls")


class ServerBackend:
    """Manage the FastAPI server subprocess."""

    def __init__(self):
        load_config()

    def _read_pid(self):
        if os.path.exists(PID_FILE):
            with open(PID_FILE) as f:
                try:
                    return int(f.read().strip())
                except (ValueError, OSError):
                    return None
        return None

    def _write_pid(self, pid):
        with open(PID_FILE, "w") as f:
            f.write(str(pid))

    def _clear_pid(self):
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

    def _is_running(self, pid=None):
        if pid is None:
            pid = self._read_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def _get_urls(self):
        """Get local and LAN URLs for the server."""
        host = get_config("host", "0.0.0.0")
        port = get_config("port", 8000)
        display_host = "127.0.0.1" if host == "0.0.0.0" else host
        urls = {"local": f"http://{display_host}:{port}"}

        # Get LAN IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("10.254.254.254", 1))
            lan_ip = s.getsockname()[0]
            s.close()
            urls["lan"] = f"http://{lan_ip}:{port}"
        except Exception:
            urls["lan"] = None

        return urls

    def status(self):
        """Return server status."""
        pid = self._read_pid()
        running = self._is_running(pid)
        result = {
            "running": running,
            "pid": pid,
            "host": get_config("host", "0.0.0.0"),
            "port": get_config("port", 8000),
            "auth": get_config("require_api_key", True),
            "model": os.path.basename(get_config("model_path", "")),
        }
        if running:
            result["urls"] = self._get_urls()
        return result

    def start(self, host=None, port=None, model=None, no_auth=False, api_key=None):
        """Start the server as a subprocess."""
        if self._is_running():
            return {"ok": False, "error": "Server is already running", "status": self.status()}

        # Build command
        server_script = os.path.join(_PROJECT_ROOT, "web_server.py")
        cmd = [sys.executable, server_script]
        if host:
            cmd.extend(["--host", host])
        if port:
            cmd.extend(["--port", str(port)])
        if model:
            cmd.extend(["--model", model])
        if no_auth:
            cmd.append("--no-auth")
        if api_key:
            cmd.extend(["--api-key", api_key])

        env = os.environ.copy()
        proc = subprocess.Popen(
            cmd,
            cwd=_PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        self._write_pid(proc.pid)

        # Wait briefly for startup
        time.sleep(2)
        running = self._is_running(proc.pid)
        result = {
            "ok": running,
            "pid": proc.pid,
            "urls": self._get_urls() if running else {},
        }
        if not running:
            result["error"] = "Server failed to start"
        return result

    def stop(self):
        """Stop the running server."""
        pid = self._read_pid()
        if not self._is_running(pid):
            self._clear_pid()
            return {"ok": False, "error": "Server is not running"}

        if sys.platform == "win32":
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        else:
            os.kill(pid, signal.SIGTERM)

        time.sleep(1)
        if self._is_running(pid):
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)

        self._clear_pid()
        return {"ok": True, "message": "Server stopped", "pid": pid}

    def restart(self, **kwargs):
        """Restart the server."""
        was_running = self._is_running()
        if was_running:
            self.stop()
            time.sleep(1)
        return self.start(**kwargs)

    def url(self):
        """Get server URLs."""
        if not self._is_running():
            return {"ok": False, "error": "Server is not running"}
        return {"ok": True, "urls": self._get_urls()}
