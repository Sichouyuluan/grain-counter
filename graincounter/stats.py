"""检测统计 — 内存计数器"""
import threading
import time
from datetime import datetime


class DetectionStats:
    """线程安全的内存统计计数器"""

    def __init__(self):
        self._lock = threading.Lock()
        self._total = 0
        self._today = 0
        self._today_date = datetime.now().strftime("%Y%m%d")
        self._errors = 0
        self._start_time = time.time()
        self._by_ip: dict[str, int] = {}

    def record_success(self, client_ip: str = ""):
        with self._lock:
            self._total += 1
            self._check_today()
            self._today += 1
            if client_ip:
                self._by_ip[client_ip] = self._by_ip.get(client_ip, 0) + 1

    def record_error(self):
        with self._lock:
            self._errors += 1

    def _check_today(self):
        today = datetime.now().strftime("%Y%m%d")
        if today != self._today_date:
            self._today_date = today
            self._today = 0

    def get_stats(self) -> dict:
        with self._lock:
            self._check_today()
            return {
                "total": self._total,
                "today": self._today,
                "errors": self._errors,
                "uptime_seconds": round(time.time() - self._start_time),
                "top_ips": sorted(self._by_ip.items(), key=lambda x: x[1], reverse=True)[:10],
            }


# 全局实例
detection_stats = DetectionStats()
