"""grainon / grainoff — 一键启动/停止 Grain Counter 全栈服务.

grainon: 启动管理面板 → 启动服务器 → 启动 Cloudflared 隧道
grainoff: 停止 Cloudflared → 停止服务器 → 关闭管理面板
"""
import os
import sys
import time
import signal
import subprocess


_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
PANEL_SCRIPT = os.path.join(_PROJECT_ROOT, "server_panel.py")
PID_FILE = os.path.join(_PROJECT_ROOT, ".panel_pid")
SERVER_PID_FILE = os.path.join(_PROJECT_ROOT, ".server_pid")


def _kill_by_name(name):
    """Kill all processes matching name."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/IM", name],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        subprocess.run(["pkill", "-f", name], capture_output=True)


def _kill_by_pid(pid):
    """Kill a process by PID."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def _read_pid(filepath):
    """Read PID from file."""
    try:
        if os.path.exists(filepath):
            with open(filepath) as f:
                return int(f.read().strip())
    except Exception:
        pass
    return None


def grainkey():
    """Print the current API Key."""
    key_file = os.path.join(_PROJECT_ROOT, ".api_key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            print(f.read().strip())
    else:
        print("No API key found. Start the server first.", file=sys.stderr)
        sys.exit(1)


def grainon():
    """Start everything: panel → server → cloudflared."""
    print("═" * 50)
    print("  Grain Counter — 一键启动 (grainon)")
    print("═" * 50)
    print(f"  项目目录: {_PROJECT_ROOT}")
    print(f"  面板脚本: {PANEL_SCRIPT}")

    if not os.path.exists(PANEL_SCRIPT):
        print("[ERROR] 找不到 server_panel.py")
        sys.exit(1)

    # Check if already running
    existing_pid = _read_pid(PID_FILE)
    if existing_pid:
        try:
            os.kill(existing_pid, 0)
            print(f"[WARN] 面板已在运行 (PID: {existing_pid})")
            print("  请先运行 grainoff 停止服务")
            sys.exit(1)
        except OSError:
            # Stale PID file
            try:
                os.remove(PID_FILE)
            except Exception:
                pass

    print("  启动管理面板 (--auto-start)...")
    # Show current API key
    key_file = os.path.join(_PROJECT_ROOT, ".api_key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            api_key = f.read().strip()
        print(f"  API Key: {api_key}")
    else:
        print("  API Key: 未生成 (面板启动后自动生成)")
    # Launch panel in a new process group (detached)
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, PANEL_SCRIPT, "--auto-start"],
        cwd=_PROJECT_ROOT,
        **kwargs,
    )
    print(f"  面板 PID: {proc.pid}")
    print("  服务器将自动启动...")
    print("  Cloudflared 隧道将自动连接...")
    print(f"  本地地址: http://localhost:8000")
    try:
        import yaml
        # 优先本地配置，再公共配置
        for fname in ("config.local.yaml", "config.yaml"):
            config_path = os.path.join(_PROJECT_ROOT, fname)
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                tunnel = cfg.get("tunnel_url", "")
                if tunnel:
                    print(f"  公网地址: {tunnel}")
                    break
    except Exception:
        pass
    print("═" * 50)


def grainoff():
    """Stop everything: cloudflared → server → panel."""
    print("═" * 50)
    print("  Grain Counter — 一键停止 (grainoff)")
    print("═" * 50)

    # 1. Stop Cloudflared
    print("[1/3] 停止 Cloudflared 隧道...")
    _kill_by_name("cloudflared.exe")
    _kill_by_name("cloudflared")
    time.sleep(1)
    print("       Cloudflared 已停止")

    # 2. Stop the web server (managed by panel)
    print("[2/3] 停止 Web 服务器...")
    server_pid = _read_pid(SERVER_PID_FILE)
    if server_pid:
        _kill_by_pid(server_pid)
        try:
            os.remove(SERVER_PID_FILE)
        except Exception:
            pass
        print(f"       服务器已停止 (PID: {server_pid})")
    else:
        print("       未找到服务器 PID 文件, 跳过")

    # 3. Stop the panel
    print("[3/3] 关闭管理面板...")
    panel_pid = _read_pid(PID_FILE)
    if panel_pid:
        _kill_by_pid(panel_pid)
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
        print(f"       面板已关闭 (PID: {panel_pid})")
    else:
        print("       未找到面板 PID 文件, 尝试强制清理...")
        # Last resort: kill python processes running server_panel
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/F", "/FI", "IMAGENAME eq python.exe", "/FI", "WINDOWTITLE eq Grain Counter*"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        print("       清理完成")

    print("═" * 50)
    print("  所有服务已停止")


if __name__ == "__main__":
    cmd = os.path.basename(sys.argv[0]) if sys.argv else ""
    if "off" in cmd.lower() or (len(sys.argv) > 1 and sys.argv[1] == "off"):
        grainoff()
    else:
        grainon()
