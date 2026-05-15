"""服务器管理面板 — UI 构建（卡片、下拉、设备行）"""
import tkinter as tk
import tkinter.ttk as ttk
from graincounter.theme import Theme, glass_frame, glass_label, glass_button, glass_entry


class PanelUI:
    """UI 构建 mixin（由 ServerPanel 继承）"""

    def _build_ui(self):
        # ── 顶部标题 ──
        header = tk.Frame(self.root, bg=Theme.surface, height=52,
                          highlightbackground=Theme.border,
                          highlightthickness=0, bd=0)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Frame(header, bg=Theme.border, height=1).pack(side=tk.BOTTOM, fill=tk.X)
        inner_h = tk.Frame(header, bg=Theme.surface)
        inner_h.pack(expand=True, fill=tk.BOTH, padx=16)
        glass_label(inner_h, text="🌾  Grain Counter",
                    font=(Theme.font, 15, "bold"),
                    fg=Theme.text, bg=Theme.surface).pack(side=tk.LEFT)
        glass_label(inner_h, text="服务器管理面板",
                    font=(Theme.font, 10),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT, padx=(10, 0))

        # ── 主体 ──
        body = tk.Frame(self.root, bg=Theme.bg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 12))
        body.grid_rowconfigure(2, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=1)

        self._build_status_card(body)
        self._build_action_card(body)
        self._build_address_card(body)
        self._build_config_card(body)
        self._build_log_card(body)

    # ── 卡片 1: 状态 ──

    def _build_status_card(self, parent):
        card = glass_frame(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 6))

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(10, 6))
        glass_label(title_row, text="运行状态",
                    font=(Theme.font, 10, "bold"),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        status_row = tk.Frame(card, bg=Theme.surface)
        status_row.pack(fill=tk.X, padx=12, pady=(4, 10))

        self.status_dot = tk.Label(status_row, text="●",
                                   bg=Theme.surface, fg=Theme.red,
                                   font=(Theme.font_mono, 16, "bold"))
        self.status_dot.pack(side=tk.LEFT)
        self.status_label = glass_label(status_row, text="未运行",
                                        fg=Theme.text_dim, bg=Theme.surface,
                                        font=(Theme.font, 11))
        self.status_label.pack(side=tk.LEFT, padx=(6, 0))

        tk.Frame(status_row, bg=Theme.border, width=1, height=16)\
            .pack(side=tk.LEFT, padx=(14, 10))

        self.device_count_label = glass_label(status_row, text="📡 0 台设备",
                                              fg=Theme.text_dim, bg=Theme.surface,
                                              font=(Theme.font, 10))
        self.device_count_label.pack(side=tk.LEFT)
        self.device_dropdown_btn = tk.Button(
            status_row, text="▼", bg=Theme.surface, fg=Theme.text_dim,
            font=(Theme.font_mono, 9, "bold"), relief="flat", bd=0,
            padx=4, pady=0, cursor="hand2", activebackground=Theme.surface_alt,
            command=self._toggle_dropdown)
        self.device_dropdown_btn.pack(side=tk.LEFT, padx=(3, 0))

        valuable_row = tk.Frame(card, bg=Theme.surface)
        valuable_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        glass_label(valuable_row, text="📸 优质照片:",
                    font=(Theme.font, 9), fg=Theme.text_dim,
                    bg=Theme.surface).pack(side=tk.LEFT)
        self.valuable_count_label = glass_label(valuable_row, text="0 张",
                                                font=(Theme.font, 9, "bold"),
                                                fg=Theme.accent, bg=Theme.surface)
        self.valuable_count_label.pack(side=tk.LEFT, padx=(4, 0))
        glass_button(valuable_row, "📂 打开", Theme.blue,
                     self._open_valuable_dir,
                     font=(Theme.font, 8), padx=8, pady=2).pack(side=tk.RIGHT)

    # ── 卡片 2: 快速操作 ──

    def _build_action_card(self, parent):
        card = glass_frame(parent)
        card.grid(row=0, column=1, sticky="nsew", padx=4, pady=(0, 6))

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(10, 6))
        glass_label(title_row, text="快速操作",
                    font=(Theme.font, 10, "bold"),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        btn_row = tk.Frame(card, bg=Theme.surface)
        btn_row.pack(fill=tk.X, padx=12, pady=(4, 10))

        self.start_btn = glass_button(btn_row, "▶  启动", Theme.accent,
                                      self._start_server,
                                      font=(Theme.font, 10, "bold"),
                                      padx=14, pady=8, width=7)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.stop_btn = glass_button(btn_row, "⏹  停止", Theme.red,
                                     self._stop_server,
                                     font=(Theme.font, 10, "bold"),
                                     padx=14, pady=8, width=7, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.restart_btn = glass_button(btn_row, "🔄 重启", Theme.orange,
                                        self._restart_server,
                                        padx=14, pady=8, width=6,
                                        state=tk.DISABLED)
        self.restart_btn.pack(side=tk.LEFT)

        ts_row = tk.Frame(card, bg=Theme.surface)
        ts_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        glass_label(ts_row, text="🌐  穿墙:",
                    font=(Theme.font, 9), fg=Theme.text_dim,
                    bg=Theme.surface).pack(side=tk.LEFT)
        self.ts_status_dot = tk.Label(ts_row, text="●",
                                      bg=Theme.surface, fg=Theme.red,
                                      font=(Theme.font_mono, 10))
        self.ts_status_dot.pack(side=tk.LEFT, padx=(2, 0))
        self.ts_start_btn = glass_button(ts_row, "启动", Theme.blue,
                                         self._start_tailscale,
                                         font=(Theme.font, 8), padx=8, pady=2)
        self.ts_start_btn.pack(side=tk.RIGHT, padx=(3, 0))
        self.ts_stop_btn = glass_button(ts_row, "停止", Theme.border_light,
                                        self._stop_tailscale,
                                        font=(Theme.font, 8), padx=8, pady=2)
        self.ts_stop_btn.pack(side=tk.RIGHT, padx=(0, 3))

    # ── 卡片 3: 地址 ──

    def _build_address_card(self, parent):
        card = glass_frame(parent)
        card.grid(row=0, column=2, sticky="nsew", padx=(4, 0), pady=(0, 6))

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(10, 6))
        glass_label(title_row, text="访问地址",
                    font=(Theme.font, 10, "bold"),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        addr_frame = tk.Frame(card, bg=Theme.surface)
        addr_frame.pack(fill=tk.X, padx=12, pady=(4, 10))

        def make_addr_row(p, icon, label_text, var, dot_color):
            row = tk.Frame(p, bg=Theme.surface)
            row.pack(fill=tk.X, pady=(0, 4))
            dot = tk.Label(row, text="●", bg=Theme.surface,
                           fg=dot_color, font=(Theme.font_mono, 8))
            dot.pack(side=tk.LEFT, padx=(0, 4))
            glass_label(row, text=f"{icon} {label_text}",
                        font=(Theme.font, 8), fg=Theme.text_dim,
                        width=5, anchor="w", bg=Theme.surface).pack(side=tk.LEFT)
            entry = tk.Entry(row, textvariable=var,
                             bg=Theme.surface_alt, fg=dot_color,
                             font=(Theme.font_mono, 9),
                             readonlybackground=Theme.surface_alt,
                             relief="flat", bd=0,
                             highlightbackground=Theme.border,
                             highlightthickness=1, state="readonly")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 4))
            tk.Button(row, text="📋", command=lambda v=var: self._copy_url(v),
                      bg=Theme.surface_alt, fg=Theme.text_dim,
                      font=(Theme.font, 8), relief="flat", bd=0,
                      padx=4, pady=1, cursor="hand2",
                      activebackground=Theme.border).pack(side=tk.LEFT, padx=(0, 2))
            tk.Button(row, text="🔗", command=lambda v=var: self._open_url(v),
                      bg=Theme.surface_alt, fg=Theme.blue,
                      font=(Theme.font, 8), relief="flat", bd=0,
                      padx=4, pady=1, cursor="hand2",
                      activebackground=Theme.border).pack(side=tk.LEFT)
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
        card = glass_frame(parent)
        card.grid(row=1, column=0, columnspan=3, sticky="nsew",
                  padx=0, pady=(0, 6))

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(8, 4))
        glass_label(title_row, text="配置",
                    font=(Theme.font, 10, "bold"),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        row = tk.Frame(card, bg=Theme.surface)
        row.pack(fill=tk.X, padx=12, pady=(2, 8))

        # 端口
        glass_label(row, text="端口:", font=(Theme.font, 9),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)
        port_entry = glass_entry(row, var=self.port_var, width=6,
                                 font=(Theme.font_mono, 10))
        port_entry.pack(side=tk.LEFT, padx=(4, 16))
        self.port_var.trace_add("write", lambda *a: self._on_port_changed())

        # API 认证
        glass_label(row, text="API 认证:", font=(Theme.font, 9),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)
        tk.Checkbutton(row, variable=self.auth_var, bg=Theme.surface, fg=Theme.text,
                       selectcolor=Theme.surface, activebackground=Theme.surface,
                       activeforeground=Theme.text, highlightthickness=0,
                       command=self._on_auth_changed).pack(side=tk.LEFT, padx=4)

        # 自定义 Key
        glass_label(row, text="Key:", font=(Theme.font, 9),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT, padx=(12, 0))
        key_input = glass_entry(row, var=self.custom_key_var, width=18,
                                font=(Theme.font_mono, 9))
        key_input.pack(side=tk.LEFT, padx=(4, 2))
        key_input.bind("<FocusOut>", lambda e: self._on_key_changed())
        tk.Button(row, text="📋", command=self._copy_custom_key,
                  bg=Theme.surface_alt, fg=Theme.text_dim,
                  font=(Theme.font, 8), relief="flat", bd=0,
                  padx=5, pady=1, cursor="hand2",
                  activebackground=Theme.border).pack(side=tk.LEFT)

        # 隐藏轮询
        glass_label(row, text="", bg=Theme.surface, width=2).pack(side=tk.LEFT)
        tk.Checkbutton(row, variable=self.hide_poll_var,
                       bg=Theme.surface, fg=Theme.text_dim,
                       selectcolor=Theme.surface, activebackground=Theme.surface,
                       activeforeground=Theme.text, highlightthickness=0,
                       font=(Theme.font, 8)).pack(side=tk.LEFT)
        glass_label(row, text="隐藏轮询", font=(Theme.font, 8),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        # 跟随滚动
        glass_label(row, text="", bg=Theme.surface, width=1).pack(side=tk.LEFT)
        tk.Checkbutton(row, variable=self.auto_scroll_var,
                       bg=Theme.surface, fg=Theme.text_dim,
                       selectcolor=Theme.surface, activebackground=Theme.surface,
                       activeforeground=Theme.text, highlightthickness=0,
                       font=(Theme.font, 8)).pack(side=tk.LEFT)
        glass_label(row, text="跟随滚动", font=(Theme.font, 8),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        # 模型选择 — 第二行
        row2 = tk.Frame(card, bg=Theme.surface)
        row2.pack(fill=tk.X, padx=12, pady=(0, 8))

        glass_label(row2, text="模型:", font=(Theme.font, 9),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value="加载中...")
        self.model_menu = ttk.Combobox(row2, textvariable=self.model_var,
                                       state="readonly", width=30)
        self.model_menu.pack(side=tk.LEFT, padx=(4, 6))

        glass_button(row2, "切换", Theme.blue, self._switch_model,
                     font=(Theme.font, 8), padx=8, pady=2).pack(side=tk.LEFT)
        glass_button(row2, "📂", Theme.surface_alt, self._open_models_dir,
                     font=(Theme.font, 8), padx=6, pady=2,
                     fg=Theme.text_dim).pack(side=tk.LEFT, padx=(4, 0))
        self.model_status_label = glass_label(row2, text="", font=(Theme.font, 8),
                                              fg=Theme.text_dim, bg=Theme.surface)
        self.model_status_label.pack(side=tk.LEFT, padx=(6, 0))

        # 运行统计 — 第三行
        row3 = tk.Frame(card, bg=Theme.surface)
        row3.pack(fill=tk.X, padx=12, pady=(0, 8))

        glass_label(row3, text="运行:", font=(Theme.font, 8),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)
        self.guard_label = glass_label(row3, text="扫描0次", font=(Theme.font, 8),
                                       fg=Theme.orange, bg=Theme.surface)
        self.guard_label.pack(side=tk.LEFT, padx=(4, 12))

        glass_label(row3, text="|", font=(Theme.font, 8),
                    fg=Theme.border_light, bg=Theme.surface).pack(side=tk.LEFT)

        self.error_label = glass_label(row3, text="错误0", font=(Theme.font, 8),
                                        fg=Theme.red, bg=Theme.surface)
        self.error_label.pack(side=tk.LEFT, padx=(12, 12))

        glass_label(row3, text="|", font=(Theme.font, 8),
                    fg=Theme.border_light, bg=Theme.surface).pack(side=tk.LEFT)

        self.detect_label = glass_label(row3, text="检测0次", font=(Theme.font, 8),
                                         fg=Theme.accent, bg=Theme.surface)
        self.detect_label.pack(side=tk.LEFT, padx=(12, 0))

        self._prev_port = self.port_var.get()
        self._prev_key = self.custom_key_var.get()

    # ── 卡片 5: 日志 ──

    def _build_log_card(self, parent):
        card = glass_frame(parent)
        card.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=0, pady=0)

        title_row = tk.Frame(card, bg=Theme.surface)
        title_row.pack(fill=tk.X, padx=12, pady=(8, 4))
        glass_label(title_row, text="服务器日志",
                    font=(Theme.font, 10, "bold"),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.LEFT)

        glass_label(title_row, text=" 过滤:", font=(Theme.font, 8),
                    fg=Theme.text_dim, bg=Theme.surface).pack(side=tk.RIGHT, padx=(0, 4))
        filter_menu = tk.OptionMenu(title_row, self.log_filter_var,
                                    "全部", "INFO", "WARNING", "ERROR", "SUCCESS", "SAVE",
                                    command=self._on_log_filter_changed)
        filter_menu.config(bg=Theme.surface_alt, fg=Theme.text_dim,
                           font=(Theme.font, 8), relief="flat", bd=0,
                           highlightthickness=0, activebackground=Theme.border, padx=0)
        filter_menu["menu"].config(bg=Theme.surface_alt, fg=Theme.text,
                                   font=(Theme.font, 8), bd=0)
        filter_menu.pack(side=tk.RIGHT)

        self.key_frame = tk.Frame(card, bg=Theme.surface)
        key_row = tk.Frame(self.key_frame, bg=Theme.surface)
        key_row.pack(fill=tk.X, padx=12, pady=(0, 4))
        glass_label(key_row, text="🔑 当前 Key:",
                    font=(Theme.font, 9), fg=Theme.text_dim,
                    bg=Theme.surface, width=10, anchor="w").pack(side=tk.LEFT)
        self.key_var = tk.StringVar(value="--")
        key_entry = glass_entry(key_row, var=self.key_var,
                                state="readonly", readonlybackground=Theme.surface_alt,
                                font=(Theme.font_mono, 9))
        key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        glass_button(key_row, "📋 复制",
                     Theme.surface_alt, lambda: self._copy_url(self.key_var),
                     font=(Theme.font, 8), padx=8, pady=1,
                     fg=Theme.text_dim,
                     activeforeground=Theme.text).pack(side=tk.LEFT)

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
                           ("ERROR", Theme.red), ("SUCCESS", Theme.blue),
                           ("SAVE", "#fb923c")]:
            self.log_text.tag_config(tag, foreground=color)

    # ── 设备下拉 ──

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
            glass_label(inner, text="服务器未运行", fg=Theme.text_dim,
                        bg=Theme.surface_alt).pack(pady=20)
        elif not self._online_devices:
            glass_label(inner, text="暂无设备连接", fg=Theme.text_dim,
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
        glass_label(left, text=f"🟢 {name}", font=(Theme.font, 9, "bold"),
                    fg=Theme.text, bg=Theme.surface, anchor="w").pack(fill=tk.X)

        secs = dev.get("connected_seconds", 0)
        h, m = secs // 3600, (secs % 3600) // 60
        conn = f"{h}h{m}m" if h > 0 else f"{m}m"
        info = f"    {dev.get('ip','?')}  ·  {conn}  ·  {dev.get('detect_count',0)} 次检测"
        glass_label(left, text=info, font=(Theme.font_mono, 8),
                    fg=Theme.text_dim, bg=Theme.surface, anchor="w").pack(fill=tk.X)

        tk.Button(row, text="断开", bg=Theme.red, fg="#fff",
                  font=(Theme.font, 8, "bold"), relief="flat", bd=0,
                  padx=8, pady=2, cursor="hand2",
                  command=lambda ip=dev.get("ip"): self._kick_device(ip))\
            .pack(side=tk.RIGHT)

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
