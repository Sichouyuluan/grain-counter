"""限速器 — 按 IP 的滑动窗口限速 + 自动封禁（线程安全）"""
import time
import threading
from collections import defaultdict


class RateLimiter:
    """基于滑动时间窗口的 IP 限速器，支持自动封禁，所有公共方法线程安全"""

    def __init__(self, max_requests=60, window_seconds=60, ban_minutes=5):
        self.max_requests = max_requests
        self.window = window_seconds
        self.ban_minutes = ban_minutes
        self._lock = threading.Lock()
        self._requests = defaultdict(list)
        self._last_cleanup = 0.0
        self._ban_counts: dict[str, int] = {}
        self._banned: dict[str, float] = {}

    def _cleanup_old(self):
        """移除超过 2*window 秒无请求的 IP，防止内存泄漏（调用方已持锁）"""
        now = time.time()
        cutoff = now - 2 * self.window
        stale = [ip for ip, timestamps in self._requests.items()
                 if not timestamps or all(t <= cutoff for t in timestamps)]
        for ip in stale:
            del self._requests[ip]

    def is_allowed(self, client_ip: str) -> bool:
        with self._lock:
            now = time.time()
            if now - self._last_cleanup > 600:
                self._cleanup_old()
                self._last_cleanup = now
            cutoff = now - self.window
            self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]
            if len(self._requests[client_ip]) >= self.max_requests:
                return False
            self._requests[client_ip].append(now)
            return True

    def get_remaining(self, client_ip: str) -> int:
        with self._lock:
            now = time.time()
            cutoff = now - self.window
            self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]
            return max(0, self.max_requests - len(self._requests[client_ip]))

    def is_banned(self, client_ip: str) -> bool:
        """返回 True 表示该 IP 仍在封禁期内，同时自动清除过期封禁"""
        with self._lock:
            unban_ts = self._banned.get(client_ip)
            if unban_ts is None:
                return False
            if time.time() < unban_ts:
                return True
            del self._banned[client_ip]
            self._ban_counts.pop(client_ip, None)
            return False

    def record_rejection(self, client_ip: str):
        """记录一次 429 拒绝，累计 3 次后自动封禁"""
        with self._lock:
            self._ban_counts[client_ip] = self._ban_counts.get(client_ip, 0) + 1
            if self._ban_counts[client_ip] >= 3:
                self._banned[client_ip] = time.time() + self.ban_minutes * 60
                self._ban_counts.pop(client_ip, None)
