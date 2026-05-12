"""
小麦籽粒检测 — 服务器管理面板
===============================
磨砂玻璃质感 (Frosted Glass) 主题
一键启动/管理 FastAPI Web 服务器

功能:
  - 一键启停 Web 服务器 (子进程)
  - 本机 / 局域网 / Tailscale 地址栏
  - API Key 管理 + 认证热切换
  - 在线设备追踪 + 踢出
  - 实时日志面板
  - Tailscale 穿墙检测/控制
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import messagebox


# ──────────────────────────────────────────────
#  Theme palette — frosted glass on dark
# ──────────────────────────────────────────────
class Theme:
    bg           = "#0d0f14"   # 最深底色
    surface      = "#161a22"   # 卡片表面
    surface_alt  = "#1c212b"   # 次要表面
    border       = "#262d3a"   # 边框
    border_light = "#333d4d"   # 高亮边框
    text         = "#e4e8ee"   # 主文字
    text_dim     = "#8892a6"   # 辅助文字
    accent       = "#4ade80"   # 绿色强调
    accent_glow  = "#4ade8033" # 绿色辉光 (rgba)
    blue         = "#60a5fa"   # 蓝色
    blue_glow    = "#60a5fa33"
    orange       = "#fb923c"   # 橙色
    red          = "#f87171"   # 红色
    font         = "Microsoft YaHei"
    font_mono    = "Consolas"


def _glass_frame(parent, **kw):
    """创建一个磨砂玻璃卡片容器"""
    kw.setdefault("bg", Theme.surface)
    kw.setdefault("highlightbackground", Theme.border)
    kw.setdefault("highlightthickness", 1)
    kw.setdefault("bd", 0)
    return tk.Frame(parent, **kw)


def _glass_label(parent, text="", **kw):
    kw.setdefault("bg", Theme.surface)
    kw.setdefault("fg", Theme.text)
    kw.setdefault("font", (Theme.font, 10))
    return tk.Label(parent, text=text, **kw)


def _glass_button(parent, text, color, command, **kw):
    """磨砂玻璃按钮 — 带 hover 高亮"""
    kw.setdefault("font", (Theme.font, 10))
    kw.setdefault("relief", "flat")
    kw.setdefault("bd", 0)
    kw.setdefault("padx", 14)
    kw.setdefault("pady", 6)
    kw.setdefault("cursor", "hand2")
    kw.setdefault("activebackground", color)
    kw.setdefault("activeforeground", "#fff")
    kw.setdefault("fg", "#fff")
    return tk.Button(parent, text=text, bg=color,
                     command=command, **kw)


def _glass_entry(parent, var=None, **kw):
    kw.setdefault("bg", Theme.surface_alt)
    kw.setdefault("fg", Theme.text)
    kw.setdefault("insertbackground", Theme.text)
    kw.setdefault("font", (Theme.font_mono, 10))
    kw.setdefault("relief", "flat")
    kw.setdefault("bd", 0)
    kw.setdefault("highlightbackground", Theme.border)
    kw.setdefault("highlightthickness", 1)
    return tk.Entry(parent, textvariable=var, **kw)


# ──────────────────────────────────────────────
#  Main Application
# ──────────────────────────────────────────────
class ServerPanel:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Grain Counter — 服务器管理面板")
        self.root.geometry("780x680")
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

        # 在线设备
        self._online_devices: list[dict] = []
        self._dropdown_open = False
        self._dropdown_win: tk.Toplevel | None = None
        self._device_count = 0
        self._valuable_count = 0

        # 变更追踪
        self._prev_port = "8000"
        self._prev_key = ""

        # 隐藏轮询开关（默认开启）
        self.hide_poll_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._load_saved_key()
        self._detect_tailscale()
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
        """悬浮 Toast 提示"""
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
    #  UI 构建
    # ═══════════════════════════════════════════

    def _build_ui(self):
        # ── 顶部标题 ──
        header = tk.Frame(self.root, bg=Theme.surface, height=52,
                          highlightbackground=Theme.border,
                          highlightthickness=0, bd=0)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        # 底部装饰线
        tk.Frame(header, bg=Theme.border, height=1).pack(side=tk.BOTTOM, fill=tk.X)

        inner_h = tk.Frame(header, bg=Theme.surface)
        inner_h.pack(expand=True, fill=tk.BOTH, padx=16)
        _glass_label(inner_h, text="🌾  Grain Counter",
                     font=(Theme.font, 15, "bold"),
                     fg=Theme.text, bg=Theme.surface).pack(side=tk.LEFT)
        _glass_label(inner_h, text="服务器管理面板",
                     font=(Theme.font, 10),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT, padx=(10, 0))

        # ── 主体（可滚动 / 内容区）──
        body = tk.Frame(self.root, bg=Theme.bg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 12))

        # 网格布局：上半部 (3 列卡片)，下半部日志
        body.grid_rowconfigure(2, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=1)

        # ---- 卡片 1: 运行状态 ----
        self._build_status_card(body)

        # ---- 卡片 2: 快速操作 ----
        self._build_action_card(body)

        # ---- 卡片 3: 地址 ----
        self._build_address_card(body)

        # ---- 卡片 4: 配置 (横跨 3 列) ----
        self._build_config_card(body)

        # ---- 卡片 5: 日志 (横跨 3 列, 占据剩余空间) ----
        self._build_log_card(body)

    # ── 卡片 1: 状态 ──
    def _build_status_card(self, parent):
        card = _glass_frame(parent,
                            highlightbackground=Theme.border,
                            highlightthickness=1, bd=0)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 6))

        # 标题行
        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(10, 6))
        _glass_label(title_row, text="运行状态",
                     font=(Theme.font, 10, "bold"),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        # 状态指示
        status_row = tk.Frame(card, bg=Theme.surface)
        status_row.pack(fill=tk.X, padx=12, pady=(4, 10))

        self.status_dot = tk.Label(status_row, text="●",
                                   bg=Theme.surface, fg=Theme.red,
                                   font=(Theme.font_mono, 16, "bold"))
        self.status_dot.pack(side=tk.LEFT)
        self.status_label = _glass_label(status_row, text="未运行",
                                         fg=Theme.text_dim,
                                         bg=Theme.surface,
                                         font=(Theme.font, 11))
        self.status_label.pack(side=tk.LEFT, padx=(6, 0))

        # 分隔
        tk.Frame(status_row, bg=Theme.border, width=1, height=16)\
            .pack(side=tk.LEFT, padx=(14, 10))

        # 设备
        self.device_count_label = _glass_label(status_row, text="📡 0 台设备",
                                               fg=Theme.text_dim,
                                               bg=Theme.surface,
                                               font=(Theme.font, 10))
        self.device_count_label.pack(side=tk.LEFT)
        self.device_dropdown_btn = tk.Button(
            status_row, text="▼", bg=Theme.surface, fg=Theme.text_dim,
            font=(Theme.font_mono, 9, "bold"), relief="flat", bd=0,
            padx=4, pady=0, cursor="hand2", activebackground=Theme.surface_alt,
            command=self._toggle_dropdown)
        self.device_dropdown_btn.pack(side=tk.LEFT, padx=(3, 0))

        # 优质照片计数
        valuable_row = tk.Frame(card, bg=Theme.surface)
        valuable_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        _glass_label(valuable_row, text="📸 优质照片:",
                     font=(Theme.font, 9), fg=Theme.text_dim,
                     bg=Theme.surface).pack(side=tk.LEFT)
        self.valuable_count_label = _glass_label(valuable_row, text="0 张",
                                                 font=(Theme.font, 9, "bold"),
                                                 fg=Theme.accent,
                                                 bg=Theme.surface)
        self.valuable_count_label.pack(side=tk.LEFT, padx=(4, 0))
        _glass_button(valuable_row, "📂 打开", Theme.blue,
                      self._open_valuable_dir,
                      font=(Theme.font, 8), padx=8, pady=2).pack(side=tk.RIGHT)

    # ── 卡片 2: 快速操作 ──
    def _build_action_card(self, parent):
        card = _glass_frame(parent,
                            highlightbackground=Theme.border,
                            highlightthickness=1, bd=0)
        card.grid(row=0, column=1, sticky="nsew", padx=4, pady=(0, 6))

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(10, 6))
        _glass_label(title_row, text="快速操作",
                     font=(Theme.font, 10, "bold"),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        # 按钮组
        btn_row = tk.Frame(card, bg=Theme.surface)
        btn_row.pack(fill=tk.X, padx=12, pady=(4, 10))

        self.start_btn = _glass_button(btn_row, "▶  启动", Theme.accent,
                                       self._start_server,
                                       font=(Theme.font, 10, "bold"),
                                       padx=14, pady=8, width=7)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.stop_btn = _glass_button(btn_row, "⏹  停止", Theme.red,
                                      self._stop_server,
                                      font=(Theme.font, 10, "bold"),
                                      padx=14, pady=8, width=7, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.restart_btn = _glass_button(btn_row, "🔄 重启", Theme.orange,
                                         self._restart_server,
                                         padx=14, pady=8, width=6,
                                         state=tk.DISABLED)
        self.restart_btn.pack(side=tk.LEFT)

        # Tailscale 行
        ts_row = tk.Frame(card, bg=Theme.surface)
        ts_row.pack(fill=tk.X, padx=12, pady=(0, 10))

        _glass_label(ts_row, text="🌐  穿墙:",
                     font=(Theme.font, 9), fg=Theme.text_dim,
                     bg=Theme.surface).pack(side=tk.LEFT)

        self.ts_status_dot = tk.Label(ts_row, text="●",
                                      bg=Theme.surface, fg=Theme.red,
                                      font=(Theme.font_mono, 10))
        self.ts_status_dot.pack(side=tk.LEFT, padx=(2, 0))

        self.ts_start_btn = _glass_button(ts_row, "启动", Theme.blue,
                                          self._start_tailscale,
                                          font=(Theme.font, 8), padx=8, pady=2)
        self.ts_start_btn.pack(side=tk.RIGHT, padx=(3, 0))
        self.ts_stop_btn = _glass_button(ts_row, "停止", Theme.border_light,
                                         self._stop_tailscale,
                                         font=(Theme.font, 8), padx=8, pady=2)
        self.ts_stop_btn.pack(side=tk.RIGHT, padx=(0, 3))

    # ── 卡片 3: 地址 ──
    def _build_address_card(self, parent):
        card = _glass_frame(parent,
                            highlightbackground=Theme.border,
                            highlightthickness=1, bd=0)
        card.grid(row=0, column=2, sticky="nsew", padx=(4, 0), pady=(0, 6))

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(10, 6))
        _glass_label(title_row, text="访问地址",
                     font=(Theme.font, 10, "bold"),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        addr_frame = tk.Frame(card, bg=Theme.surface)
        addr_frame.pack(fill=tk.X, padx=12, pady=(4, 10))

        def make_addr_row(parent, icon, label_text, var, dot_color):
            row = tk.Frame(parent, bg=Theme.surface)
            row.pack(fill=tk.X, pady=(0, 4))

            dot = tk.Label(row, text="●", bg=Theme.surface,
                           fg=dot_color, font=(Theme.font_mono, 8))
            dot.pack(side=tk.LEFT, padx=(0, 4))

            _glass_label(row, text=f"{icon} {label_text}",
                         font=(Theme.font, 8), fg=Theme.text_dim,
                         width=5, anchor="w",
                         bg=Theme.surface).pack(side=tk.LEFT)

            entry = tk.Entry(row, textvariable=var,
                             bg=Theme.surface_alt, fg=dot_color,
                             font=(Theme.font_mono, 9),
                             readonlybackground=Theme.surface_alt,
                             relief="flat", bd=0,
                             highlightbackground=Theme.border,
                             highlightthickness=1,
                             state="readonly")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 4))

            tk.Button(row, text="📋", command=lambda v=var: self._copy_url(v),
                      bg=Theme.surface_alt, fg=Theme.text_dim,
                      font=(Theme.font, 8), relief="flat", bd=0,
                      padx=4, pady=1, cursor="hand2",
                      activebackground=Theme.border)\
                .pack(side=tk.LEFT, padx=(0, 2))
            tk.Button(row, text="🔗", command=lambda v=var: self._open_url(v),
                      bg=Theme.surface_alt, fg=Theme.blue,
                      font=(Theme.font, 8), relief="flat", bd=0,
                      padx=4, pady=1, cursor="hand2",
                      activebackground=Theme.border)\
                .pack(side=tk.LEFT)

            return dot

        self.local_url_var = tk.StringVar(value="http://-- 未启动 --")
        self.lan_url_var = tk.StringVar(value="http://-- 未启动 --")
        self.ts_url_var = tk.StringVar(value="检测中...")

        self.local_dot = make_addr_row(addr_frame, "💻", "本机",
                                       self.local_url_var, Theme.accent)
        self.lan_dot = make_addr_row(addr_frame, "📱", "局域网",
                                     self.lan_url_var, Theme.blue)
        make_addr_row(addr_frame, "🌐", "穿墙",
                      self.ts_url_var, "#facc15")

    # ── 卡片 4: 配置 ──
    def _build_config_card(self, parent):
        card = _glass_frame(parent,
                            highlightbackground=Theme.border,
                            highlightthickness=1, bd=0)
        card.grid(row=1, column=0, columnspan=3, sticky="nsew",
                  padx=0, pady=(0, 6))

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(8, 4))
        _glass_label(title_row, text="配置",
                     font=(Theme.font, 10, "bold"),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        row = tk.Frame(card, bg=Theme.surface)
        row.pack(fill=tk.X, padx=12, pady=(2, 8))

        # 端口
        _glass_label(row, text="端口:", font=(Theme.font, 9),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="8000")
        port_entry = _glass_entry(row, var=self.port_var, width=6,
                                  font=(Theme.font_mono, 10))
        port_entry.pack(side=tk.LEFT, padx=(4, 16))
        self.port_var.trace_add("write", lambda *a: self._on_port_changed())

        # API 认证
        _glass_label(row, text="API 认证:", font=(Theme.font, 9),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)
        self.auth_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row, variable=self.auth_var, bg=Theme.surface, fg=Theme.text,
                       selectcolor=Theme.surface, activebackground=Theme.surface,
                       activeforeground=Theme.text, highlightthickness=0,
                       command=self._on_auth_changed).pack(side=tk.LEFT, padx=4)

        # 自定义 Key
        _glass_label(row, text="Key:", font=(Theme.font, 9),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT, padx=(12, 0))
        self.custom_key_var = tk.StringVar(value="")
        key_input = _glass_entry(row, var=self.custom_key_var, width=18,
                                 font=(Theme.font_mono, 9))
        key_input.pack(side=tk.LEFT, padx=(4, 2))
        key_input.bind("<FocusOut>", lambda e: self._on_key_changed())
        tk.Button(row, text="📋", command=self._copy_custom_key,
                  bg=Theme.surface_alt, fg=Theme.text_dim,
                  font=(Theme.font, 8), relief="flat", bd=0,
                  padx=5, pady=1, cursor="hand2",
                  activebackground=Theme.border).pack(side=tk.LEFT)

        # 隐藏轮询
        _glass_label(row, text="", bg=Theme.surface, width=2).pack(side=tk.LEFT)
        tk.Checkbutton(row, variable=self.hide_poll_var,
                       bg=Theme.surface, fg=Theme.text_dim,
                       selectcolor=Theme.surface, activebackground=Theme.surface,
                       activeforeground=Theme.text, highlightthickness=0,
                       font=(Theme.font, 8)).pack(side=tk.LEFT)
        _glass_label(row, text="隐藏轮询", font=(Theme.font, 8),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        # 保存初始值
        self._prev_port = self.port_var.get()
        self._prev_key = self.custom_key_var.get()

    # ── 卡片 5: 日志 ──
    def _build_log_card(self, parent):
        card = _glass_frame(parent,
                            highlightbackground=Theme.border,
                            highlightthickness=1, bd=0)
        card.grid(row=2, column=0, columnspan=3, sticky="nsew",
                  padx=0, pady=0)

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(8, 4))
        _glass_label(title_row, text="服务器日志",
                     font=(Theme.font, 10, "bold"),
                     fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        # API Key 显示行（启动后出现）
        self.key_frame = tk.Frame(card, bg=Theme.surface)
        key_row = tk.Frame(self.key_frame, bg=Theme.surface)
        key_row.pack(fill=tk.X, padx=12, pady=(0, 4))
        _glass_label(key_row, text="🔑 当前 Key:",
                     font=(Theme.font, 9), fg=Theme.text_dim,
                     bg=Theme.surface, width=10, anchor="w").pack(side=tk.LEFT)
        self.key_var = tk.StringVar(value="--")
        key_entry = _glass_entry(key_row, var=self.key_var,
                                 state="readonly", readonlybackground=Theme.surface_alt,
                                 font=(Theme.font_mono, 9))
        key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        _glass_button(key_row, "📋 复制",
                      Theme.surface_alt, lambda: self._copy_url(self.key_var),
                      font=(Theme.font, 8), padx=8, pady=1,
                      fg=Theme.text_dim,
                      activeforeground=Theme.text).pack(side=tk.LEFT)

        # 日志文本框
        log_outer = tk.Frame(card, bg=Theme.bg)
        log_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 10))

        self.log_text = tk.Text(log_outer, bg="#0a0c10", fg=Theme.accent,
                                font=(Theme.font_mono, 9), wrap=tk.WORD,
                                insertbackground=Theme.accent, state=tk.DISABLED,
                                relief="flat", bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(log_outer, orient=tk.VERTICAL,
                                 command=self.log_text.yview,
                                 bg=Theme.surface_alt, troughcolor=Theme.bg,
                                 activebackground=Theme.border,
                                 highlightthickness=0, bd=0, width=8)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for tag, color in [("INFO", Theme.accent), ("WARNING", Theme.orange),
                           ("ERROR", Theme.red), ("SUCCESS", Theme.blue)]:
            self.log_text.tag_config(tag, foreground=color)

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
            self._toggle_auth_on_server(v)

    def _on_key_changed(self):
        v = self.custom_key_var.get().strip()
        if v != self._prev_key:
            self._log("Key 已修改", "INFO")
            self._prev_key = v

    def _toggle_auth_on_server(self, enable: bool):
        port = self.port_var.get().strip()
        def run():
            try:
                url = f"http://localhost:{port}/api/toggle-auth"
                req = urllib.request.Request(url, data=b"{}", method="POST",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    r = json.loads(resp.read().decode())
                    if r.get("ok"):
                        s = "ON" if r.get("auth") else "OFF"
                        self.root.after(0, lambda: self._log(f"认证已切换: {s}（热切换）", "SUCCESS"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"认证切换失败: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

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

    def _log(self, msg: str, level="INFO"):
        # 隐藏轮询开关：过滤后台轮询消息
        if self.hide_poll_var.get() and any(
            kw in msg for kw in [
                "/api/online-devices", "/api/valuable-stats",
                "/api/ping", "/api/health",
                "台设备", "设备数量",
            ]
        ):
            return
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] {msg}\n"
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, line, level)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        try:
            lp = os.path.join(self.project_dir, "server_panel.log")
            with open(lp, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    # ═══════════════════════════════════════════
    #  在线设备下拉
    # ═══════════════════════════════════════════

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
        self._dropdown_win.configure(bg=Theme.surface_alt)
        bx = self.device_dropdown_btn.winfo_rootx()
        by = self.device_dropdown_btn.winfo_rooty() + self.device_dropdown_btn.winfo_height()
        self._dropdown_win.geometry(f"440x240+{bx}+{by}")
        self._rebuild_dropdown()
        self._dropdown_win.bind("<FocusOut>", lambda e: self._close_dropdown())
        self._dropdown_win.focus_set()
        if self.server_running:
            self._dropdown_win.after(3000, self._refresh_dropdown)

    def _rebuild_dropdown(self):
        if not self._dropdown_win:
            return
        for w in self._dropdown_win.winfo_children():
            w.destroy()
        inner = tk.Frame(self._dropdown_win, bg=Theme.surface_alt, padx=8, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        if not self.server_running:
            _glass_label(inner, text="服务器未运行", fg=Theme.text_dim,
                         bg=Theme.surface_alt).pack(pady=20)
        elif not self._online_devices:
            _glass_label(inner, text="暂无设备连接", fg=Theme.text_dim,
                         bg=Theme.surface_alt).pack(pady=20)
        else:
            canvas = tk.Canvas(inner, bg=Theme.surface_alt, highlightthickness=0)
            sb = tk.Scrollbar(inner, orient=tk.VERTICAL, command=canvas.yview,
                              bg=Theme.surface_alt, troughcolor=Theme.bg)
            sf = tk.Frame(canvas, bg=Theme.surface_alt)
            sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=sf, anchor="nw")
            canvas.configure(yscrollcommand=sb.set, width=420, height=200)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            for dev in self._online_devices:
                self._add_device_row(sf, dev)

    def _add_device_row(self, parent, dev):
        row = tk.Frame(parent, bg=Theme.surface, padx=8, pady=5)
        row.pack(fill=tk.X, pady=(0, 3))
        left = tk.Frame(row, bg=Theme.surface)
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        name = dev.get("display_name", "未知")
        if dev.get("kicked"):
            name += " [已踢出]"
        _glass_label(left, text=f"🟢 {name}", font=(Theme.font, 9, "bold"),
                     fg=Theme.text, bg=Theme.surface, anchor="w").pack(fill=tk.X)

        secs = dev.get("connected_seconds", 0)
        h, m = secs // 3600, (secs % 3600) // 60
        conn = f"{h}h{m}m" if h > 0 else f"{m}m"
        info = f"    {dev.get('ip','?')}  ·  {conn}  ·  {dev.get('detect_count',0)} 次检测"
        _glass_label(left, text=info, font=(Theme.font_mono, 8),
                     fg=Theme.text_dim, bg=Theme.surface, anchor="w").pack(fill=tk.X)

        tk.Button(row, text="断开", bg=Theme.red, fg="#fff",
                  font=(Theme.font, 8, "bold"), relief="flat", bd=0,
                  padx=8, pady=2, cursor="hand2",
                  command=lambda ip=dev.get("ip"): self._kick_device(ip))\
            .pack(side=tk.RIGHT)

    def _kick_device(self, ip: str):
        if not self.server_running:
            return
        port = self.port_var.get().strip()
        def run():
            try:
                url = f"http://localhost:{port}/api/kick-device"
                data = json.dumps({"ip": ip}).encode("utf-8")
                req = urllib.request.Request(url, data=data,
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if json.loads(resp.read().decode()).get("ok"):
                        self.root.after(0, lambda: self._log(f"已踢出: {ip}", "WARNING"))
                        self.root.after(0, self._refresh_online_devices)
            except Exception as e:
                self.root.after(0, lambda: self._log(f"踢出失败: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

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
        self._rebuild_dropdown()
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

    def _update_device_count(self, count: int):
        self._device_count = count
        self.device_count_label.config(text=f"📡 {count} 台设备")

    def _start_device_loop(self):
        self._refresh_online_devices()
        self.root.after(3000, self._start_device_loop)

    # ═══════════════════════════════════════════
    #  服务器控制
    # ═══════════════════════════════════════════

    def _start_server(self):
        if self.server_running:
            return
        if not os.path.exists(self.web_server_path):
            self._log("找不到 web_server.py", "ERROR")
            messagebox.showerror("错误", "找不到 web_server.py")
            return

        port = self.port_var.get().strip()
        auth = self.auth_var.get()
        cmd = [sys.executable, self.web_server_path, "--port", port]
        if not auth:
            cmd.append("--no-auth")
        custom_key = self.custom_key_var.get().strip()
        if custom_key:
            cmd.extend(["--api-key", custom_key])

        self._log(f"启动: {' '.join(cmd)}", "INFO")
        try:
            si = None
            if sys.platform == "win32":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=self.project_dir, startupinfo=si)
            self.server_running = True
            self._update_ui_state(True)
            self._log(f"PID={self.server_process.pid}", "SUCCESS")
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
                if any(x in line.lower() for x in ("warn", "warning")):
                    lvl = "WARNING"
                elif any(x in line for x in ("ERROR", "error", "Traceback")):
                    lvl = "ERROR"
                elif "SUCCESS" in line:
                    lvl = "SUCCESS"
                else:
                    lvl = "INFO"
                self.root.after(0, self._log, line, lvl)
        except Exception:
            pass
        finally:
            if self.server_running:
                self.root.after(0, self._on_server_stopped)

    def _stop_server(self):
        if not self.server_running or not self.server_process:
            return
        self._log("正在停止...", "WARNING")
        try:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._log("强制终止...", "ERROR")
                self.server_process.kill()
                self.server_process.wait(timeout=3)
            self._log("已停止", "SUCCESS")
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
        self._log("进程已退出", "WARNING")

    def _restart_server(self):
        self._stop_server()
        self.root.after(500, self._start_server)

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
            self.root.after(1500, self._fetch_api_key)
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
    #  Tailscale
    # ═══════════════════════════════════════════

    def _detect_tailscale(self):
        def run():
            try:
                r = subprocess.run(["tailscale", "status"],
                                   capture_output=True, text=True, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                if r.returncode != 0:
                    self.root.after(0, lambda: self._set_ts(False, None, "未安装"))
                    return
                ip_r = subprocess.run(["tailscale", "ip", "-4"],
                                      capture_output=True, text=True, timeout=5,
                                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                ts_ip = ip_r.stdout.strip() if ip_r.returncode == 0 else None
                self.root.after(0, lambda: self._set_ts(bool(ts_ip), ts_ip, "已连接" if ts_ip else "未连接"))
            except FileNotFoundError:
                self.root.after(0, lambda: self._set_ts(False, None, "未安装"))
            except Exception:
                self.root.after(0, lambda: self._set_ts(False, None, "检测失败"))
        threading.Thread(target=run, daemon=True).start()

    def _set_ts(self, connected: bool, ip: str | None, status_text: str):
        self.tailscale_online = connected
        self.tailscale_ip = ip
        port = self.port_var.get().strip()
        if connected and ip:
            self.ts_status_dot.config(fg=Theme.accent)
            self.ts_url_var.set(f"http://{ip}:{port}")
            self._log(f"Tailscale: {ip}", "SUCCESS")
        else:
            self.ts_status_dot.config(fg=Theme.red)
            self.ts_url_var.set(f"-- {status_text} --")

    def _start_tailscale(self):
        def run():
            self.root.after(0, lambda: self._log("启动 Tailscale...", "INFO"))
            try:
                r = subprocess.run(["tailscale", "up"],
                                   capture_output=True, text=True, timeout=30,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                if r.returncode == 0:
                    self.root.after(0, lambda: self._log("Tailscale 已启动", "SUCCESS"))
                    self._detect_tailscale()
                else:
                    self.root.after(0, lambda: self._log(f"启动失败: {r.stderr.strip() or '未知'}", "ERROR"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"异常: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _stop_tailscale(self):
        def run():
            self.root.after(0, lambda: self._log("停止 Tailscale...", "WARNING"))
            try:
                r = subprocess.run(["tailscale", "down"],
                                   capture_output=True, text=True, timeout=15,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                if r.returncode == 0:
                    self.root.after(0, lambda: self._log("Tailscale 已停止", "SUCCESS"))
                self._detect_tailscale()
            except Exception as e:
                self.root.after(0, lambda: self._log(f"异常: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _fetch_api_key(self):
        port = self.port_var.get().strip()
        def run():
            try:
                time.sleep(1.0)
                hurl = f"http://localhost:{port}/api/health"
                with urllib.request.urlopen(hurl, timeout=3) as resp:
                    h = json.loads(resp.read().decode())
                    if not h.get("auth", True):
                        self.root.after(0, lambda: self._safe_pack_forget(self.key_frame))
                        return
                kurl = f"http://localhost:{port}/api/key"
                with urllib.request.urlopen(kurl, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    self.root.after(0, lambda: self.key_var.set(data.get("key", "--")))
            except Exception:
                self.root.after(0, lambda: self.key_var.set("获取失败"))
        threading.Thread(target=run, daemon=True).start()

    # ═══════════════════════════════════════════
    #  优质照片
    # ═══════════════════════════════════════════

    def _open_valuable_dir(self):
        vdir = os.path.join(self.project_dir, "Valuable photos")
        try:
            if not os.path.isdir(vdir):
                os.makedirs(vdir, exist_ok=True)
        except FileExistsError:
            pass
        try:
            subprocess.Popen(["explorer", vdir],
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            self._log(f"已打开: {vdir}", "SUCCESS")
        except Exception as e:
            self._log(f"打开失败: {e}", "ERROR")

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

    def _update_valuable_count(self, count: int):
        self._valuable_count = count
        self.valuable_count_label.config(text=f"{count} 张")

    # ═══════════════════════════════════════════
    #  进程检查 & 关闭
    # ═══════════════════════════════════════════

    def _check_loop(self):
        if self.server_running and self.server_process:
            if self.server_process.poll() is not None:
                self._on_server_stopped()
        self.root.after(2000, self._check_loop)

    def _on_close(self):
        self._close_dropdown()
        if self.server_running:
            if messagebox.askyesno("确认退出",
                                   "服务器正在运行，关闭面板将停止服务器。\n确定退出？"):
                self._stop_server()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        try:
            lp = os.path.join(self.project_dir, "server_panel.log")
            with open(lp, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*50}\n面板启动: {datetime.now():%Y-%m-%d %H:%M:%S}\n{'='*50}\n")
        except Exception:
            pass
        self._log("管理面板已启动", "INFO")
        self._log("点击 [▶ 启动] 开始 Web 服务器", "INFO")
        self.root.after(2000, self._check_loop)
        self.root.mainloop()


if __name__ == "__main__":
    ServerPanel().run()
