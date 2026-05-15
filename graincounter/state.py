"""集中应用状态 — 替代散落各处的模块级全局变量，线程安全访问"""
import threading
import asyncio

# 在状态模块中延迟导入，避免循环依赖
# 具体类型在 web_server lifespan 中注入


class AppState:
    """服务器运行时全局状态容器，所有可变状态集中管理"""

    def __init__(self):
        self._lock = threading.Lock()
        self._detector = None
        self._api_key = None
        self._valuable_saver = None
        self._rate_limiter = None
        self._detect_rate_limiter = None
        self._device_tracker = None

    # ── detector（线程安全读写，防止 select_model 竞态）──

    @property
    def detector(self):
        with self._lock:
            return self._detector

    @detector.setter
    def detector(self, value):
        with self._lock:
            self._detector = value

    # ── 其余属性（启动时赋值一次，运行时只读，无需锁）──

    @property
    def api_key(self):
        return self._api_key

    @api_key.setter
    def api_key(self, value):
        self._api_key = value

    @property
    def valuable_saver(self):
        return self._valuable_saver

    @valuable_saver.setter
    def valuable_saver(self, value):
        self._valuable_saver = value

    @property
    def rate_limiter(self):
        return self._rate_limiter

    @rate_limiter.setter
    def rate_limiter(self, value):
        self._rate_limiter = value

    @property
    def detect_rate_limiter(self):
        return self._detect_rate_limiter

    @detect_rate_limiter.setter
    def detect_rate_limiter(self, value):
        self._detect_rate_limiter = value

    @property
    def device_tracker(self):
        return self._device_tracker

    @device_tracker.setter
    def device_tracker(self, value):
        self._device_tracker = value


# 模块级单例 — 整个应用共享
app_state = AppState()
