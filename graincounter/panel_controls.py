"""服务器管理面板 — 服务器控制、设备管理、模型切换、Tailscale"""
import json
import os
import re as _re
import subprocess
import sys
import threading
import time
import urllib.request
import yaml

from graincounter.theme import Theme


class PanelControls:
    """服务器控制逻辑 mixin（由 ServerPanel 继承）"""

    # ── API Key 辅助 ──
    def _get_api_key(self) -> str | None:
        """获取当前有效的 API Key"""
        custom = self.custom_key_var.get().strip()
        if custom:
            return custom
        key_file = os.path.join(self.project_dir, ".api_key")
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                return f.read().strip()
        return os.environ.get("GRAIN_API_KEY")

    def _api_request(self, url, method="GET", data=None, timeout=3):
        """发送带 API Key 的 HTTP 请求，返回 (status, body_dict_or_None)"""
        headers = {"Content-Type": "application/json"}
        key = self._get_api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception:
            return 0, None

    # ── 轮询退避 ──
    _poll_failures: dict[str, int] = {}
    _poll_base_intervals: dict[str, int] = {
        "device_loop": 3000,
        "valuable_stats": 5000,
        "runtime_stats": 5000,
        "warm_status": 5000,
    }

    def _poll_backoff(self, key: str) -> int:
        """计算退避间隔：连续失败 N 次 → min(2^N * base, 60000) ms，成功时重置"""
        base = self._poll_base_intervals.get(key, 5000)
        failures = self._poll_failures.get(key, 0)
        if failures <= 1:
            return base
        return min(base * (2 ** (failures - 1)), 60000)

    def _poll_record(self, key: str, success: bool):
        if success:
            self._poll_failures[key] = 0
        else:
            self._poll_failures[key] = self._poll_failures.get(key, 0) + 1

    # ── 服务器控制 ──

    def _start_server(self):
        if self.server_running:
            return
        if not os.path.exists(self.web_server_path):
            self._log("找不到 web_server.py", "ERROR")
            return
        port = self.port_var.get().strip()
        auth = self.auth_var.get()
        cmd = [sys.executable, self.web_server_path, "--port", port]
        if not auth:
            cmd.append("--no-auth")
        custom_key = self.custom_key_var.get().strip()
        if custom_key:
            cmd.extend(["--api-key", custom_key])
        # 启动前指定模型
        model_val = self.model_var.get()
        if model_val and model_val not in ("加载中...", "无可用模型"):
            model_name = model_val.split(" (")[0] if " (" in model_val else model_val
            cmd.extend(["--model", model_name])
        # 脱敏：隐藏命令行中的 API Key
        masked_cmd = []
        skip_next = False
        for arg in cmd:
            if skip_next:
                masked_cmd.append("***")
                skip_next = False
            elif arg == "--api-key":
                masked_cmd.append(arg)
                skip_next = True
            else:
                masked_cmd.append(arg)
        self._log(f"启动: {' '.join(masked_cmd)}", "INFO")
        try:
            si = None
            if sys.platform == "win32":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # 设置 PYTHONIOENCODING 避免 UTF-8 日志在 GBK 终端下乱码
            server_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=self.project_dir, startupinfo=si, env=server_env)
            self.server_running = True
            self._update_ui_state(True)
            self._log(f"PID={self.server_process.pid}", "SUCCESS")
            self.log_thread = threading.Thread(target=self._read_log, daemon=True)
            self.log_thread.start()
            self.root.after(3000, self._start_device_loop)
            self.root.after(5000, self._poll_valuable_stats)
            self.root.after(4000, self._load_models)
            self.root.after(4000, self._poll_runtime_stats)
            self.root.after(5000, self._poll_warm_status)
        except Exception as e:
            self._log(f"启动失败: {e}", "ERROR")

    def _read_log(self):
        import re as _re
        try:
            for line in self.server_process.stdout:
                line = line.rstrip()
                # 剥离 ANSI 转义码，修复日志乱码
                line = _re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
                line = _re.sub(r'\x1b\]([0-9]+);.*?\x07', '', line)
                if not line or any(x in line for x in (
                    "/api/ping", "/api/health", "/api/stats",
                    "/api/online-devices", "/api/valuable-stats", "/api/models",
                )):
                    continue
                if "[VALUABLE]" in line or "[MANUAL_SAVE]" in line:
                    lvl = "SAVE"
                elif any(x in line.lower() for x in ("warn", "warning")):
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

    # ── 设备管理 ──

    def _refresh_online_devices(self):
        if not self.server_running:
            self._online_devices = []
            self._update_device_count(0)
            return
        port = self.port_var.get().strip()
        def fetch():
            ok = False
            code, data = self._api_request(f"http://localhost:{port}/api/online-devices")
            if code == 200 and data:
                self._online_devices = data.get("devices", [])
                self.root.after(0, lambda: self._update_device_count(data.get("count", 0)))
                ok = True
            else:
                self._online_devices = []
                self.root.after(0, lambda: self._update_device_count(0))
            self._poll_record("device_loop", ok)
        threading.Thread(target=fetch, daemon=True).start()

    def _update_device_count(self, count):
        self._device_count = count
        self.device_count_label.config(text=f"📡 {count} 台设备")

    def _start_device_loop(self):
        self._refresh_online_devices()
        self.root.after(self._poll_backoff("device_loop"), self._start_device_loop)

    def _kick_device(self, ip):
        if not self.server_running:
            return
        port = self.port_var.get().strip()
        def run():
            code, r = self._api_request(
                f"http://localhost:{port}/api/kick-device",
                method="POST", data={"ip": ip},
            )
            if code == 200 and r and r.get("ok"):
                self.root.after(0, lambda: self._log(f"已踢出: {ip}", "WARNING"))
                self.root.after(0, self._refresh_online_devices)
            else:
                self.root.after(0, lambda: self._log(f"踢出失败", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    # ── 模型管理 ──

    def scan_models_dir(self):
        """启动前扫描 models/ 目录，填充下拉框"""
        models_dir = os.path.join(self.project_dir, "models")
        if not os.path.isdir(models_dir):
            return
        files = sorted([f for f in os.listdir(models_dir) if f.endswith(".onnx")])
        if not files:
            return
        labels = []
        default = None
        config_model = os.path.basename(getattr(self, '_config_model_path', ''))
        for f in files:
            full = os.path.join(models_dir, f)
            size_mb = round(os.path.getsize(full) / 1024 / 1024, 1)
            labels.append(f"{f} ({size_mb}MB)")
            if f == config_model or not default:
                default = f"{f} ({size_mb}MB)"
        self.model_menu["values"] = labels
        if default:
            self.model_var.set(default)
            self.model_status_label.config(text="就绪", fg=Theme.text_dim)

    def _load_models(self):
        if not self.server_running:
            return
        port = self.port_var.get().strip()
        def fetch():
            code, data = self._api_request(f"http://localhost:{port}/api/models")
            if code == 200 and data:
                models = data.get("models", [])
                self.root.after(0, lambda m=models: self._update_model_menu(m))
        threading.Thread(target=fetch, daemon=True).start()

    def _update_model_menu(self, models):
        if not models:
            self.model_menu["values"] = ["无可用模型"]
            self.model_var.set("无可用模型")
            return
        labels = [f"{m['name']} ({m['size_mb']}MB)" for m in models]
        self.model_menu["values"] = labels
        for m in models:
            if m.get("active"):
                self.model_var.set(f"{m['name']} ({m['size_mb']}MB)")
                self.model_status_label.config(text=f"当前: {m['name']}", fg=Theme.accent)
                break

    def _switch_model(self):
        if not self.server_running:
            self._show_toast("服务器未运行")
            return
        model_name = self.model_var.get()
        if not model_name or model_name in ("加载中...", "无可用模型"):
            return
        # 从 "model.onnx (XX.XMB)" 中提取文件名
        if " (" in model_name:
            model_name = model_name.split(" (")[0]
        self.model_status_label.config(text="切换中...", fg=Theme.orange)
        port = self.port_var.get().strip()
        def run():
            code, r = self._api_request(
                f"http://localhost:{port}/api/select-model",
                method="POST", data={"model": model_name}, timeout=30,
            )
            if code == 200 and r and r.get("ok"):
                self.root.after(0, lambda: self.model_status_label.config(
                    text=f"已切换: {model_name}", fg=Theme.accent))
                self.root.after(0, lambda: self._log(f"模型已切换: {model_name}", "SUCCESS"))
            else:
                self.root.after(0, lambda: self.model_status_label.config(
                    text="切换失败", fg=Theme.red))
        threading.Thread(target=run, daemon=True).start()

    # ── 认证切换 ──

    def _toggle_auth_on_server(self, enable):
        port = self.port_var.get().strip()
        def run():
            code, r = self._api_request(
                f"http://localhost:{port}/api/toggle-auth", method="POST",
            )
            if code == 200 and r and r.get("ok"):
                s = "ON" if r.get("auth") else "OFF"
                self.root.after(0, lambda: self._log(f"认证已切换: {s}（热切换）", "SUCCESS"))
            else:
                self.root.after(0, lambda: self._log(f"认证切换失败", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _fetch_api_key(self):
        port = self.port_var.get().strip()
        def run():
            time.sleep(1.0)
            code, h = self._api_request(f"http://localhost:{port}/api/health")
            if code == 200 and h and not h.get("auth", True):
                self.root.after(0, lambda: self._safe_pack_forget(self.key_frame))
                return
            code2, data = self._api_request(f"http://localhost:{port}/api/key")
            if code2 == 200 and data:
                self.root.after(0, lambda d=data: self.key_var.set(d.get("key", "--")))
            else:
                self.root.after(0, lambda: self.key_var.set("获取失败"))
        threading.Thread(target=run, daemon=True).start()

    # ── Tailscale ──

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

    def _set_ts(self, connected, ip, status_text):
        self.tailscale_online = connected
        self.tailscale_ip = ip
        port = self.port_var.get().strip()
        if connected and ip:
            self.ts_status_dot.config(fg=Theme.accent)
            self.ts_url_var.set(f"http://{ip}:{port}")
            if hasattr(self, 'ts_entry'):
                self.ts_entry.config(fg=Theme.accent)
            self._log(f"Tailscale: {ip}", "SUCCESS")
        else:
            self.ts_status_dot.config(fg=Theme.red)
            self.ts_url_var.set(f"-- {status_text} --")
            if hasattr(self, 'ts_entry'):
                self.ts_entry.config(fg="#facc15")

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

    # ── 攻击详情 ──
    def _show_attack_log(self):
        """显示攻击日志弹窗"""
        if not self.server_running:
            self._show_toast("服务器未运行")
            return
        port = self.port_var.get().strip()

        def fetch():
            code, data = self._api_request(
                f"http://localhost:{port}/api/attack-log?limit=30",
            )
            if code == 200 and data and data.get("events"):
                lines = [f"保护触发: {data['protection_count']}次 | 最近攻击:"]
                for e in data["events"]:
                    lines.append(f"  {e['time']} | {e['ip']} | {e['status']} | {e['path']}")
                self.root.after(0, lambda: self._show_attack_popup("\n".join(lines)))
            else:
                self.root.after(0, lambda: self._show_toast("暂无攻击记录"))
        threading.Thread(target=fetch, daemon=True).start()

    def _show_attack_popup(self, text):
        import tkinter as tk
        popup = tk.Toplevel(self.root)
        popup.title("攻击详情")
        popup.geometry("700x400")
        popup.configure(bg=Theme.surface)
        popup.transient(self.root)
        popup.grab_set()

        frame = tk.Frame(popup, bg=Theme.surface)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        scroll = tk.Scrollbar(frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        txt = tk.Text(frame, font=("Consolas", 9), bg=Theme.surface_alt,
                      fg="#e0e0e0", insertbackground="#fff",
                      yscrollcommand=scroll.set, wrap=tk.NONE)
        txt.insert("1.0", text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)
        scroll.config(command=txt.yview)

        btn = tk.Button(popup, text="关闭", command=popup.destroy,
                        bg=Theme.surface_alt, fg="#ccc", relief=tk.FLAT,
                        font=(Theme.font, 10), padx=20, pady=4, cursor="hand2")
        btn.pack(pady=(0, 8))

    # ── 优质照片 ──

    def _poll_valuable_stats(self):
        if not self.server_running:
            self.root.after(self._poll_backoff("valuable_stats"), self._poll_valuable_stats)
            return
        port = self.port_var.get().strip()
        def fetch():
            ok = False
            code, data = self._api_request(f"http://localhost:{port}/api/valuable-stats")
            if code == 200 and data:
                self.root.after(0, lambda d=data: self._update_valuable_count(d.get("total_count", 0)))
                ok = True
            self._poll_record("valuable_stats", ok)
            self.root.after(self._poll_backoff("valuable_stats"), self._poll_valuable_stats)
        threading.Thread(target=fetch, daemon=True).start()

    def _update_valuable_count(self, count):
        self._valuable_count = count
        self.valuable_count_label.config(text=f"{count} 张")

    def _poll_runtime_stats(self):
        """拉取 runtime stats 更新面板状态（带退避 + API Key）"""
        if not self.server_running:
            self.root.after(self._poll_backoff("runtime_stats"), self._poll_runtime_stats)
            return
        port = self.port_var.get().strip()
        def fetch():
            ok = False
            code, data = self._api_request(f"http://localhost:{port}/api/stats")
            if code == 200 and data:
                gs = data.get("guard", {})
                self.root.after(0, lambda d=data, g=gs: self._update_runtime_labels(d, g))
                ok = True
            self._poll_record("runtime_stats", ok)
            self.root.after(self._poll_backoff("runtime_stats"), self._poll_runtime_stats)
        threading.Thread(target=fetch, daemon=True).start()

    def _update_runtime_labels(self, stats, guard_stats):
        # 扫描攻击
        pc = guard_stats.get("protection_count", 0)
        self.guard_label.config(text=f"触发{pc}次", fg=Theme.red if pc > 0 else Theme.orange)
        # 检测次数
        dt = stats.get("today", 0)
        self.detect_label.config(text=f"检测{dt}次")
        # 错误
        err = stats.get("errors", 0)
        self.error_label.config(text=f"错误{err}", fg=Theme.red if err > 0 else Theme.text_dim)

    def _open_valuable_dir(self):
        vdir = os.path.join(self.project_dir, "Valuable photos")
        try:
            os.makedirs(vdir, exist_ok=True)
        except FileExistsError:
            pass
        try:
            if sys.platform == "win32":
                cmd = ["explorer", vdir]
            elif sys.platform == "darwin":
                cmd = ["open", vdir]
            else:
                cmd = ["xdg-open", vdir]
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            self._log(f"已打开: {vdir}", "SUCCESS")
        except Exception as e:
            self._log(f"打开失败: {e}", "ERROR")

    def _open_models_dir(self):
        mdir = os.path.join(self.project_dir, "models")
        if not os.path.isdir(mdir):
            os.makedirs(mdir, exist_ok=True)
        if sys.platform == "win32":
            cmd = ["explorer", mdir]
        elif sys.platform == "darwin":
            cmd = ["open", mdir]
        else:
            cmd = ["xdg-open", mdir]
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

    # ── API Key 刷新 ──

    def _regenerate_api_key(self):
        """重新生成 API Key（不依赖服务器运行状态）"""
        import secrets
        new_key = secrets.token_urlsafe(32)
        key_file = os.path.join(self.project_dir, ".api_key")
        with open(key_file, "w") as f:
            f.write(new_key)
        self.custom_key_var.set(new_key)
        self.key_var.set(new_key)
        self._prev_key = new_key
        self._log("API Key 已重新生成", "SUCCESS")
        self._show_toast("✅ 新 Key 已生成")
        # 如果服务器在运行，同步到服务器
        if self.server_running:
            port = self.port_var.get().strip()
            def run():
                self._api_request(
                    f"http://localhost:{port}/api/key/regenerate",
                    method="POST",
                )
            threading.Thread(target=run, daemon=True).start()

    # ── ScanGuard 防护配置 ──

    def _on_scan_config_changed(self):
        if not self.server_running:
            return
        if hasattr(self, '_scan_config_after_id') and self._scan_config_after_id:
            self.root.after_cancel(self._scan_config_after_id)
        self._scan_config_after_id = self.root.after(800, self._send_scan_config)

    def _send_scan_config(self):
        port = self.port_var.get().strip()
        try:
            seconds = int(self.protect_seconds_var.get())
            config = {
                "path_threshold": int(self.path_threshold_var.get()),
                "flood_threshold": int(self.flood_threshold_var.get()),
                "protect_minutes": max(1, seconds // 60),
                "stop_after": int(self.stop_after_var.get()),
            }
        except ValueError:
            return
        def run():
            code, data = self._api_request(
                f"http://localhost:{port}/api/scan-config",
                method="PUT", data=config,
            )
            if code == 200:
                self.root.after(0, lambda: self._log("防护配置已更新", "INFO"))
            else:
                self.root.after(0, lambda: self._log("防护配置更新失败", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _reset_scan_config(self):
        """恢复 ScanGuard 默认配置"""
        self.path_threshold_var.set("15")
        self.flood_threshold_var.set("50")
        self.protect_seconds_var.set("180")
        self.stop_after_var.set("5")
        if self.server_running:
            port = self.port_var.get().strip()
            defaults = {"path_threshold": 15, "flood_threshold": 50, "protect_minutes": 3, "stop_after": 5}
            def run():
                self._api_request(
                    f"http://localhost:{port}/api/scan-config",
                    method="PUT", data=defaults,
                )
            threading.Thread(target=run, daemon=True).start()
        self._log("防护配置已恢复默认", "INFO")

    # ── Cloudflared ──

    def _load_cf_tunnel_url(self):
        """自动获取隧道 URL，优先级：
        1. cloudflared config.yml 的 hostname（自动，任何电脑都能用）
        2. cloudflared 日志里的 quick tunnel URL（trycloudflare.com）
        3. config.local.yaml / config.yaml（手动配置）
        """
        if self._cf_tunnel_url:
            return
        try:
            # 1. 从 cloudflared 配置读取命名隧道 hostname
            cf_config = os.path.join(os.path.expanduser("~"), ".cloudflared", "config.yml")
            if os.path.exists(cf_config):
                with open(cf_config, "r", encoding="utf-8") as f:
                    cfc = yaml.safe_load(f) or {}
                ingress = cfc.get("ingress", [])
                for rule in ingress:
                    hostname = rule.get("hostname", "")
                    if hostname:
                        self._cf_tunnel_url = f"https://{hostname}"
                        return
        except Exception:
            pass
        try:
            # 2. 从项目配置文件读取
            for fname in ("config.local.yaml", "config.yaml"):
                config_path = os.path.join(self.project_dir, fname)
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = yaml.safe_load(f) or {}
                    url = cfg.get("tunnel_url", "")
                    if url:
                        self._cf_tunnel_url = url
                        return
        except Exception:
            pass

    def _detect_cloudflared(self):
        # 先检查进程状态
        online = (hasattr(self, 'cloudflared_process') and self.cloudflared_process is not None
                  and self.cloudflared_process.poll() is None)
        if online:
            # 进程在运行，但连接可能尚未建立
            self.cf_status_dot.config(fg="#facc15")  # 黄色 = 启动中
            self.cf_url_var.set("连接中...")
        else:
            self._set_cf(False, "未运行")
        # 后台检查 tunnel list + 加载配置URL
        def run():
            try:
                self._load_cf_tunnel_url()
                r = subprocess.run(["cloudflared", "tunnel", "list"],
                                   capture_output=True, text=True, timeout=10,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                if r.returncode == 0 and "grain-counter" in r.stdout:
                    connected = "connected" in r.stdout.lower() or "running" in r.stdout.lower()
                    self.root.after(0, lambda: self._set_cf(connected, "已连接" if connected else "已断开"))
                else:
                    self.root.after(0, lambda: self._set_cf(False, "未安装"))
            except FileNotFoundError:
                self.root.after(0, lambda: self._set_cf(False, "未安装"))
            except Exception:
                self.root.after(0, lambda: self._set_cf(False, "检测失败"))
        threading.Thread(target=run, daemon=True).start()

    def _set_cf(self, online, status_text):
        color = Theme.accent if online else Theme.red
        self.cf_status_dot.config(fg=color)
        if hasattr(self, 'cf_address_dot') and self.cf_address_dot:
            self.cf_address_dot.config(fg=color)
        entry_color = Theme.accent if online else "#facc15"
        # 优先显示 tunnel_url，没有则显示状态文本
        display = self._cf_tunnel_url if online and self._cf_tunnel_url else f"-- {status_text} --"
        self.cf_url_var.set(display)
        if hasattr(self, 'cf_entry'):
            self.cf_entry.config(fg=entry_color)
        if online:
            if self._cf_tunnel_url:
                self._log(f"Cloudflared: {self._cf_tunnel_url}", "SUCCESS")
            else:
                self._log("Cloudflared tunnel connected", "SUCCESS")

    def _start_cloudflared(self):
        def run():
            self.root.after(0, lambda: self._log("启动 Cloudflared 隧道...", "INFO"))
            try:
                proc = subprocess.Popen(
                    ["cloudflared", "tunnel", "run", "grain-counter"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                self.cloudflared_process = proc
                self.root.after(0, lambda: self._log(f"Cloudflared PID={proc.pid}", "SUCCESS"))
                self._detect_cloudflared()
                threading.Thread(target=self._read_cloudflared_logs, daemon=True).start()
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Cloudflared 启动异常: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    def _read_cloudflared_logs(self):
        url_pattern = _re.compile(r'https://[a-zA-Z0-9.-]+\.(?:trycloudflare|cfargotunnel)\.com\S*')
        try:
            for line in self.cloudflared_process.stdout:
                line = line.rstrip()
                if not line:
                    continue
                clean = _re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
                clean = _re.sub(r'\x1b\]([0-9]+);.*?\x07', '', clean)
                # 尝试从日志中提取 quick tunnel URL
                url_match = url_pattern.search(clean)
                if url_match and not self._cf_tunnel_url:
                    self._cf_tunnel_url = url_match.group(0)
                # 检测连接成功 → 加载 URL + 更新状态
                if "Registered tunnel connection" in clean:
                    self.root.after(0, lambda: self._load_cf_tunnel_url())
                    self.root.after(0, lambda: self._set_cf(True, "已连接"))
                # 内容分级
                upper = clean.upper()
                if " ERR " in upper or " ERROR " in upper or "FAILED" in upper:
                    lvl = "ERROR"
                elif " WRN " in upper or " WARNING " in upper:
                    lvl = "WARNING"
                else:
                    lvl = "CLOUDFLARE"
                self.root.after(0, lambda c=clean, l=lvl: self._log(c, l))
        except Exception:
            pass
        finally:
            self.root.after(0, lambda: self._log("Cloudflared 隧道已断开", "WARNING"))

    def _stop_cloudflared(self):
        def run():
            self.root.after(0, lambda: self._log("停止 Cloudflared 隧道...", "WARNING"))
            try:
                if hasattr(self, 'cloudflared_process') and self.cloudflared_process:
                    pid = self.cloudflared_process.pid
                    # Windows: taskkill /F /T 强制杀死进程树（含子进程）
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            capture_output=True, timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                        # 补刀：杀死所有残留 cloudflared.exe 进程
                        subprocess.run(
                            ["taskkill", "/F", "/IM", "cloudflared.exe"],
                            capture_output=True, timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    else:
                        self.cloudflared_process.terminate()
                        try:
                            self.cloudflared_process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            self.cloudflared_process.kill()
                    self.cloudflared_process = None
                else:
                    # 无进程句柄时直接杀所有 cloudflared
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/F", "/IM", "cloudflared.exe"],
                            capture_output=True, timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                # 直接设置状态为已断开，不依赖 cloudflared tunnel list 的延迟反馈
                self.root.after(0, lambda: self._set_cf(False, "已停止"))
                self.root.after(0, lambda: self._log("Cloudflared 已停止", "SUCCESS"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Cloudflared 停止异常: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    # ── 预热状态轮询 ──

    def _poll_warm_status(self):
        if not self.server_running:
            self.root.after(self._poll_backoff("warm_status"), self._poll_warm_status)
            return
        port = self.port_var.get().strip()
        def fetch():
            ok = False
            code, data = self._api_request(f"http://localhost:{port}/api/models/warm-status")
            if code == 200 and data:
                models = data.get("models", {})
                warm_names = []
                for n, s in models.items():
                    if s.get("warm") and not s.get("is_main"):
                        warm_names.append(n)
                display = ", ".join(warm_names) if warm_names else "无"
                self.root.after(0, lambda d=display: self.warm_status_label.config(text=d))
                ok = True
            self._poll_record("warm_status", ok)
            self.root.after(self._poll_backoff("warm_status"), self._poll_warm_status)
        threading.Thread(target=fetch, daemon=True).start()
