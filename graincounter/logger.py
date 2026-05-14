"""日志系统 — 双输出日志 + API Key 脱敏"""
import os
import sys
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime


class PinHidingFilter(logging.Filter):
    """在日志中隐藏 API Key 片段"""

    _PATTERNS = [
        re.compile(r'(key=)[A-Za-z0-9_-]{8,}', re.IGNORECASE),
        re.compile(r'(Bearer\s+)[A-Za-z0-9_-]{8,}', re.IGNORECASE),
    ]

    def filter(self, record):
        msg = record.getMessage()
        if "key" in msg.lower():
            for pat in self._PATTERNS:
                msg = pat.sub(r"\1***PIN***", msg)
            record.msg = msg
            record.args = ()
        return True


class UvicornSafeFilter(logging.Filter):
    """修复 uvicorn access logger 的格式化崩溃"""

    def filter(self, record):
        if not record.args:
            msg = getattr(record, 'msg', '')
            if isinstance(msg, str) and any(x in msg for x in ('%(client_addr)', '%(request_line)', '%(status_code)')):
                # uvicorn access log 占位符，提供 5 个安全默认值
                record.args = ('?', '?', 0, '-', 0)
            elif '%s' in msg:
                record.args = ()
        return True


def setup_logger(name="grain_web", log_dir=None, level=logging.INFO) -> logging.Logger:
    """配置并返回 logger 实例"""
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

    # 给 uvicorn access log 添加脱敏 + 安全过滤器
    for _name in ("uvicorn.access", "uvicorn"):
        _l = logging.getLogger(_name)
        if not any(isinstance(f, PinHidingFilter) for f in _l.filters):
            _l.addFilter(PinHidingFilter())
        if not any(isinstance(f, UvicornSafeFilter) for f in _l.filters):
            _l.addFilter(UvicornSafeFilter())

    return logger


# 全局默认 logger（延迟初始化）
_logger = None


def get_logger():
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger
