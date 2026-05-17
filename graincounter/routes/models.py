"""模型管理 API — 列出模型、切换模型"""
import os
import json
import asyncio
import logging

from fastapi import APIRouter, Request, HTTPException, Depends

from graincounter.config import get_config, set_config, get_project_root
from graincounter.detector import GrainDetector
from graincounter.middleware import verify_api_key
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
async def select_model(request: Request, _: str = Depends(verify_api_key)):
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    model_name = data.get("model")
    if not model_name:
        raise HTTPException(status_code=400, detail={"error": True, "message": "需要指定 model 参数", "code": 400})
    if os.path.basename(model_name) != model_name:
        raise HTTPException(status_code=400, detail={"error": True, "message": "无效的模型名称", "code": 400})
    if not model_name.lower().endswith(".onnx"):
        raise HTTPException(status_code=400, detail={"error": True, "message": "仅支持 .onnx 模型文件", "code": 400})

    models_dir = os.path.join(get_project_root(), "models")
    model_path = os.path.join(models_dir, model_name)
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail={"error": True, "message": f"模型文件不存在: {model_name}", "code": 404})

    logger.info(f"切换模型: {model_name}")

    # Check if model is already warm (was secondary, promote to main)
    warm_detector = app_state.get_warm_model(model_name)
    if warm_detector is not None:
        old_detector = app_state.detector
        old_name = app_state._main_model_name
        app_state.detector = warm_detector
        app_state._main_model_name = model_name
        app_state.remove_warm_model(model_name)
        if old_detector and old_name and old_name != model_name:
            app_state.set_warm_model(old_name, old_detector)
        logger.info(f"模型切换成功 (from warm): {model_name}")
        set_config("model_path", model_path, persist=True)
        return {"ok": True, "model": model_name, "from_warm": True}

    # Load new model (cold load)
    try:
        new_detector = await asyncio.to_thread(
            GrainDetector,
            model_path=model_path,
            input_size=get_config("input_size", 640),
            score_threshold=get_config("score_threshold", 0.25),
            nms_threshold=get_config("nms_threshold", 0.5),
        )
        old_detector = app_state.detector
        old_name = app_state._main_model_name
        app_state.detector = new_detector
        app_state._main_model_name = model_name
        # Store old main as warm secondary
        if old_detector and old_name and old_name != model_name:
            app_state.set_warm_model(old_name, old_detector)
        set_config("model_path", model_path, persist=True)
        logger.info(f"模型切换成功: {model_name}")
        return {"ok": True, "model": model_name, "from_warm": False}
    except Exception as e:
        logger.error(f"模型切换失败: {e}")
        raise HTTPException(status_code=500, detail={"error": True, "message": f"模型加载失败: {e}", "code": 500})


@router.post("/api/models/warm")
async def warm_model(request: Request, _: str = Depends(verify_api_key)):
    """Pre-warm a specific model (load into warm_models cache)"""
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    model_name = data.get("model")
    if not model_name:
        raise HTTPException(status_code=400, detail={"error": True, "message": "需要指定 model 参数"})
    if os.path.basename(model_name) != model_name:
        raise HTTPException(status_code=400, detail={"error": True, "message": "无效的模型名称"})
    if not model_name.lower().endswith(".onnx"):
        raise HTTPException(status_code=400, detail={"error": True, "message": "仅支持 .onnx 模型文件"})

    # Already warm?
    existing = app_state.get_warm_model(model_name)
    if existing is not None:
        app_state.touch_warm_model(model_name)
        logger.info(f"[WARM] Model already warm: {model_name}")
        return {"ok": True, "model": model_name, "status": "already_warm"}

    models_dir = os.path.join(get_project_root(), "models")
    model_path = os.path.join(models_dir, model_name)
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail={"error": True, "message": f"模型文件不存在: {model_name}"})

    try:
        detector = await asyncio.to_thread(
            GrainDetector,
            model_path=model_path,
            input_size=get_config("input_size", 640),
            score_threshold=get_config("score_threshold", 0.25),
            nms_threshold=get_config("nms_threshold", 0.5),
        )
        app_state.set_warm_model(model_name, detector)
        logger.info(f"[WARM] Model warmed: {model_name}")
        return {"ok": True, "model": model_name, "status": "loaded"}
    except Exception as e:
        logger.error(f"[WARM] Failed to warm model {model_name}: {e}")
        raise HTTPException(status_code=500, detail={"error": True, "message": f"模型加载失败: {e}"})


@router.get("/api/models/warm-status")
async def warm_status():
    """Return warm status for all known models"""
    models = app_state.get_warm_status()
    return {
        "ok": True,
        "main_model": app_state._main_model_name,
        "models": models,
        "warm_count": len([n for n, s in models.items() if s.get("warm")]),
    }
