"""模型管理 API — 列出模型、切换模型"""
import os
import json
import asyncio
import logging

from fastapi import APIRouter, Request, HTTPException

from graincounter.config import get_config, set_config, get_project_root
from graincounter.detector import GrainDetector
from graincounter.state import app_state

logger = logging.getLogger("grain_web")
router = APIRouter(tags=["models"])


@router.get("/api/models")
async def list_models():
    models_dir = os.path.join(get_project_root(), "models")
    if not os.path.isdir(models_dir):
        return {"models": [], "current": os.path.basename(get_config("model_path"))}
    files = [f for f in os.listdir(models_dir) if f.endswith(".onnx")]
    files.sort()
    current = os.path.basename(get_config("model_path"))
    result = []
    for f in files:
        full = os.path.join(models_dir, f)
        size_mb = round(os.path.getsize(full) / 1024 / 1024, 1)
        result.append({"name": f, "size_mb": size_mb, "active": f == current})
    return {"models": result, "current": current}


@router.post("/api/select-model")
async def select_model(request: Request):
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    model_name = data.get("model")
    if not model_name:
        raise HTTPException(status_code=400, detail={"error": True, "message": "需要指定 model 参数", "code": 400})

    models_dir = os.path.join(get_project_root(), "models")
    model_path = os.path.join(models_dir, model_name)
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail={"error": True, "message": f"模型文件不存在: {model_name}", "code": 404})

    logger.info(f"切换模型: {model_name}")
    try:
        new_detector = await asyncio.to_thread(
            GrainDetector,
            model_path=model_path,
            input_size=get_config("input_size", 640),
            score_threshold=get_config("score_threshold", 0.25),
            nms_threshold=get_config("nms_threshold", 0.5),
        )
        app_state.detector = new_detector  # 线程安全写入
        set_config("model_path", model_path, persist=True)
        logger.info(f"模型切换成功: {model_name}")
        return {"ok": True, "model": model_name}
    except Exception as e:
        logger.error(f"模型切换失败: {e}")
        raise HTTPException(status_code=500, detail={"error": True, "message": f"模型加载失败: {e}", "code": 500})
