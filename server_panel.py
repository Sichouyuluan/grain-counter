"""
小麦籽粒检测 — 服务器管理面板（主入口）
功能拆分: theme.py | panel_ui.py | panel_controls.py
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import threading
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import messagebox

from graincounter.theme import Theme
from graincounter.panel_ui import PanelUI
from graincounter.panel_controls import PanelControls


class ServerPanel(PanelUI, PanelControls):
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Grain Counter — 服务器管理面板")
        self.root.geometry("920x680")
        self.root.configure(bg=Theme.bg)
        self.root.resizable(True, True)
        self.root.minsize(640, 520)

        # 状态
        self.server_process: subprocess.Popen | None = None
        self.server_running = False
        self.log_thread: threading.Thread | None = None

        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_server_path = os.path.join(self.project_dir, "web_server.py")

        # Tailscale
        self.tailscale_ip: str | None = None
        self.tailscale_online = False

        # Cloudflared
        self.cloudflared_process: subprocess.Popen | None = None

        # 在线设备
        self._online_devices: list[dict] = []
        self._dropdown_open = False
        self._dropdown_win: tk.Toplevel | None = None
        self._device_count = 0
        self._valuable_count = 0

        # 变更追踪
        self._prev_port = "8000"
        self._prev_key = ""

        # 面板配置变量
        self.port_var = tk.StringVar(value="8000")
        self.auth_var = tk.BooleanVar(value=True)
        self.custom_key_var = tk.StringVar(value="")
        self.hide_poll_var = tk.BooleanVar(value=True)
        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.log_filter_var = tk.StringVar(value="全部")

        self._panel_config_path = os.path.join(self.project_dir, ".panel_config.json")
        self._log_history: list[tuple[str, str]] = []

        self._load_panel_config()
        self._build_ui()       # 来自 PanelUI
        self._load_saved_key()
        # 启动前扫描模型目录
        self._config_model_path = self._read_config_model_path()
        self.scan_models_dir()  # 来自 PanelControls
        self._detect_tailscale()  # 来自 PanelControls
        self._detect_cloudflared()  # 来自 PanelControls
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══════════════════════════════════════════
    #  工具方法
    # ═══════════════════════════════════════════

    @staticmethod
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _show_toast(self, msg: str, duration_ms: int = 1800):
        tw = tk.Toplevel(self.root)
        tw.overrideredirect(True)
        tw.configure(bg=Theme.border)
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 90
        y = self.root.winfo_y() + 50
        tw.geometry(f"200x34+{x}+{y}")
        tk.Label(tw, text=msg, bg=Theme.border, fg=Theme.text,
                 font=(Theme.font, 9)).pack(expand=True, fill=tk.BOTH)
        tw.after(duration_ms, tw.destroy)

    # ═══════════════════════════════════════════
    #  配置持久化
    # ═══════════════════════════════════════════

    def _read_config_model_path(self):
        """从 config.yaml 读取当前模型路径"""
        try:
            import yaml
            config_path = os.path.join(self.project_dir, "config.yaml")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                return cfg.get("model_path", "models/grain_v8m_v10.onnx")
        except Exception:
            pass
        return "models/grain_v8m_v10.onnx"

    def _load_panel_config(self):
        try:
            if os.path.exists(self._panel_config_path):
                with open(self._panel_config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.port_var.set(cfg.get("port", "8000"))
                self.auth_var.set(cfg.get("auth", True))
                self.hide_poll_var.set(cfg.get("hide_poll", True))
                self.auto_scroll_var.set(cfg.get("auto_scroll", True))
                self.custom_key_var.set(cfg.get("key", ""))
                self._prev_port = self.port_var.get()
                self._prev_key = cfg.get("key", "")
        except Exception:
            pass

    def _save_panel_config(self):
        try:
            cfg = {
                "port": self.port_var.get(),
                "auth": self.auth_var.get(),
                "hide_poll": self.hide_poll_var.get(),
                "auto_scroll": self.auto_scroll_var.get(),
                "key": self.custom_key_var.get(),
            }
            with open(self._panel_config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ═══════════════════════════════════════════
    #  剪贴板 & URL
    # ═══════════════════════════════════════════

    def _copy_url(self, url_var):
        url = url_var.get()
        if url and not url.startswith("http://--"):
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self._log(f"已复制: {url}", "SUCCESS")
            self._show_toast("✅ 已复制")

    def _open_url(self, url_var):
        url = url_var.get()
        if url and not url.startswith("http://--"):
            webbrowser.open(url)
            self._log(f"已打开: {url}", "SUCCESS")
        else:
            self._show_toast("⚠️ 地址无效")

    def _copy_custom_key(self):
        key = self.custom_key_var.get().strip()
        if key:
            self.root.clipboard_clear()
            self.root.clipboard_append(key)
            self._log(f"已复制 Key: {key[:4]}...", "SUCCESS")
            self._show_toast("✅ Key 已复制")

    # ═══════════════════════════════════════════
    #  配置变更
    # ═══════════════════════════════════════════

    def _on_port_changed(self):
        v = self.port_var.get()
        if v != self._prev_port:
            self._log(f"端口: {self._prev_port} → {v}", "INFO")
            self._prev_port = v
            self._update_urls()

    def _on_auth_changed(self):
        v = self.auth_var.get()
        label = "ON" if v else "OFF"
        self._log(f"API 认证: {label}", "INFO")
        if self.server_running:
            self._toggle_auth_on_server(v)  # 来自 PanelControls

    def _on_key_changed(self):
        v = self.custom_key_var.get().strip()
        if v != self._prev_key:
            self._log("Key 已修改", "INFO")
            self._prev_key = v

    def _load_saved_key(self):
        try:
            kf = os.path.join(self.project_dir, ".api_key")
            saved = ""
            if os.path.exists(kf):
                with open(kf, "r") as f:
                    saved = f.read().strip()
            if not saved:
                saved = secrets.token_urlsafe(32)
                with open(kf, "w") as f:
                    f.write(saved)
            self.custom_key_var.set(saved)
            self._prev_key = saved
        except Exception:
            pass

    # ═══════════════════════════════════════════
    #  日志
    # ═══════════════════════════════════════════

    def _on_log_filter_changed(self, *args):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for lvl, line in self._log_history:
            if self.log_filter_var.get() == "全部" or lvl == self.log_filter_var.get():
                self.log_text.insert(tk.END, line, lvl)
        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _log(self, msg: str, level="INFO"):
        if self.hide_poll_var.get() and not any(
            kw in msg for kw in ["[VALUABLE]", "[MANUAL_SAVE]"]
        ):
            if any(kw in msg for kw in [
                "/api/online-devices", "/api/valuable-stats",
                "/api/ping", "/api/health", "台设备", "设备数量",
            ]):
                return
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] {msg}\n"
        self._log_history.append((level, line))
        if self.log_filter_var.get() == "全部" or level == self.log_filter_var.get():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, line, level)
            if self.auto_scroll_var.get():
                self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        try:
            lp = os.path.join(self.project_dir, "server_panel.log")
            with open(lp, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    # ═══════════════════════════════════════════
    #  UI 状态
    # ═══════════════════════════════════════════

    def _update_ui_state(self, running: bool):
        green = Theme.accent
        red = Theme.red
        dot_c = green if running else red

        self.status_dot.config(fg=dot_c)
        self.local_dot.config(fg=dot_c)
        self.lan_dot.config(fg=dot_c)
        self.status_label.config(text="运行中" if running else "未运行",
                                 fg=green if running else Theme.text_dim)

        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        self.restart_btn.config(state=tk.NORMAL if running else tk.DISABLED)

        if running:
            self._update_urls()
            self.root.after(1500, self._fetch_api_key)  # 来自 PanelControls
        else:
            self.local_url_var.set("http://-- 未启动 --")
            self.lan_url_var.set("http://-- 未启动 --")
            if self.tailscale_ip:
                self.ts_url_var.set(f"http://{self.tailscale_ip}:{self.port_var.get()}")
            self._safe_pack_forget(self.key_frame)
            self._update_device_count(0)

    @staticmethod
    def _safe_pack_forget(widget):
        try:
            widget.pack_forget()
        except Exception:
            pass

    def _update_urls(self):
        port = self.port_var.get().strip()
        local_ip = self._get_local_ip()
        self.local_url_var.set(f"http://localhost:{port}")
        self.lan_url_var.set(f"http://{local_ip}:{port}")
        if self.tailscale_ip:
            self.ts_url_var.set(f"http://{self.tailscale_ip}:{port}")

    # ═══════════════════════════════════════════
    #  进程检查 & 关闭
    # ═══════════════════════════════════════════

    def _check_loop(self):
        if self.server_running and self.server_process:
            if self.server_process.poll() is not None:
                self._on_server_stopped()  # 来自 PanelControls
        self.root.after(2000, self._check_loop)

    def _on_close(self):
        self._save_panel_config()
        self._close_dropdown()  # 来自 PanelUI
        if self.server_running:
            if messagebox.askyesno("确认退出",
                                   "服务器正在运行，关闭面板将停止服务器。\n确定退出？"):
                self._stop_server()  # 来自 PanelControls
                self._stop_cloudflared()
                self.root.destroy()
        else:
            self.root.destroy()
        # Cleanup PID
        try:
            pid_path = os.path.join(self.project_dir, ".panel_pid")
            if os.path.exists(pid_path):
                os.remove(pid_path)
        except Exception:
            pass

    def run(self, auto_start=False):
        # Write PID file for grainoff
        pid_path = os.path.join(self.project_dir, ".panel_pid")
        try:
            with open(pid_path, "w") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass
        try:
            lp = os.path.join(self.project_dir, "server_panel.log")
            with open(lp, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*50}\n面板启动: {datetime.now():%Y-%m-%d %H:%M:%S}\n{'='*50}\n")
        except Exception:
            pass
        self._log("管理面板已启动", "INFO")
        self.root.deiconify()
        self.root.after(2000, self._check_loop)
        if auto_start:
            self.root.after(800, self._auto_start_all)
        self.root.mainloop()
        # Cleanup PID on exit
        try:
            if os.path.exists(pid_path):
                os.remove(pid_path)
        except Exception:
            pass

    def _auto_start_all(self):
        self._log("自动启动模式: 启动服务器 + Cloudflared", "INFO")
        self._start_server()
        self.root.after(5000, self._start_cloudflared)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Grain Counter 服务器管理面板")
    parser.add_argument("--auto-start", action="store_true", help="自动启动服务器和 Cloudflared 隧道")
    args = parser.parse_args()
    ServerPanel().run(auto_start=args.auto_start)
