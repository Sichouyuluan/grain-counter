"""
小麦籽粒检测 - 服务器管理面板
- 一键启动/关闭 Web 服务器
- 实时显示服务器状态
- 在线设备下拉列表（HTTP 追踪）
- 内嵌命令行日志输出
- 地址栏带一键复制（本机 + 局域网）
"""

import os
import sys
import time
import json
import subprocess
import threading
import socket
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime
import urllib.request


class ServerPanel:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🌾 小麦籽粒检测 - 服务器管理面板")
        self.root.geometry("720x580")
        self.root.configure(bg="#1e1e1e")
        self.root.resizable(True, True)

        self.server_process = None
        self.server_running = False
        self.log_thread = None

        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_server_path = os.path.join(self.project_dir, "web_server.py")

        self.tailscale_ip = None
        self.tailscale_online = False
        self.device_count = 0

        # 在线设备下拉相关
        self._dropdown_open = False
        self._dropdown_win = None
        self._online_devices = []

        self._build_ui()
        self._load_saved_key()
        self._detect_tailscale()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ============================================================
    #  获取本机局域网 IP
    # ============================================================
    @staticmethod
    def _get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    # ============================================================
    #  复制到剪贴板 + toast 提示
    # ============================================================
    def _copy_url(self, url_var):
        url = url_var.get()
        if url and not url.startswith("http://--"):
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self._log(f"已复制: {url}", "SUCCESS")
            self._show_toast("✅ 已复制到剪贴板")

    def _open_url(self, url_var):
        url = url_var.get()
        if url and not url.startswith("http://--"):
            import webbrowser
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
            self._show_toast("✅ Key 已复制到剪贴板")
        else:
            self._show_toast("⚠️ Key 为空")

    def _on_port_changed(self, *_args):
        new_val = self.port_var.get()
        if new_val != self._prev_port:
            self._log(f"端口修改: {self._prev_port} → {new_val}", "INFO")
            self._prev_port = new_val

    def _on_auth_changed(self, *_args):
        new_val = self.auth_var.get()
        if new_val != self._prev_auth:
            label = "开启" if new_val else "关闭"
            self._log(f"API 认证: {label}", "INFO")
            self._prev_auth = new_val
            if self.server_running:
                self._toggle_auth_on_server(new_val)

    def _on_hide_pin_changed(self, *_args):
        new_val = self.hide_pin_var.get()
        if new_val != self._prev_hide_pin:
            label = "开启" if new_val else "关闭"
            self._log(f"隐藏 PIN: {label}", "INFO")
            self._prev_hide_pin = new_val

    def _on_key_changed(self):
        new_val = self.custom_key_var.get().strip()
        if new_val != self._prev_key:
            if new_val:
                self._log(f"API Key 已修改: {new_val[:4]}...", "INFO")
            else:
                self._log("API Key 已清空", "INFO")
            self._prev_key = new_val

    def _toggle_auth_on_server(self, enable):
        """热切换服务器的 API 认证，无需重启"""
        port = self.port_var.get().strip()
        def do_toggle():
            try:
                url = f"http://localhost:{port}/api/toggle-auth"
                req = urllib.request.Request(url, data=b"{}", method="POST",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    result = json.loads(resp.read().decode())
                    if result.get("ok"):
                        state = "开启" if result.get("auth") else "关闭"
                        self.root.after(0, lambda: self._log(f"服务器 API 认证已{state}（热切换，无需重启）", "SUCCESS"))
                    else:
                        self.root.after(0, lambda: self._log("热切换失败", "ERROR"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"热切换异常: {e}", "ERROR"))
        threading.Thread(target=do_toggle, daemon=True).start()

    def _load_saved_key(self):
        """启动时读取 .api_key 文件，预填到输入框；没有则自动生成"""
        import secrets as _secrets
        try:
            key_file = os.path.join(self.project_dir, ".api_key")
            saved = ""
            if os.path.exists(key_file):
                with open(key_file, "r") as f:
                    saved = f.read().strip()
            if not saved:
                saved = _secrets.token_urlsafe(32)
                with open(key_file, "w") as f:
                    f.write(saved)
            self.custom_key_var.set(saved)
        except Exception:
            pass

    def _show_toast(self, msg):
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.configure(bg="#333")
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 80
        y = self.root.winfo_y() + 60
        toast.geometry(f"160x30+{x}+{y}")
        tk.Label(toast, text=msg, bg="#333", fg="#fff",
                 font=("Microsoft YaHei", 9)).pack(expand=True)
        toast.after(1500, toast.destroy)

    # ============================================================
    #  UI 构建
    # ============================================================
    def _build_ui(self):
        # ---- 顶部标题栏 ----
        title_frame = tk.Frame(self.root, bg="#2d2d2d", height=48)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="🌾 小麦籽粒检测 Web 服务器",
                 bg="#2d2d2d", fg="#fff",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # ---- 状态栏 ----
        status_frame = tk.Frame(self.root, bg="#2b2b2b", height=36)
        status_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        status_frame.pack_propagate(False)
        tk.Label(status_frame, text="状态:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(10, 5))
        self.status_dot = tk.Label(status_frame, text="●", bg="#2b2b2b", fg="#f44336",
                                   font=("Consolas", 12, "bold"))
        self.status_dot.pack(side=tk.LEFT)
        self.status_label = tk.Label(status_frame, text="未运行", bg="#2b2b2b", fg="#aaa",
                                     font=("Microsoft YaHei", 10))
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))
        tk.Label(status_frame, text="  |  ", bg="#2b2b2b", fg="#555",
                 font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)

        # ---- 设备数量 + 下拉按钮 ----
        self.device_count_label = tk.Label(status_frame, text="📡 0台设备", bg="#2b2b2b", fg="#aaa",
                                           font=("Microsoft YaHei", 10))
        self.device_count_label.pack(side=tk.LEFT, padx=(0, 2))
        self.device_dropdown_btn = tk.Button(
            status_frame, text="▼", bg="#2b2b2b", fg="#aaa",
            font=("Consolas", 9, "bold"), relief="flat",
            activebackground="#3a3a3a", activeforeground="#fff",
            bd=0, padx=4, pady=0, cursor="hand2",
            command=self._toggle_dropdown
        )
        self.device_dropdown_btn.pack(side=tk.LEFT, padx=(0, 5))

        # ---- 地址栏 ----
        addr_outer = tk.Frame(self.root, bg="#2b2b2b")
        addr_outer.pack(fill=tk.X, padx=10, pady=(5, 5))

        # ---- API Key 显示栏 ----
        self.key_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.key_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.key_frame.pack_forget()

        row_key = tk.Frame(self.key_frame, bg="#2b2b2b")
        row_key.pack(fill=tk.X)
        tk.Label(row_key, text="🔑 Key:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 9), width=8, anchor="w").pack(side=tk.LEFT)
        self.key_var = tk.StringVar(value="--")
        self.key_entry = tk.Entry(row_key, textvariable=self.key_var,
                                  bg="#404040", fg="#0f0", font=("Consolas", 10),
                                  insertbackground="#fff", state="readonly", readonlybackground="#404040")
        self.key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.key_copy_btn = tk.Button(row_key, text="📋 复制", command=lambda: self._copy_url(self.key_var),
                                      bg="#555", fg="#fff", font=("Microsoft YaHei", 9),
                                      relief="flat", padx=10, pady=2, cursor="hand2")
        self.key_copy_btn.pack(side=tk.LEFT)

        # 本机地址行
        row_local = tk.Frame(addr_outer, bg="#2b2b2b")
        row_local.pack(fill=tk.X, pady=(0, 3))
        self.local_dot = tk.Label(row_local, text="●", bg="#2b2b2b", fg="#f44336",
                                  font=("Consolas", 9, "bold"))
        self.local_dot.pack(side=tk.LEFT, padx=(2, 0))
        tk.Label(row_local, text="💻 本机:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 9), width=7, anchor="w").pack(side=tk.LEFT)
        self.local_url_var = tk.StringVar(value="http://-- 未启动 --")
        local_entry = tk.Entry(row_local, textvariable=self.local_url_var,
                               bg="#404040", fg="#0f0", font=("Consolas", 10),
                               insertbackground="#fff", readonlybackground="#404040",
                               state="readonly")
        local_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(row_local, text="📋 复制", command=lambda: self._copy_url(self.local_url_var),
                  bg="#555", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT)
        tk.Button(row_local, text="🔗 打开", command=lambda: self._open_url(self.local_url_var),
                  bg="#6C63FF", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(5,0))

        # 局域网地址行
        row_lan = tk.Frame(addr_outer, bg="#2b2b2b")
        row_lan.pack(fill=tk.X)
        self.lan_dot = tk.Label(row_lan, text="●", bg="#2b2b2b", fg="#f44336",
                                font=("Consolas", 9, "bold"))
        self.lan_dot.pack(side=tk.LEFT, padx=(2, 0))
        tk.Label(row_lan, text="📱 局域网:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 9), width=7, anchor="w").pack(side=tk.LEFT)
        self.lan_url_var = tk.StringVar(value="http://-- 未启动 --")
        lan_entry = tk.Entry(row_lan, textvariable=self.lan_url_var,
                             bg="#404040", fg="#0ff", font=("Consolas", 10),
                             insertbackground="#fff", readonlybackground="#404040",
                             state="readonly")
        lan_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(row_lan, text="📋 复制", command=lambda: self._copy_url(self.lan_url_var),
                  bg="#555", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT)
        tk.Button(row_lan, text="🔗 打开", command=lambda: self._open_url(self.lan_url_var),
                  bg="#6C63FF", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(5,0))

        # Tailscale 穿墙地址行
        row_ts = tk.Frame(addr_outer, bg="#2b2b2b")
        row_ts.pack(fill=tk.X)
        self.ts_status_dot = tk.Label(row_ts, text="●", bg="#2b2b2b", fg="#f44336",
                                      font=("Consolas", 9, "bold"))
        self.ts_status_dot.pack(side=tk.LEFT, padx=(2, 0))
        tk.Label(row_ts, text="🌐 穿墙:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 9), width=7, anchor="w").pack(side=tk.LEFT)
        self.ts_url_var = tk.StringVar(value="检测中...")
        ts_entry = tk.Entry(row_ts, textvariable=self.ts_url_var,
                            bg="#404040", fg="#ff0", font=("Consolas", 10),
                            insertbackground="#fff", readonlybackground="#404040",
                            state="readonly")
        ts_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(row_ts, text="📋 复制", command=lambda: self._copy_url(self.ts_url_var),
                  bg="#555", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(row_ts, text="🔗 打开", command=lambda: self._open_url(self.ts_url_var),
                  bg="#6C63FF", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(5,0))
        tk.Button(row_ts, text="🔗 管理后台", command=self._open_tailscale_admin,
                  bg="#6C63FF", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT)

        # ---- 控制按钮 ----
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        self.start_btn = tk.Button(btn_frame, text="▶  启动服务器", command=self._start_server,
                                   bg="#4CAF50", fg="#fff", font=("Microsoft YaHei", 11, "bold"),
                                   relief="flat", padx=20, pady=8, activebackground="#45a049",
                                   cursor="hand2")
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_btn = tk.Button(btn_frame, text="⏹  停止服务器", command=self._stop_server,
                                  bg="#f44336", fg="#fff", font=("Microsoft YaHei", 11, "bold"),
                                  relief="flat", padx=20, pady=8, activebackground="#d32f2f",
                                  state=tk.DISABLED, cursor="hand2")
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.restart_btn = tk.Button(btn_frame, text="🔄 重启", command=self._restart_server,
                                     bg="#FF9800", fg="#fff", font=("Microsoft YaHei", 10),
                                     relief="flat", padx=15, pady=8, activebackground="#F57C00",
                                     state=tk.DISABLED, cursor="hand2")
        self.restart_btn.pack(side=tk.LEFT, padx=(0, 15))

        # 穿墙按钮
        sep = tk.Frame(btn_frame, bg="#555", width=1, height=30)
        sep.pack(side=tk.LEFT, padx=5)
        self.ts_start_btn = tk.Button(btn_frame, text="🌐 启动穿墙", command=self._start_tailscale,
                                      bg="#2196F3", fg="#fff", font=("Microsoft YaHei", 10),
                                      relief="flat", padx=12, pady=8, activebackground="#1976D2",
                                      cursor="hand2")
        self.ts_start_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.ts_stop_btn = tk.Button(btn_frame, text="🌐 停止穿墙", command=self._stop_tailscale,
                                     bg="#795548", fg="#fff", font=("Microsoft YaHei", 10),
                                     relief="flat", padx=12, pady=8, activebackground="#5D4037",
                                     cursor="hand2")
        self.ts_stop_btn.pack(side=tk.LEFT)

        # ---- 配置区 ----
        config_frame = tk.LabelFrame(self.root, text=" 配置 ", bg="#2b2b2b", fg="#aaa",
                                     font=("Microsoft YaHei", 10), padx=10, pady=8)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        row1 = tk.Frame(config_frame, bg="#2b2b2b")
        row1.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row1, text="端口:", bg="#2b2b2b", fg="#ddd",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="8000")
        tk.Entry(row1, textvariable=self.port_var, width=8, bg="#404040", fg="#fff",
                 insertbackground="#fff", font=("Consolas", 10)).pack(side=tk.LEFT, padx=(5, 20))
        tk.Label(row1, text="API认证:", bg="#2b2b2b", fg="#ddd",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.auth_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row1, variable=self.auth_var, bg="#2b2b2b", fg="#fff",
                       selectcolor="#4CAF50", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=5)
        tk.Label(row1, text="隐藏PIN:", bg="#2b2b2b", fg="#ddd",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(15, 0))
        self.hide_pin_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row1, variable=self.hide_pin_var, bg="#2b2b2b", fg="#fff",
                       selectcolor="#FF9800", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=5)

        # API Key 输入框
        tk.Label(row1, text="Key:", bg="#2b2b2b", fg="#ddd",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(15, 0))
        self.custom_key_var = tk.StringVar(value="")
        self.key_input = tk.Entry(row1, textvariable=self.custom_key_var, width=16, bg="#404040", fg="#0f0",
                                  insertbackground="#fff", font=("Consolas", 9))
        self.key_input.pack(side=tk.LEFT, padx=(5, 3))
        tk.Button(row1, text="📋", command=lambda: self._copy_custom_key(),
                  bg="#555", fg="#fff", font=("Microsoft YaHei", 8),
                  relief="flat", padx=4, pady=1, cursor="hand2").pack(side=tk.LEFT)

        # ---- 配置变更追踪 ----
        self._prev_port = self.port_var.get()
        self._prev_auth = self.auth_var.get()
        self._prev_hide_pin = self.hide_pin_var.get()
        self._prev_key = self.custom_key_var.get()
        self.port_var.trace_add("write", self._on_port_changed)
        self.auth_var.trace_add("write", self._on_auth_changed)
        self.hide_pin_var.trace_add("write", self._on_hide_pin_changed)
        self.key_input.bind("<FocusOut>", lambda e: self._on_key_changed())

        # ---- 日志输出区 ----
        log_frame = tk.LabelFrame(self.root, text=" 📋 服务器日志 ", bg="#2b2b2b", fg="#aaa",
                                  font=("Microsoft YaHei", 10), padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, bg="#1e1e1e", fg="#00ff00",
                                                  font=("Consolas", 9), wrap=tk.WORD,
                                                  insertbackground="#00ff00", state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_config("INFO", foreground="#00ff00")
        self.log_text.tag_config("WARNING", foreground="#FFA500")
        self.log_text.tag_config("ERROR", foreground="#f44336")
        self.log_text.tag_config("SUCCESS", foreground="#4CAF50")

    # ============================================================
    #  日志输出
    # ============================================================
    def _log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {msg}\n"
        display_line = line
        if self.hide_pin_var.get():
            lower_msg = msg.lower()
            if "key" in lower_msg:
                display_line = f"[{timestamp}] [{level}] ***PIN已隐藏***\n"
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, display_line, level)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        try:
            log_path = os.path.join(self.project_dir, "server_panel.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(display_line)
        except Exception:
            pass

    # ============================================================
    #  在线设备下拉列表
    # ============================================================
    def _toggle_dropdown(self):
        if self._dropdown_open:
            self._close_dropdown()
        else:
            self._show_dropdown()

    def _show_dropdown(self):
        if self._dropdown_open:
            return
        self._dropdown_open = True
        self.device_dropdown_btn.config(text="▲")

        # 创建下拉窗口
        self._dropdown_win = tk.Toplevel(self.root)
        self._dropdown_win.overrideredirect(True)
        self._dropdown_win.configure(bg="#333")

        # 计算位置：在设备数量按钮下方
        btn_x = self.device_dropdown_btn.winfo_rootx()
        btn_y = self.device_dropdown_btn.winfo_rooty() + self.device_dropdown_btn.winfo_height()
        self._dropdown_win.geometry(f"420x200+{btn_x}+{btn_y}")

        # 内容框架
        inner = tk.Frame(self._dropdown_win, bg="#333", padx=8, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        if not self.server_running:
            tk.Label(inner, text="服务器未运行", bg="#333", fg="#888",
                     font=("Microsoft YaHei", 10)).pack(pady=20)
        elif not self._online_devices:
            tk.Label(inner, text="暂无设备连接", bg="#333", fg="#888",
                     font=("Microsoft YaHei", 10)).pack(pady=20)
        else:
            for dev in self._online_devices:
                self._add_device_row(inner, dev)

        # 点击外部关闭
        self._dropdown_win.bind("<FocusOut>", lambda e: self._close_dropdown())
        self._dropdown_win.focus_set()

        # 3秒后自动刷新
        if self.server_running:
            self._dropdown_win.after(3000, self._refresh_dropdown)

    def _add_device_row(self, parent, dev):
        """添加一个设备行"""
        row = tk.Frame(parent, bg="#3a3a3a", padx=8, pady=6)
        row.pack(fill=tk.X, pady=(0, 4))

        # 左侧：设备信息
        left = tk.Frame(row, bg="#3a3a3a")
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 第一行：名称 + 状态
        name_text = dev.get("display_name", "未知设备")
        if dev.get("kicked"):
            name_text += " [已踢出]"
        tk.Label(left, text=f"🟢 {name_text}", bg="#3a3a3a", fg="#fff",
                 font=("Microsoft YaHei", 9, "bold"), anchor="w").pack(fill=tk.X)

        # 第二行：IP + 连接时长 + 检测次数
        conn_secs = dev.get("connected_seconds", 0)
        hours = conn_secs // 3600
        mins = (conn_secs % 3600) // 60
        if hours > 0:
            conn_str = f"{hours}小时{mins}分"
        else:
            conn_str = f"{mins}分钟"

        info_text = f"    {dev.get('ip', '?')}  ·  连接 {conn_str}  ·  检测 {dev.get('detect_count', 0)}次"
        tk.Label(left, text=info_text, bg="#3a3a3a", fg="#aaa",
                 font=("Consolas", 8), anchor="w").pack(fill=tk.X)

        # 右侧：断开按钮
        kick_btn = tk.Button(
            row, text="断开", bg="#f44336", fg="#fff",
            font=("Microsoft YaHei", 8, "bold"),
            relief="flat", padx=8, pady=2, cursor="hand2",
            activebackground="#d32f2f",
            command=lambda ip=dev.get("ip"): self._kick_device(ip)
        )
        kick_btn.pack(side=tk.RIGHT, padx=(5, 0))

    def _kick_device(self, ip):
        """踢出设备"""
        if not self.server_running:
            return
        port = self.port_var.get().strip()
        def do_kick():
            try:
                url = f"http://localhost:{port}/api/kick-device"
                data = json.dumps({"ip": ip}).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    result = json.loads(resp.read().decode())
                    if result.get("ok"):
                        self.root.after(0, lambda: self._log(f"已踢出设备: {ip}", "WARNING"))
                        self.root.after(0, self._refresh_online_devices)
                    else:
                        self.root.after(0, lambda: self._log(f"踢出失败: {result}", "ERROR"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"踢出异常: {e}", "ERROR"))
        threading.Thread(target=do_kick, daemon=True).start()

    def _close_dropdown(self):
        self._dropdown_open = False
        self.device_dropdown_btn.config(text="▼")
        if self._dropdown_win:
            try:
                self._dropdown_win.destroy()
            except Exception:
                pass
            self._dropdown_win = None

    def _refresh_dropdown(self):
        """刷新下拉列表内容"""
        if not self._dropdown_open or not self._dropdown_win:
            return
        self._refresh_online_devices()
        # 重建下拉内容
        try:
            for w in self._dropdown_win.winfo_children():
                w.destroy()
        except Exception:
            return

        inner = tk.Frame(self._dropdown_win, bg="#333", padx=8, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        if not self._online_devices:
            tk.Label(inner, text="暂无设备连接", bg="#333", fg="#888",
                     font=("Microsoft YaHei", 10)).pack(pady=20)
        else:
            for dev in self._online_devices:
                self._add_device_row(inner, dev)

        # 继续刷新
        if self._dropdown_open:
            self._dropdown_win.after(3000, self._refresh_dropdown)

    def _refresh_online_devices(self):
        """从服务器获取在线设备列表"""
        if not self.server_running:
            self._online_devices = []
            self._update_device_count(0)
            return
        port = self.port_var.get().strip()
        def fetch():
            try:
                url = f"http://localhost:{port}/api/online-devices"
                with urllib.request.urlopen(url, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    devices = data.get("devices", [])
                    count = data.get("count", len(devices))
                    self._online_devices = devices
                    self.root.after(0, lambda: self._update_device_count(count))
            except Exception:
                self._online_devices = []
                self.root.after(0, lambda: self._update_device_count(0))
        threading.Thread(target=fetch, daemon=True).start()

    def _update_device_count(self, count):
        """更新设备数量显示"""
        self.device_count = count
        self.device_count_label.config(text=f"📡 {count}台设备")

    def _start_device_loop(self):
        """定时轮询在线设备"""
        self._refresh_online_devices()
        self.root.after(3000, self._start_device_loop)

    # ============================================================
    #  启动服务器
    # ============================================================
    def _start_server(self):
        if self.server_running:
            return

        if not os.path.exists(self.web_server_path):
            self._log(f"找不到 web_server.py: {self.web_server_path}", "ERROR")
            messagebox.showerror("错误", f"找不到 web_server.py\n路径: {self.web_server_path}")
            return

        port = self.port_var.get().strip()
        auth = self.auth_var.get()

        cmd = [sys.executable, self.web_server_path, "--port", port]
        if not auth:
            cmd.append("--no-auth")
        custom_key = self.custom_key_var.get().strip()
        if custom_key:
            cmd.extend(["--api-key", custom_key])

        self._log(f"启动命令: {' '.join(cmd)}", "INFO")

        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.project_dir,
                startupinfo=startupinfo,
            )
            self.server_running = True
            self._update_ui_state(True)
            self._log(f"进程已启动  PID={self.server_process.pid}", "SUCCESS")

            self.log_thread = threading.Thread(target=self._read_log, daemon=True)
            self.log_thread.start()

            # 启动在线设备轮询
            self.root.after(3000, self._start_device_loop)

        except Exception as e:
            self._log(f"启动失败: {e}", "ERROR")
            messagebox.showerror("启动失败", str(e))

    def _read_log(self):
        try:
            for line in self.server_process.stdout:
                line = line.rstrip()
                if not line:
                    continue
                if "/api/ping" in line:
                    continue
                if "WARNING" in line or "warn" in line.lower():
                    self.root.after(0, self._log, line, "WARNING")
                elif "ERROR" in line or "error" in line.lower() or "Traceback" in line:
                    self.root.after(0, self._log, line, "ERROR")
                elif "Uvicorn" in line or "Started server" in line or "Application startup" in line:
                    self.root.after(0, self._log, line, "SUCCESS")
                else:
                    self.root.after(0, self._log, line, "INFO")
        except Exception:
            pass
        finally:
            if self.server_running:
                self.root.after(0, self._on_server_stopped)

    # ============================================================
    #  停止服务器
    # ============================================================
    def _stop_server(self):
        if not self.server_running or not self.server_process:
            return
        self._log("正在停止服务器...", "WARNING")
        try:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._log("强制终止进程...", "ERROR")
                self.server_process.kill()
                self.server_process.wait(timeout=3)
            self._log("服务器已停止", "SUCCESS")
        except Exception as e:
            self._log(f"停止失败: {e}", "ERROR")
        finally:
            self.server_running = False
            self.server_process = None
            self._online_devices = []
            self._update_ui_state(False)

    def _on_server_stopped(self):
        self.server_running = False
        self.server_process = None
        self._online_devices = []
        self._update_ui_state(False)
        self._log("服务器进程已退出", "WARNING")

    # ============================================================
    #  重启
    # ============================================================
    def _restart_server(self):
        self._stop_server()
        self.root.after(500, self._start_server)

    # ============================================================
    #  UI 状态更新
    # ============================================================
    def _update_ui_state(self, running):
        if running:
            self.status_dot.config(fg="#4CAF50")
            self.status_label.config(text="运行中", fg="#4CAF50")
            self.local_dot.config(fg="#4CAF50")
            self.lan_dot.config(fg="#4CAF50")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.restart_btn.config(state=tk.NORMAL)
            port = self.port_var.get().strip()
            local_ip = self._get_local_ip()
            self.local_url_var.set(f"http://localhost:{port}")
            self.lan_url_var.set(f"http://{local_ip}:{port}")
            if self.tailscale_ip:
                self.ts_url_var.set(f"http://{self.tailscale_ip}:{port}")
            self._fetch_api_key(port)
        else:
            self.status_dot.config(fg="#f44336")
            self.status_label.config(text="未运行", fg="#aaa")
            self.local_dot.config(fg="#f44336")
            self.lan_dot.config(fg="#f44336")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.restart_btn.config(state=tk.DISABLED)
            self.local_url_var.set("http://-- 未启动 --")
            self.lan_url_var.set("http://-- 未启动 --")
            self.key_frame.pack_forget()
            self._update_device_count(0)
            if self.tailscale_ip:
                port_off = self.port_var.get().strip()
                self.ts_url_var.set(f"http://{self.tailscale_ip}:{port_off}")

    # ============================================================
    #  Tailscale 穿墙检测
    # ============================================================
    def _detect_tailscale(self):
        def detect():
            try:
                result = subprocess.run(
                    ["tailscale", "status"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if result.returncode != 0:
                    self.root.after(0, lambda: self._set_tailscale_state(False, None, "未安装"))
                    return
                ip_result = subprocess.run(
                    ["tailscale", "ip", "-4"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                ts_ip = ip_result.stdout.strip() if ip_result.returncode == 0 else None
                if ts_ip:
                    self.root.after(0, lambda: self._set_tailscale_state(True, ts_ip, "已连接"))
                else:
                    self.root.after(0, lambda: self._set_tailscale_state(False, None, "未连接"))
            except FileNotFoundError:
                self.root.after(0, lambda: self._set_tailscale_state(False, None, "未安装"))
            except Exception:
                self.root.after(0, lambda: self._set_tailscale_state(False, None, "检测失败"))
        threading.Thread(target=detect, daemon=True).start()

    def _set_tailscale_state(self, connected, ip, status_text):
        self.tailscale_online = connected
        self.tailscale_ip = ip
        port = self.port_var.get().strip()
        if connected and ip:
            self.ts_status_dot.config(fg="#4CAF50")
            self.ts_url_var.set(f"http://{ip}:{port}")
            self._log(f"Tailscale 已连接  IP={ip}", "SUCCESS")
        else:
            self.ts_status_dot.config(fg="#f44336")
            self.ts_url_var.set(f"-- {status_text} --")
            if status_text == "未安装":
                self._log("Tailscale 未安装，穿墙功能不可用", "WARNING")
            else:
                self._log(f"Tailscale {status_text}", "WARNING")

    def _open_tailscale_admin(self):
        import webbrowser
        webbrowser.open("https://login.tailscale.com/admin/machines")
        self._log("已打开 Tailscale 管理后台", "INFO")

    def _start_tailscale(self):
        def run():
            try:
                self.root.after(0, lambda: self._log("正在启动 Tailscale...", "INFO"))
                result = subprocess.run(
                    ["tailscale", "up"],
                    capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if result.returncode == 0:
                    self.root.after(0, lambda: self._log("Tailscale 启动成功", "SUCCESS"))
                    self._detect_tailscale()
                else:
                    err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                    self.root.after(0, lambda: self._log(f"Tailscale 启动失败: {err}", "ERROR"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Tailscale 启动异常: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _stop_tailscale(self):
        def run():
            try:
                self.root.after(0, lambda: self._log("正在停止 Tailscale...", "WARNING"))
                result = subprocess.run(
                    ["tailscale", "down"],
                    capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if result.returncode == 0:
                    self.root.after(0, lambda: self._log("Tailscale 已停止", "SUCCESS"))
                else:
                    err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                    self.root.after(0, lambda: self._log(f"Tailscale 停止失败: {err}", "ERROR"))
                self._detect_tailscale()
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Tailscale 停止异常: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _fetch_api_key(self, port):
        def fetch():
            try:
                time.sleep(1.5)
                health_url = f"http://localhost:{port}/api/health"
                with urllib.request.urlopen(health_url, timeout=3) as resp:
                    health = json.loads(resp.read().decode())
                    if not health.get("auth", True):
                        self.root.after(0, lambda: self.key_frame.pack_forget())
                        return
                key_url = f"http://localhost:{port}/api/key"
                with urllib.request.urlopen(key_url, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    key = data.get("key", "--")
                    self.root.after(0, lambda: self.key_var.set(key))
                    self.root.after(0, lambda: self.key_frame.pack(fill=tk.X, padx=10, pady=(0, 5)))
            except Exception:
                self.root.after(0, lambda: self.key_var.set("获取失败"))
        threading.Thread(target=fetch, daemon=True).start()

    # ============================================================
    #  定时检查进程状态
    # ============================================================
    def _check_loop(self):
        if self.server_running and self.server_process:
            if self.server_process.poll() is not None:
                self._on_server_stopped()
        self.root.after(2000, self._check_loop)

    # ============================================================
    #  关闭
    # ============================================================
    def _on_close(self):
        self._close_dropdown()
        if self.server_running:
            if messagebox.askyesno("确认退出", "服务器正在运行，关闭面板将同时停止服务器。\n确定退出？"):
                self._stop_server()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        try:
            log_path = os.path.join(self.project_dir, "server_panel.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"面板启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*60}\n")
        except Exception:
            pass
        self._log("服务器管理面板已启动", "INFO")
        self._log(f"项目路径: {self.project_dir}", "INFO")
        self._log(f"Web服务器: {self.web_server_path}", "INFO")
        self._log("─" * 50, "INFO")
        self._log("点击 [▶ 启动服务器] 开始", "INFO")
        self.root.after(2000, self._check_loop)
        self.root.mainloop()


if __name__ == "__main__":
    panel = ServerPanel()
    panel.run()
