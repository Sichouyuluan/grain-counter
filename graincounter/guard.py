"""扫描攻击检测 — 全局异常统计 + 自动保护 + 停服"""
import time
import threading
from collections import deque
from graincounter.logger import get_logger

logger = get_logger()


class ScanGuard:
    """
    扫描攻击检测器（双重检测机制）
    - 10秒滑动窗口内，统计所有IP的 404/403/429 响应
    - 路径维度：不同路径数 > path_threshold(15) → 触发（目录扫描）
    - 总量维度：异常响应总数 > flood_threshold(50) → 触发（洪水攻击）
    - 保护模式持续 3 分钟，期间所有请求返回 503
    - 一次启动中出现 5 次保护触发 → 自动停止服务器
    """

    def __init__(self, window_seconds=10, path_threshold=15,
                 flood_threshold=50, protect_minutes=3, stop_after=5,
                 stop_callback=None):
        self._lock = threading.Lock()
        self._window_seconds = window_seconds
        self._path_threshold = path_threshold
        self._flood_threshold = flood_threshold
        self._protect_seconds = protect_minutes * 60
        self._stop_after = stop_after
        self._stop_callback = stop_callback

        # 滑动窗口: deque of (timestamp, ip, status, path)
        self._window: deque = deque()
        # 保护状态
        self._protected_until = 0.0
        self._protection_count = 0
        # 最近一次触发原因
        self._trigger_reason = ""

    def check_and_record(self, client_ip: str, status: int, path: str):
        """每次请求后调用，双重检测记录并检查是否需要保护"""
        now = time.time()
        with self._lock:
            # 清理过期记录
            cutoff = now - self._window_seconds
            while self._window and self._window[0][0] < cutoff:
                self._window.popleft()

            # 记录本请求
            self._window.append((now, client_ip, status, path))

            # 筛选窗口内异常响应 (404, 403, 429)
            abnormal_entries = [r for r in self._window if r[2] in (404, 403, 429)]
            total_abnormal = len(abnormal_entries)

            # 维度1: 不同路径数（目录扫描检测）
            unique_paths = len(set(r[3] for r in abnormal_entries))

            # 维度2: 异常响应总数（洪水攻击检测）
            triggered = False
            if unique_paths > self._path_threshold:
                self._trigger_reason = f"path_scan({unique_paths}>{self._path_threshold})"
                triggered = True
            elif total_abnormal > self._flood_threshold:
                self._trigger_reason = f"flood({total_abnormal}>{self._flood_threshold})"
                triggered = True

            if triggered:
                self._trigger_protection(now)

    def _trigger_protection(self, now: float):
        self._protected_until = now + self._protect_seconds
        self._protection_count += 1
        logger.warning(
            f"[GUARD] 检测到扫描攻击({self._trigger_reason})！已触发第{self._protection_count}次保护，持续{self._protect_seconds//60}分钟"
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
            abnormal_entries = [r for r in self._window if r[2] in (404, 403, 429)]
            return {
                "protection_count": self._protection_count,
                "is_protected": protected,
                "remaining_seconds": max(0, int(self._protected_until - now)),
                "window_size": len(self._window),
                "total_abnormal": len(abnormal_entries),
                "unique_paths": len(set(r[3] for r in abnormal_entries)),
                "trigger_reason": self._trigger_reason,
            }

    # ── Dynamic config setters/getters ──

    @property
    def path_threshold(self):
        with self._lock:
            return self._path_threshold

    @path_threshold.setter
    def path_threshold(self, value):
        with self._lock:
            self._path_threshold = int(value)

    @property
    def flood_threshold(self):
        with self._lock:
            return self._flood_threshold

    @flood_threshold.setter
    def flood_threshold(self, value):
        with self._lock:
            self._flood_threshold = int(value)

    @property
    def protect_minutes(self):
        with self._lock:
            return self._protect_seconds // 60

    @protect_minutes.setter
    def protect_minutes(self, value):
        with self._lock:
            self._protect_seconds = int(value) * 60

    @property
    def stop_after(self):
        with self._lock:
            return self._stop_after

    @stop_after.setter
    def stop_after(self, value):
        with self._lock:
            self._stop_after = int(value)

    def get_config(self) -> dict:
        with self._lock:
            return {
                "path_threshold": self._path_threshold,
                "flood_threshold": self._flood_threshold,
                "protect_minutes": self._protect_seconds // 60,
                "stop_after": self._stop_after,
                "protection_count": self._protection_count,
                "is_protected": time.time() < self._protected_until,
                "remaining_seconds": max(0, int(self._protected_until - time.time())),
            }

    def get_recent_attacks(self, limit=50) -> list[dict]:
        """返回最近异常事件的详细信息（用于面板攻击详情展示）"""
        with self._lock:
            abnormal = [
                {"time": time.strftime("%H:%M:%S", time.localtime(r[0])),
                 "timestamp": r[0], "ip": r[1], "status": r[2], "path": r[3]}
                for r in self._window if r[2] in (404, 403, 429)
            ]
            return sorted(abnormal, key=lambda x: x["timestamp"], reverse=True)[:limit]


# 全局实例（lifespan 中初始化）
_guard: ScanGuard | None = None


def get_guard() -> ScanGuard | None:
    return _guard


def set_guard(g: ScanGuard):
    global _guard
    _guard = g
