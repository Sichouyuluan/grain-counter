"""日志系统 — 双输出日志 + API Key 脱敏"""
import os
import sys
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime


class PinHidingFilter(logging.Filter):
    """在日志中隐藏 API Key / Token 片段"""

    _PATTERNS = [
        re.compile(r'(key=)[A-Za-z0-9_\-]{8,}', re.IGNORECASE),
        re.compile(r'(Bearer\s+)[A-Za-z0-9_\-]{8,}', re.IGNORECASE),
        re.compile(r'(--api-key\s+)[A-Za-z0-9_\-]{8,}', re.IGNORECASE),
        re.compile(r'(api[_-]?key[=:]\s*)[A-Za-z0-9_\-]{8,}', re.IGNORECASE),
        re.compile(r'(token[=:]\s*)[A-Za-z0-9_\-]{8,}', re.IGNORECASE),
    ]

    _TRIGGER_WORDS = ("key", "bearer", "authorization", "token", "auth")

    def filter(self, record):
        msg = record.getMessage()
        msg_lower = msg.lower()
        if any(w in msg_lower for w in self._TRIGGER_WORDS):
            for pat in self._PATTERNS:
                msg = pat.sub(r"\1***PIN***", msg)
            record.msg = msg
            record.args = ()
        return True


class _SafeFormatMessageMixin:
    """混合入 uvicorn AccessFormatter，截获空 args 崩溃"""
    def formatMessage(self, record):
        if not record.args:
            record.args = ('-', '-', '-', '-', '-')
        try:
            return super().formatMessage(record)
        except Exception:
            return str(getattr(record, 'msg', ''))


def setup_logger(name="grain_web", log_dir=None, level=logging.INFO) -> logging.Logger:
    """配置并返回 logger 实例"""
    # Monkey-patch uvicorn 的 AccessFormatter 防止空 args 崩溃
    try:
        from uvicorn.logging import AccessFormatter
        if not issubclass(AccessFormatter, _SafeFormatMessageMixin):
            class SafeAccessFormatter(_SafeFormatMessageMixin, AccessFormatter):
                pass
            import uvicorn.logging
            uvicorn.logging.AccessFormatter = SafeAccessFormatter
    except Exception:
        pass

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # stdout handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(level)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # 文件 handler
    if log_dir is None:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(
        log_dir, f"grain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    fh = RotatingFileHandler(log_file, encoding="utf-8", maxBytes=10*1024*1024, backupCount=5)
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # 给 grain_web logger 自身添加 API Key 脱敏过滤器
    if not any(isinstance(f, PinHidingFilter) for f in logger.filters):
        logger.addFilter(PinHidingFilter())

    # 给 uvicorn access log 添加脱敏过滤器
    for _name in ("uvicorn.access", "uvicorn"):
        _l = logging.getLogger(_name)
        if not any(isinstance(f, PinHidingFilter) for f in _l.filters):
            _l.addFilter(PinHidingFilter())

    return logger


# 全局默认 logger（延迟初始化）
_logger = None


def get_logger():
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger
