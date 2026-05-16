"""页面 & 优质照片 API — HTML 首页、优质照片管理"""
import os
import subprocess
import sys
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from graincounter.config import get_config, set_config
from graincounter.state import app_state
from graincounter.middleware import verify_api_key

logger = logging.getLogger("grain_web")
router = APIRouter(tags=["pages"])

# HTML 模板懒加载
_html_cache = None


def _get_html() -> str:
    global _html_cache
    if _html_cache is None:
        html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates", "index.html")
        if not os.path.exists(html_path):
            raise FileNotFoundError(f"模板文件不存在: {html_path}")
        with open(html_path, "r", encoding="utf-8") as f:
            _html_cache = f.read()
    return _html_cache


@router.get("/", response_class=HTMLResponse)
async def index():
    try:
        return _get_html()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/api/valuable-stats")
async def valuable_stats():
    vdir = get_config("valuable_dir", "Valuable photos")
    abs_dir = os.path.abspath(vdir)
    count = 0
    if os.path.exists(abs_dir) and os.path.isdir(abs_dir):
        count = len([f for f in os.listdir(abs_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))])
    return {
        "saved_count": app_state.valuable_saver.saved_count,
        "total_count": count,
        "dir": vdir,
        "enable": get_config("valuable_enable", True),
    }


@router.post("/api/valuable-toggle")
async def valuable_toggle(_: str = Depends(verify_api_key)):
    current = get_config("valuable_enable", True)
    set_config("valuable_enable", not current)
    state = "开启" if get_config("valuable_enable") else "关闭"
    logger.info(f"优质照片筛选已{state}")
    return {"ok": True, "enable": get_config("valuable_enable")}


@router.post("/api/valuable-reset")
async def valuable_reset(_: str = Depends(verify_api_key)):
    app_state.valuable_saver.reset_count()
    return {"ok": True, "saved_count": 0}


@router.post("/api/valuable-open-dir")
async def valuable_open_dir(_: str = Depends(verify_api_key)):
    vdir = get_config("valuable_dir", "Valuable photos")
    abs_dir = os.path.abspath(vdir)
    if os.path.exists(abs_dir):
        subprocess.Popen(["explorer", abs_dir], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return {"ok": True, "dir": abs_dir}
    return {"ok": False, "error": "目录不存在"}
