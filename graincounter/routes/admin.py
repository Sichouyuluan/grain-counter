"""管理类 API — 配置、健康检查、认证、统计"""
import os
import json
import secrets
import logging

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse

from graincounter.config import get_config, set_config
from graincounter.guard import get_guard
from graincounter.stats import detection_stats
from graincounter.state import app_state
from graincounter.middleware import verify_api_key

logger = logging.getLogger("grain_web")
router = APIRouter(tags=["admin"])


@router.get("/api/config")
async def public_config():
    return {
        "max_upload_mb": get_config("max_upload_mb", 10),
        "auth_enabled": get_config("require_api_key", True),
        "version": "2.1.0",
    }


@router.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model": os.path.basename(get_config("model_path")),
        "auth": get_config("require_api_key", True),
    }


@router.get("/api/ping")
async def ping():
    return {"ok": True, "auth": get_config("require_api_key", True)}


@router.post("/api/toggle-auth")
async def toggle_auth(_: str = Depends(verify_api_key)):
    current = get_config("require_api_key", True)
    set_config("require_api_key", not current)
    state = "ON" if get_config("require_api_key") else "OFF"
    logger.info(f"API auth toggled to: {state}")
    return {"ok": True, "auth": get_config("require_api_key")}


@router.get("/api/key")
async def get_api_key(_: str = Depends(verify_api_key)):
    return {"key": app_state.api_key}


@router.post("/api/key/regenerate")
async def regenerate_api_key(_: str = Depends(verify_api_key)):
    from graincounter.config import get_project_root
    new_key = secrets.token_urlsafe(32)
    app_state.api_key = new_key
    key_file = os.path.join(get_project_root(), ".api_key")
    with open(key_file, "w") as f:
        f.write(new_key)
    logger.info(f"API Key regenerated: {new_key[:4]}...***PIN***")
    return {"ok": True, "key": new_key}


@router.get("/api/stats")
async def detection_statistics(_: str = Depends(verify_api_key)):
    stats = detection_stats.get_stats()
    guard = get_guard()
    if guard:
        stats["guard"] = guard.get_stats()
    return stats


@router.get("/api/attack-log")
async def attack_log(_: str = Depends(verify_api_key), limit: int = 50):
    """返回最近的攻击事件详情（IP、时间、路径、状态码）"""
    guard = get_guard()
    if guard:
        events = guard.get_recent_attacks(limit=limit)
        return {
            "events": events,
            "count": len(events),
            "protection_count": guard.get_stats()["protection_count"],
        }
    return {"events": [], "count": 0, "protection_count": 0}


@router.get("/api/scan-config")
async def get_scan_config(_: str = Depends(verify_api_key)):
    guard = get_guard()
    if not guard:
        return {"ok": False, "error": "ScanGuard not initialized"}
    return {"ok": True, "config": guard.get_config()}


@router.put("/api/scan-config")
async def update_scan_config(request: Request, _: str = Depends(verify_api_key)):
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    guard = get_guard()
    if not guard:
        raise HTTPException(status_code=503, detail="ScanGuard not initialized")
    if "path_threshold" in data:
        guard.path_threshold = int(data["path_threshold"])
    if "flood_threshold" in data:
        guard.flood_threshold = int(data["flood_threshold"])
    if "protect_minutes" in data:
        guard.protect_minutes = int(data["protect_minutes"])
    if "stop_after" in data:
        guard.stop_after = int(data["stop_after"])
    logger.info(f"ScanGuard config updated: {data}")
    return {"ok": True, "config": guard.get_config()}
