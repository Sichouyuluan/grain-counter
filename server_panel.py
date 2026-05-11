"""
小麦籽粒检测 - 服务器管理面板
- 一键启动/关闭 FastAPI Web 服务器
- 实时显示运行状态
- 地址栏（本机 + 局域网 + Tailscale 穿墙）
- API Key 管理 + 认证开关
- 在线设备下拉列表
- 实时日志面板
- Tailscale 检测/控制
"""
import os
import sys
import time
import json
import subprocess
import threading
import socket
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext, messagebox
from datetime import datetime
import urllib.request


class ServerPanel:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🌾 小麦籽粒检测 - 服务器管理面板")
        self.root.geometry("740x620")
        self.root.configure(bg="#1e1e1e")
        self.root.resizable(True, True)

        # 服务进程状态
        self.server_process = None
        self.server_running = False
        self.log_thread = None

        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_server_path = os.path.join(self.project_dir, "web_server.py")

        # Tailscale 状态
        self.tailscale_ip = None
        self.tailscale_online = False

        # 在线设备
        self._online_devices = []
        self._dropdown_open = False
        self._dropdown_win = None
        self.device_count = 0
        self.valuable_count = 0

        # 上次值（用于变更检测）
        self._prev_port = "8000"
        self._prev_auth = True
        self._prev_key = ""

        self._build_ui()
        self._load_saved_key()
        self._detect_tailscale()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ============================================================
    #  工具方法
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

    def _url_for_port(self, host):
        port = self.port_var.get().strip()
        return f"http://{host}:{port}"

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
        # ---- 顶部标题 ----
        title_frame = tk.Frame(self.root, bg="#2d2d2d", height=48)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="🌾 小麦籽粒检测 Web 服务器",
                 bg="#2d2d2d", fg="#fff",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # ---- 状态栏 ----
        self._build_status_bar()

        # ---- 地址栏 ----
        self._build_address_bar()

        # ---- API Key 栏 ----
        self._build_key_bar()

        # ---- 控制按钮 ----
        self._build_control_buttons()

        # ---- 配置区 ----
        self._build_config_section()

        # ---- 日志面板 ----
        self._build_log_panel()

    def _build_status_bar(self):
        frame = tk.Frame(self.root, bg="#2b2b2b", height=36)
        frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        frame.pack_propagate(False)

        tk.Label(frame, text="状态:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(10, 5))
        self.status_dot = tk.Label(frame, text="●", bg="#2b2b2b", fg="#f44336",
                                   font=("Consolas", 12, "bold"))
        self.status_dot.pack(side=tk.LEFT)
        self.status_label = tk.Label(frame, text="未运行", bg="#2b2b2b", fg="#aaa",
                                     font=("Microsoft YaHei", 10))
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))

        tk.Label(frame, text="  |  ", bg="#2b2b2b", fg="#555",
                 font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)

        # 设备计数 + 下拉
        self.device_count_label = tk.Label(frame, text="📡 0台设备", bg="#2b2b2b", fg="#aaa",
                                           font=("Microsoft YaHei", 10))
        self.device_count_label.pack(side=tk.LEFT, padx=(0, 2))
        self.device_dropdown_btn = tk.Button(
            frame, text="▼", bg="#2b2b2b", fg="#aaa",
            font=("Consolas", 9, "bold"), relief="flat",
            activebackground="#3a3a3a", activeforeground="#fff",
            bd=0, padx=4, pady=0, cursor="hand2",
            command=self._toggle_dropdown
        )
        self.device_dropdown_btn.pack(side=tk.LEFT, padx=(0, 5))

    def _build_address_bar(self):
        outer = tk.Frame(self.root, bg="#2b2b2b")
        outer.pack(fill=tk.X, padx=10, pady=(5, 5))

        def make_entry_row(parent, label_text, var, color="#0f0"):
            row = tk.Frame(parent, bg="#2b2b2b")
            row.pack(fill=tk.X, pady=(0, 3))
            dot = tk.Label(row, text="●", bg="#2b2b2b", fg="#f44336",
                           font=("Consolas", 9, "bold"))
            dot.pack(side=tk.LEFT, padx=(2, 0))
            tk.Label(row, text=label_text, bg="#2b2b2b", fg="#aaa",
                     font=("Microsoft YaHei", 9), width=7, anchor="w").pack(side=tk.LEFT)
            entry = tk.Entry(row, textvariable=var,
                             bg="#404040", fg=color, font=("Consolas", 10),
                             insertbackground="#fff", readonlybackground="#404040",
                             state="readonly")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            tk.Button(row, text="📋 复制",
                      command=lambda v=var: self._copy_url(v),
                      bg="#555", fg="#fff", font=("Microsoft YaHei", 9),
                      relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT)
            tk.Button(row, text="🔗 打开",
                      command=lambda v=var: self._open_url(v),
                      bg="#6C63FF", fg="#fff", font=("Microsoft YaHei", 9),
                      relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(5, 0))
            return dot

        self.local_url_var = tk.StringVar(value="http://-- 未启动 --")
        self.lan_url_var = tk.StringVar(value="http://-- 未启动 --")
        self.ts_url_var = tk.StringVar(value="检测中...")

        self.local_dot = make_entry_row(outer, "💻 本机:", self.local_url_var, "#0f0")
        self.lan_dot = make_entry_row(outer, "📱 局域网:", self.lan_url_var, "#0ff")

        # Tailscale 行（带管理后台按钮）
        ts_row = tk.Frame(outer, bg="#2b2b2b")
        ts_row.pack(fill=tk.X)
        self.ts_status_dot = tk.Label(ts_row, text="●", bg="#2b2b2b", fg="#f44336",
                                      font=("Consolas", 9, "bold"))
        self.ts_status_dot.pack(side=tk.LEFT, padx=(2, 0))
        tk.Label(ts_row, text="🌐 穿墙:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 9), width=7, anchor="w").pack(side=tk.LEFT)
        ts_entry = tk.Entry(ts_row, textvariable=self.ts_url_var,
                            bg="#404040", fg="#ff0", font=("Consolas", 10),
                            insertbackground="#fff", readonlybackground="#404040",
                            state="readonly")
        ts_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(ts_row, text="📋 复制", command=lambda: self._copy_url(self.ts_url_var),
                  bg="#555", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(ts_row, text="🔗 打开", command=lambda: self._open_url(self.ts_url_var),
                  bg="#6C63FF", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(5, 0))
        tk.Button(ts_row, text="🔗 管理后台", command=self._open_tailscale_admin,
                  bg="#6C63FF", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT)

    def _build_key_bar(self):
        self.key_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.key_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        row = tk.Frame(self.key_frame, bg="#2b2b2b")
        row.pack(fill=tk.X)

        key_row = tk.Frame(row, bg="#2b2b2b")
        key_row.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(key_row, text="🔑 Key:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 9), width=8, anchor="w").pack(side=tk.LEFT)
        self.key_var = tk.StringVar(value="--")
        key_entry = tk.Entry(key_row, textvariable=self.key_var,
                             bg="#404040", fg="#0f0", font=("Consolas", 10),
                             insertbackground="#fff", state="readonly", readonlybackground="#404040")
        key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(key_row, text="📋 复制", command=lambda: self._copy_url(self.key_var),
                  bg="#555", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT)

    def _build_control_buttons(self):
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        self.start_btn = self._make_button(btn_frame, "▶  启动服务器", "#4CAF50",
                                           self._start_server, state=tk.NORMAL)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_btn = self._make_button(btn_frame, "⏹  停止服务器", "#f44336",
                                          self._stop_server, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.restart_btn = self._make_button(btn_frame, "🔄 重启", "#FF9800",
                                             self._restart_server, state=tk.DISABLED)
        self.restart_btn.pack(side=tk.LEFT, padx=(0, 15))

        sep = tk.Frame(btn_frame, bg="#555", width=1, height=30)
        sep.pack(side=tk.LEFT, padx=5)

        self.ts_start_btn = self._make_button(btn_frame, "🌐 启动穿墙", "#2196F3",
                                              self._start_tailscale)
        self.ts_start_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.ts_stop_btn = self._make_button(btn_frame, "🌐 停止穿墙", "#795548",
                                             self._stop_tailscale)
        self.ts_stop_btn.pack(side=tk.LEFT)

    @staticmethod
    def _make_button(parent, text, color, command, state=tk.NORMAL, font_size=11):
        is_main = "启动" in text or "停止" in text
        font = ("Microsoft YaHei", font_size, "bold") if is_main else ("Microsoft YaHei", font_size)
        return tk.Button(parent, text=text, command=command,
                         bg=color, fg="#fff", font=font,
                         relief="flat", padx=20 if is_main else 15,
                         pady=8, activebackground=color, cursor="hand2",
                         state=state)

    def _build_config_section(self):
        config_frame = tk.LabelFrame(self.root, text=" 配置 ", bg="#2b2b2b", fg="#aaa",
                                     font=("Microsoft YaHei", 10), padx=12, pady=8)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        row1 = tk.Frame(config_frame, bg="#2b2b2b")
        row1.pack(fill=tk.X, pady=(0, 4))

        # 端口
        tk.Label(row1, text="端口:", bg="#2b2b2b", fg="#ddd",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="8000")
        port_entry = tk.Entry(row1, textvariable=self.port_var, width=8,
                              bg="#404040", fg="#fff", insertbackground="#fff",
                              font=("Consolas", 10))
        port_entry.pack(side=tk.LEFT, padx=(5, 20))
        self.port_var.trace_add("write", lambda *a: self._on_port_changed())

        # API 认证
        tk.Label(row1, text="API认证:", bg="#2b2b2b", fg="#ddd",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.auth_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row1, variable=self.auth_var, bg="#2b2b2b", fg="#fff",
                       selectcolor="#4CAF50", font=("Microsoft YaHei", 9),
                       command=self._on_auth_changed).pack(side=tk.LEFT, padx=5)

        # 自定义 Key
        tk.Label(row1, text="Key:", bg="#2b2b2b", fg="#ddd",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(15, 0))
        self.custom_key_var = tk.StringVar(value="")
        self.key_input = tk.Entry(row1, textvariable=self.custom_key_var, width=18,
                                  bg="#404040", fg="#0f0", insertbackground="#fff",
                                  font=("Consolas", 9))
        self.key_input.pack(side=tk.LEFT, padx=(5, 3))
        self.key_input.bind("<FocusOut>", lambda e: self._on_key_changed())
        tk.Button(row1, text="📋", command=self._copy_custom_key,
                  bg="#555", fg="#fff", font=("Microsoft YaHei", 8),
                  relief="flat", padx=6, pady=1, cursor="hand2").pack(side=tk.LEFT, padx=(0, 15))

        # 优质照片计数
        tk.Label(row1, text="📸 已保存:", bg="#2b2b2b", fg="#aaa",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.valuable_count_label = tk.Label(row1, text="0张", bg="#2b2b2b", fg="#4CAF50",
                                             font=("Microsoft YaHei", 9, "bold"))
        self.valuable_count_label.pack(side=tk.LEFT, padx=(2, 0))
        tk.Button(row1, text="📂 打开", command=self._open_valuable_dir,
                  bg="#6C63FF", fg="#fff", font=("Microsoft YaHei", 9),
                  relief="flat", padx=8, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=(5, 0))

        # 保存初始值
        self._prev_port = self.port_var.get()
        self._prev_auth = self.auth_var.get()
        self._prev_key = self.custom_key_var.get()

    def _build_log_panel(self):
        log_frame = tk.LabelFrame(self.root, text=" 📋 服务器日志 ", bg="#2b2b2b", fg="#aaa",
                                  font=("Microsoft YaHei", 10), padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        inner = tk.Frame(log_frame, bg="#1e1e1e")
        inner.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(inner, bg="#1e1e1e", fg="#00ff00",
                                font=("Consolas", 9), wrap=tk.WORD,
                                insertbackground="#00ff00", state=tk.DISABLED,
                                relief="flat", bd=0, highlightthickness=0)

        scrollbar = tk.Scrollbar(inner, orient=tk.VERTICAL, command=self.log_text.yview,
                                 bg="#3a3a3a", troughcolor="#2b2b2b",
                                 activebackground="#555", highlightthickness=0,
                                 bd=0, width=10)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for tag, color in [("INFO", "#00ff00"), ("WARNING", "#FFA500"),
                           ("ERROR", "#f44336"), ("SUCCESS", "#4CAF50")]:
            self.log_text.tag_config(tag, foreground=color)

    # ============================================================
    #  剪贴板 & URL 操作
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

    # ============================================================
    #  配置变更
    # ============================================================
    def _on_port_changed(self):
        new_val = self.port_var.get()
        if new_val != self._prev_port:
            self._log(f"端口修改: {self._prev_port} → {new_val}", "INFO")
            self._prev_port = new_val
            self._update_urls()

    def _on_auth_changed(self):
        new_val = self.auth_var.get()
        if new_val != self._prev_auth:
            label = "开启" if new_val else "关闭"
            self._log(f"API 认证: {label}", "INFO")
            self._prev_auth = new_val
            if self.server_running:
                self._toggle_auth_on_server(new_val)

    def _on_key_changed(self):
        new_val = self.custom_key_var.get().strip()
        if new_val != self._prev_key:
            self._log(f"API Key 已修改", "INFO")
            self._prev_key = new_val

    def _toggle_auth_on_server(self, enable):
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
                        self.root.after(0, lambda: self._log(f"服务器 API 认证已{state}（热切换）", "SUCCESS"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"热切换异常: {e}", "ERROR"))
        threading.Thread(target=do_toggle, daemon=True).start()

    def _load_saved_key(self):
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
            self._prev_key = saved
        except Exception:
            pass

    # ============================================================
    #  日志
    # ============================================================
    def _log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {msg}\n"
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, line, level)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        try:
            log_path = os.path.join(self.project_dir, "server_panel.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    # ============================================================
    #  在线设备下拉
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
        self._dropdown_win = tk.Toplevel(self.root)
        self._dropdown_win.overrideredirect(True)
        self._dropdown_win.configure(bg="#333")
        btn_x = self.device_dropdown_btn.winfo_rootx()
        btn_y = self.device_dropdown_btn.winfo_rooty() + self.device_dropdown_btn.winfo_height()
        self._dropdown_win.geometry(f"440x240+{btn_x}+{btn_y}")
        self._rebuild_dropdown_content()
        self._dropdown_win.bind("<FocusOut>", lambda e: self._close_dropdown())
        self._dropdown_win.focus_set()
        if self.server_running:
            self._dropdown_win.after(3000, self._refresh_dropdown)

    def _rebuild_dropdown_content(self):
        if not self._dropdown_win:
            return
        for w in self._dropdown_win.winfo_children():
            w.destroy()
        inner = tk.Frame(self._dropdown_win, bg="#333", padx=8, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        if not self.server_running:
            tk.Label(inner, text="服务器未运行", bg="#333", fg="#888",
                     font=("Microsoft YaHei", 10)).pack(pady=20)
        elif not self._online_devices:
            tk.Label(inner, text="暂无设备连接", bg="#333", fg="#888",
                     font=("Microsoft YaHei", 10)).pack(pady=20)
        else:
            canvas = tk.Canvas(inner, bg="#333", highlightthickness=0)
            scrollbar = tk.Scrollbar(inner, orient=tk.VERTICAL, command=canvas.yview)
            scroll_frame = tk.Frame(canvas, bg="#333")
            scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set, width=420, height=200)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            for dev in self._online_devices:
                self._add_device_row(scroll_frame, dev)

    def _add_device_row(self, parent, dev):
        row = tk.Frame(parent, bg="#3a3a3a", padx=8, pady=6)
        row.pack(fill=tk.X, pady=(0, 4))

        left = tk.Frame(row, bg="#3a3a3a")
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        name = dev.get("display_name", "未知设备")
        if dev.get("kicked"):
            name += " [已踢出]"
        tk.Label(left, text=f"🟢 {name}", bg="#3a3a3a", fg="#fff",
                 font=("Microsoft YaHei", 9, "bold"), anchor="w").pack(fill=tk.X)

        conn_secs = dev.get("connected_seconds", 0)
        hours, mins = conn_secs // 3600, (conn_secs % 3600) // 60
        conn_str = f"{hours}小时{mins}分" if hours > 0 else f"{mins}分钟"
        info = f"    {dev.get('ip', '?')}  ·  连接 {conn_str}  ·  检测 {dev.get('detect_count', 0)}次"
        tk.Label(left, text=info, bg="#3a3a3a", fg="#aaa",
                 font=("Consolas", 8), anchor="w").pack(fill=tk.X)

        kick_btn = tk.Button(row, text="断开", bg="#f44336", fg="#fff",
                             font=("Microsoft YaHei", 8, "bold"),
                             relief="flat", padx=8, pady=2, cursor="hand2",
                             command=lambda ip=dev.get("ip"): self._kick_device(ip))
        kick_btn.pack(side=tk.RIGHT, padx=(5, 0))

    def _kick_device(self, ip):
        if not self.server_running:
            return
        port = self.port_var.get().strip()
        def do_kick():
            try:
                url = f"http://localhost:{port}/api/kick-device"
                data = json.dumps({"ip": ip}).encode("utf-8")
                req = urllib.request.Request(url, data=data,
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if json.loads(resp.read().decode()).get("ok"):
                        self.root.after(0, lambda: self._log(f"已踢出设备: {ip}", "WARNING"))
                        self.root.after(0, self._refresh_online_devices)
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
        if not self._dropdown_open or not self._dropdown_win:
            return
        self._refresh_online_devices()
        self._rebuild_dropdown_content()
        if self._dropdown_open:
            self._dropdown_win.after(3000, self._refresh_dropdown)

    def _refresh_online_devices(self):
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
                    self._online_devices = data.get("devices", [])
                    self.root.after(0, lambda: self._update_device_count(data.get("count", 0)))
            except Exception:
                self._online_devices = []
                self.root.after(0, lambda: self._update_device_count(0))
        threading.Thread(target=fetch, daemon=True).start()

    def _update_device_count(self, count):
        self.device_count = count
        self.device_count_label.config(text=f"📡 {count}台设备")

    def _start_device_loop(self):
        self._refresh_online_devices()
        self.root.after(3000, self._start_device_loop)

    # ============================================================
    #  服务器控制
    # ============================================================
    def _start_server(self):
        if self.server_running:
            return
        if not os.path.exists(self.web_server_path):
            self._log(f"找不到 web_server.py: {self.web_server_path}", "ERROR")
            messagebox.showerror("错误", f"找不到 web_server.py")
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

            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=self.project_dir, startupinfo=startupinfo,
            )
            self.server_running = True
            self._update_ui_state(True)
            self._log(f"进程已启动  PID={self.server_process.pid}", "SUCCESS")
            self.log_thread = threading.Thread(target=self._read_log, daemon=True)
            self.log_thread.start()
            self.root.after(3000, self._start_device_loop)
            self.root.after(5000, self._poll_valuable_stats)
        except Exception as e:
            self._log(f"启动失败: {e}", "ERROR")
            messagebox.showerror("启动失败", str(e))

    def _read_log(self):
        try:
            for line in self.server_process.stdout:
                line = line.rstrip()
                if not line or "/api/ping" in line or "/api/health" in line:
                    continue
                if "WARNING" in line or "warn" in line.lower():
                    level = "WARNING"
                elif "ERROR" in line or "error" in line.lower() or "Traceback" in line:
                    level = "ERROR"
                elif "SUCCESS" in line:
                    level = "SUCCESS"
                else:
                    level = "INFO"
                self.root.after(0, self._log, line, level)
        except Exception:
            pass
        finally:
            if self.server_running:
                self.root.after(0, self._on_server_stopped)

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

    def _restart_server(self):
        self._stop_server()
        self.root.after(500, self._start_server)

    # ============================================================
    #  UI 状态
    # ============================================================
    def _update_ui_state(self, running):
        colors = ("#4CAF50", "#f44336")
        dot_color = colors[0] if running else colors[1]
        self.status_dot.config(fg=dot_color)
        self.local_dot.config(fg=dot_color)
        self.lan_dot.config(fg=dot_color)
        self.status_label.config(text="运行中" if running else "未运行",
                                 fg=colors[0] if running else "#aaa")
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        self.restart_btn.config(state=tk.NORMAL if running else tk.DISABLED)

        if running:
            self._update_urls()
            self._fetch_api_key()
        else:
            self.local_url_var.set("http://-- 未启动 --")
            self.lan_url_var.set("http://-- 未启动 --")
            self.key_frame.pack_forget()
            self._update_device_count(0)

    def _update_urls(self):
        port = self.port_var.get().strip()
        local_ip = self._get_local_ip()
        self.local_url_var.set(f"http://localhost:{port}")
        self.lan_url_var.set(f"http://{local_ip}:{port}")
        if self.tailscale_ip:
            self.ts_url_var.set(f"http://{self.tailscale_ip}:{port}")

    # ============================================================
    #  Tailscale
    # ============================================================
    def _detect_tailscale(self):
        def detect():
            try:
                result = subprocess.run(
                    ["tailscale", "status"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                if result.returncode != 0:
                    self.root.after(0, lambda: self._set_tailscale_state(False, None, "未安装"))
                    return
                ip_result = subprocess.run(
                    ["tailscale", "ip", "-4"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                ts_ip = ip_result.stdout.strip() if ip_result.returncode == 0 else None
                self.root.after(0, lambda: self._set_tailscale_state(
                    bool(ts_ip), ts_ip, "已连接" if ts_ip else "未连接"))
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

    def _open_tailscale_admin(self):
        import webbrowser
        webbrowser.open("https://login.tailscale.com/admin/machines")
        self._log("已打开 Tailscale 管理后台", "INFO")

    def _start_tailscale(self):
        def run():
            self.root.after(0, lambda: self._log("正在启动 Tailscale...", "INFO"))
            try:
                result = subprocess.run(
                    ["tailscale", "up"], capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                if result.returncode == 0:
                    self.root.after(0, lambda: self._log("Tailscale 启动成功", "SUCCESS"))
                    self._detect_tailscale()
                else:
                    err = result.stderr.strip() or "未知错误"
                    self.root.after(0, lambda: self._log(f"Tailscale 启动失败: {err}", "ERROR"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Tailscale 启动异常: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _stop_tailscale(self):
        def run():
            self.root.after(0, lambda: self._log("正在停止 Tailscale...", "WARNING"))
            try:
                result = subprocess.run(
                    ["tailscale", "down"], capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                if result.returncode == 0:
                    self.root.after(0, lambda: self._log("Tailscale 已停止", "SUCCESS"))
                self._detect_tailscale()
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Tailscale 停止异常: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _fetch_api_key(self):
        port = self.port_var.get().strip()
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
                    self.root.after(0, lambda: self.key_var.set(data.get("key", "--")))
                    self.root.after(0, lambda: self.key_frame.pack(fill=tk.X, padx=10, pady=(0, 5)))
            except Exception:
                self.root.after(0, lambda: self.key_var.set("获取失败"))
        threading.Thread(target=fetch, daemon=True).start()

    # ============================================================
    #  优质照片
    # ============================================================
    def _open_valuable_dir(self):
        vdir = os.path.join(self.project_dir, "Valuable photos")
        os.makedirs(vdir, exist_ok=True)
        os.startfile(vdir)
        self._log(f"已打开优质照片目录: {vdir}", "SUCCESS")

    def _poll_valuable_stats(self):
        if not self.server_running:
            self.root.after(5000, self._poll_valuable_stats)
            return
        port = self.port_var.get().strip()
        def fetch():
            try:
                url = f"http://localhost:{port}/api/valuable-stats"
                with urllib.request.urlopen(url, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    self.root.after(0, lambda: self._update_valuable_count(data.get("total_count", 0)))
            except Exception:
                pass
            self.root.after(5000, self._poll_valuable_stats)
        threading.Thread(target=fetch, daemon=True).start()

    def _update_valuable_count(self, count):
        self.valuable_count = count
        self.valuable_count_label.config(text=f"{count}张")

    # ============================================================
    #  进程检查
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
                f.write(f"\n{'='*60}\n面板启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*60}\n")
        except Exception:
            pass
        self._log("服务器管理面板已启动", "INFO")
        self._log("点击 [▶ 启动服务器] 开始", "INFO")
        self.root.after(2000, self._check_loop)
        self.root.mainloop()


if __name__ == "__main__":
    panel = ServerPanel()
    panel.run()
