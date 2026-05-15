"""扫描攻击检测 — 全局异常统计 + 自动保护 + 停服"""
import time
import threading
from collections import deque
from graincounter.logger import get_logger

logger = get_logger()


class ScanGuard:
    """
    扫描攻击检测器
    - 5秒滑动窗口内，所有IP的 404+403+429 总数 > 20 → 触发保护
    - 保护模式持续 5 分钟，期间所有请求返回 503
    - 一次启动中出现 3 次保护触发 → 自动停止服务器
    """

    def __init__(self, window_seconds=5, threshold=20,
                 protect_minutes=5, stop_after=3,
                 stop_callback=None):
        self._lock = threading.Lock()
        self._window_seconds = window_seconds
        self._threshold = threshold
        self._protect_seconds = protect_minutes * 60
        self._stop_after = stop_after
        self._stop_callback = stop_callback

        # 滑动窗口: deque of (timestamp, ip, status, path)
        self._window: deque = deque()
        # 保护状态
        self._protected_until = 0.0
        self._protection_count = 0

    def check_and_record(self, client_ip: str, status: int, path: str):
        """每次请求后调用，记录并检查是否需要保护"""
        now = time.time()
        with self._lock:
            # 清理过期记录
            cutoff = now - self._window_seconds
            while self._window and self._window[0][0] < cutoff:
                self._window.popleft()

            # 记录本请求
            self._window.append((now, client_ip, status, path))

            # 统计窗口内异常响应
            abnormal = sum(1 for r in self._window if r[2] in (404, 403, 429))

            if abnormal > self._threshold:
                self._trigger_protection(now)

    def _trigger_protection(self, now: float):
        self._protected_until = now + self._protect_seconds
        self._protection_count += 1
        logger.warning(
            f"[GUARD] 检测到扫描攻击！已触发第{self._protection_count}次保护，持续{self._protect_seconds//60}分钟"
        )
        if self._protection_count >= self._stop_after and self._stop_callback:
            logger.error(f"[GUARD] 已触发{self._protection_count}次保护，自动停止服务器")
            self._stop_callback()

    def is_protected(self) -> bool:
        """当前是否处于保护模式"""
        with self._lock:
            return time.time() < self._protected_until

    def get_remaining_protect_seconds(self) -> int:
        with self._lock:
            return max(0, int(self._protected_until - time.time()))

    def get_stats(self) -> dict:
        with self._lock:
            now = time.time()
            protected = now < self._protected_until
            return {
                "protection_count": self._protection_count,
                "is_protected": protected,
                "remaining_seconds": max(0, int(self._protected_until - now)),
                "window_size": len(self._window),
            }


# 全局实例（lifespan 中初始化）
_guard: ScanGuard | None = None


def get_guard() -> ScanGuard | None:
    return _guard


def set_guard(g: ScanGuard):
    global _guard
    _guard = g
