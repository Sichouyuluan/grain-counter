"""设备管理 API — 在线设备列表、踢出设备"""
import json

from fastapi import APIRouter, Request, Depends, HTTPException

from graincounter.state import app_state
from graincounter.middleware import verify_api_key

router = APIRouter(tags=["devices"])


@router.get("/api/online-devices")
async def online_devices(_: str = Depends(verify_api_key)):
    devices = app_state.device_tracker.get_online_devices()
    return {"count": len(devices), "devices": devices}


@router.post("/api/kick-device")
async def kick_device(request: Request, _: str = Depends(verify_api_key)):
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    target_ip = data.get("ip")
    if not target_ip:
        raise HTTPException(status_code=400, detail={"error": True, "message": "需要指定 ip 参数", "code": 400})
    app_state.device_tracker.kick(target_ip)
    return {"ok": True, "message": f"设备 {target_ip} 已被移除，5分钟后自动恢复"}
