"""服务器管理面板 — 服务器控制、设备管理、模型切换、Tailscale"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

from graincounter.theme import Theme


class PanelControls:
    """服务器控制逻辑 mixin（由 ServerPanel 继承）"""

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
            self.root.after(4000, self._load_models)
        except Exception as e:
            self._log(f"启动失败: {e}", "ERROR")

    def _read_log(self):
        try:
            for line in self.server_process.stdout:
                line = line.rstrip()
                if not line or "/api/ping" in line or "/api/health" in line:
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
        self._device_count = count
        self.device_count_label.config(text=f"📡 {count} 台设备")

    def _start_device_loop(self):
        self._refresh_online_devices()
        self.root.after(3000, self._start_device_loop)

    def _kick_device(self, ip):
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
            try:
                url = f"http://localhost:{port}/api/models"
                with urllib.request.urlopen(url, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    models = data.get("models", [])
                    self.root.after(0, lambda: self._update_model_menu(models))
            except Exception:
                pass
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
            try:
                url = f"http://localhost:{port}/api/select-model"
                data = json.dumps({"model": model_name}).encode("utf-8")
                req = urllib.request.Request(url, data=data,
                                             headers={"Content-Type": "application/json"},
                                             method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    r = json.loads(resp.read().decode())
                    if r.get("ok"):
                        self.root.after(0, lambda: self.model_status_label.config(
                            text=f"已切换: {model_name}", fg=Theme.accent))
                        self.root.after(0, lambda: self._log(f"模型已切换: {model_name}", "SUCCESS"))
                    else:
                        self.root.after(0, lambda: self.model_status_label.config(
                            text="切换失败", fg=Theme.red))
            except Exception as e:
                self.root.after(0, lambda: self.model_status_label.config(
                    text="切换失败", fg=Theme.red))
                self.root.after(0, lambda: self._log(f"模型切换失败: {e}", "ERROR"))
        threading.Thread(target=run, daemon=True).start()

    # ── 认证切换 ──

    def _toggle_auth_on_server(self, enable):
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

    # ── 优质照片 ──

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
        self._valuable_count = count
        self.valuable_count_label.config(text=f"{count} 张")

    def _open_valuable_dir(self):
        vdir = os.path.join(self.project_dir, "Valuable photos")
        try:
            os.makedirs(vdir, exist_ok=True)
        except FileExistsError:
            pass
        try:
            subprocess.Popen(["explorer", vdir],
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            self._log(f"已打开: {vdir}", "SUCCESS")
        except Exception as e:
            self._log(f"打开失败: {e}", "ERROR")

    def _open_models_dir(self):
        mdir = os.path.join(self.project_dir, "models")
        if not os.path.isdir(mdir):
            os.makedirs(mdir, exist_ok=True)
        subprocess.Popen(["explorer", mdir],
                         creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
