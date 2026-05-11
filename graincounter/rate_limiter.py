"""限速器 — 按 IP 的滑动窗口限速"""
import time
from collections import defaultdict


class RateLimiter:
    """基于滑动时间窗口的 IP 限速器"""

    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]
        if len(self._requests[client_ip]) >= self.max_requests:
            return False
        self._requests[client_ip].append(now)
        return True

    def get_remaining(self, client_ip: str) -> int:
        now = time.time()
        cutoff = now - self.window
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]
        return max(0, self.max_requests - len(self._requests[client_ip]))
