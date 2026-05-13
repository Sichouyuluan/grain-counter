"""
小麦籽粒检测 Web 服务器
- FastAPI + YOLOv8 ONNX 推理
- 手机/平板/桌面浏览器访问
- API Key 认证 + 限速 + 在线设备追踪 + 踢出
"""
import os
import io
import re
import time
import json
import base64
import subprocess
import secrets
import logging
from contextlib import asynccontextmanager
from datetime import datetime

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn

from graincounter.config import load_config, get_config, set_config
from graincounter.logger import setup_logger, PinHidingFilter
from graincounter.rate_limiter import RateLimiter
from graincounter.device_tracker import OnlineDeviceTracker
from graincounter.detector import GrainDetector, draw_results
from graincounter.valuable import ValuablePhotoSaver

# ============================================================
#  初始化 — 配置 / 日志 / 全局对象
# ============================================================
cfg = load_config()
logger = setup_logger("grain_web")

rate_limiter = RateLimiter(
    max_requests=get_config("rate_limit_per_minute", 60),
    window_seconds=60,
)
device_tracker = OnlineDeviceTracker(offline_threshold=30)
detector = None
api_key = None
valuable_saver = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector, api_key, valuable_saver
    detector = GrainDetector(
        model_path=get_config("model_path"),
        input_size=get_config("input_size", 640),
        score_threshold=get_config("score_threshold", 0.25),
        nms_threshold=get_config("nms_threshold", 0.5),
    )
    valuable_saver = ValuablePhotoSaver()
    api_key = _load_or_generate_api_key()
    logger.info(f"API Key: {api_key[:4]}...***PIN***")
    logger.info(f"服务启动: http://0.0.0.0:{get_config('port', 8000)}")
    yield
    logger.info("服务关闭")


def _load_or_generate_api_key() -> str:
    """从文件或环境变量加载 API Key，不存在则自动生成"""
    key = os.environ.get("GRAIN_API_KEY")
    if key:
        return key
    from graincounter.config import get_project_root
    key_file = os.path.join(get_project_root(), ".api_key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            key = f.read().strip()
    if not key:
        key = secrets.token_urlsafe(32)
        with open(key_file, "w") as f:
            f.write(key)
    return key


app = FastAPI(title="小麦籽粒检测", version="2.0.0", lifespan=lifespan)

# 中间件
if get_config("enable_response_compression", True):
    app.add_middleware(GZipMiddleware, minimum_size=get_config("response_compress_min_size", 1000))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
#  认证 & 中间件
# ============================================================
async def verify_api_key(authorization: str = Header(None)):
    if not get_config("require_api_key", True):
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="需要 API Key")
    token = authorization.replace("Bearer ", "").strip()
    if not secrets.compare_digest(token, api_key):
        raise HTTPException(status_code=403, detail="API Key 无效")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    path = request.url.path

    # 1. 踢出检查
    if path not in ("/api/online-devices", "/api/kick-device") and device_tracker.is_kicked(client_ip):
        return JSONResponse(status_code=403, content={"error": "你已被暂时移除，请5分钟后再试"})

    # 2. 限速
    if path not in ("/api/ping", "/api/online-devices", "/api/kick-device") and not rate_limiter.is_allowed(client_ip):
        return JSONResponse(status_code=429, content={"error": "请求过于频繁，请稍后再试"})

    # 3. 设备追踪（跳过 localhost）
    if client_ip not in ("127.0.0.1", "::1"):
        user_agent = request.headers.get("user-agent", "")
        device_tracker.update_activity(client_ip, user_agent)

    response = await call_next(request)

    # 检测请求计数
    if path == "/api/detect" and client_ip not in ("127.0.0.1", "::1"):
        device_tracker.increment_detect(client_ip)

    return response


# ============================================================
#  HTML 页面
# ============================================================
_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "index.html")
with open(_HTML_PATH, "r", encoding="utf-8") as _f:
    HTML_PAGE = _f.read()


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_PAGE


# ============================================================
#  API 路由
# ============================================================
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model": get_config("model_path"),
        "auth": get_config("require_api_key", True),
    }


@app.get("/api/ping")
async def ping():
    return {"ok": True, "auth": get_config("require_api_key", True)}


@app.post("/api/toggle-auth")
async def toggle_auth():
    current = get_config("require_api_key", True)
    set_config("require_api_key", not current)
    state = "ON" if get_config("require_api_key") else "OFF"
    logger.info(f"API auth toggled to: {state}")
    return {"ok": True, "auth": get_config("require_api_key")}


@app.get("/api/key")
async def get_api_key():
    return {"key": api_key}


@app.get("/api/models")
async def list_models():
    """列出 models/ 目录下所有 .onnx 模型文件"""
    from graincounter.config import get_project_root
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


@app.post("/api/select-model")
async def select_model(request: Request):
    """切换模型文件（热重载）"""
    global detector
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    model_name = data.get("model")
    if not model_name:
        raise HTTPException(status_code=400, detail="需要指定 model 参数")

    from graincounter.config import get_project_root
    models_dir = os.path.join(get_project_root(), "models")
    model_path = os.path.join(models_dir, model_name)
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"模型文件不存在: {model_name}")

    logger.info(f"切换模型: {model_name}")
    try:
        new_detector = GrainDetector(
            model_path=model_path,
            input_size=get_config("input_size", 640),
            score_threshold=get_config("score_threshold", 0.25),
            nms_threshold=get_config("nms_threshold", 0.5),
        )
        detector = new_detector
        set_config("model_path", model_path)
        logger.info(f"模型切换成功: {model_name}")
        return {"ok": True, "model": model_name}
    except Exception as e:
        logger.error(f"模型切换失败: {e}")
        raise HTTPException(status_code=500, detail=f"模型加载失败: {e}")


@app.get("/api/online-devices")
async def online_devices():
    devices = device_tracker.get_online_devices()
    return {"count": len(devices), "devices": devices}


@app.post("/api/kick-device")
async def kick_device(request: Request):
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    target_ip = data.get("ip")
    if not target_ip:
        raise HTTPException(status_code=400, detail="需要指定 ip 参数")
    device_tracker.kick(target_ip)
    return {"ok": True, "message": f"设备 {target_ip} 已被移除，5分钟后自动恢复"}


@app.post("/api/detect")
async def detect_image(
    file: UploadFile = File(...),
    conf: float = Query(default=None, ge=0.01, le=1.0, description="置信度阈值"),
    iou: float = Query(default=None, ge=0.01, le=1.0, description="IoU阈值"),
    _: str = Depends(verify_api_key),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    content = await file.read()
    max_bytes = get_config("max_upload_mb", 10) * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"文件过大，最大 {get_config('max_upload_mb')}MB")

    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="无法解析图片")

    t0 = time.perf_counter()
    results = detector.detect(img, conf=conf, iou=iou)
    elapsed = time.perf_counter() - t0

    # 优质训练照片筛选
    saved_valuable = valuable_saver.check_and_save(img, results, filename=file.filename or "image.jpg")

    vis = draw_results(img, results)
    _, buffer = cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 90])
    vis_b64 = base64.b64encode(buffer).decode("utf-8")

    return {
        "count": len(results),
        "elapsed_ms": round(elapsed * 1000, 1),
        "detections": results,
        "result_image": f"data:image/jpeg;base64,{vis_b64}",
        "image_size": {"width": img.shape[1], "height": img.shape[0]},
        "valuable_saved": saved_valuable,
        "valuable_count": valuable_saver.saved_count,
    }


@app.get("/api/valuable-stats")
async def valuable_stats():
    """获取优质训练照片统计信息"""
    vdir = get_config("valuable_dir", "Valuable photos")
    abs_dir = os.path.abspath(vdir)
    count = 0
    if os.path.exists(abs_dir):
        count = len([f for f in os.listdir(abs_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))])
    return {
        "saved_count": valuable_saver.saved_count,
        "total_count": count,
        "dir": vdir,
        "enable": get_config("valuable_enable", True),
    }


@app.post("/api/valuable-toggle")
async def valuable_toggle():
    """开启/关闭优质照片筛选"""
    current = get_config("valuable_enable", True)
    set_config("valuable_enable", not current)
    state = "开启" if get_config("valuable_enable") else "关闭"
    logger.info(f"优质照片筛选已{state}")
    return {"ok": True, "enable": get_config("valuable_enable")}


@app.post("/api/valuable-reset")
async def valuable_reset():
    """重置本次会话保存计数"""
    valuable_saver.reset_count()
    return {"ok": True, "saved_count": 0}


@app.post("/api/valuable-open-dir")
async def valuable_open_dir():
    """打开优质照片文件夹"""
    vdir = get_config("valuable_dir", "Valuable photos")
    abs_dir = os.path.abspath(vdir)
    if os.path.exists(abs_dir):
        subprocess.Popen(["explorer", abs_dir], creationflags=subprocess.CREATE_NO_WINDOW)
        return {"ok": True, "dir": abs_dir}
    return {"ok": False, "error": "目录不存在"}


@app.post("/api/save-image")
async def save_image(
    file: UploadFile = File(...),
    _: str = Depends(verify_api_key),
):
    """手动保存图片到优质照片目录（用于前端'识别不准'功能）"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="无法解析图片")
    vdir = get_config("valuable_dir", "Valuable photos")
    os.makedirs(vdir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    save_name = f"manual_{timestamp}{ext}"
    save_path = os.path.join(vdir, save_name)
    cv2.imwrite(save_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    valuable_saver._saved_count += 1
    logger.info(f"[MANUAL_SAVE] {save_name}")
    return {"ok": True, "path": save_name}



# ============================================================
#  启动
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="小麦籽粒检测 Web 服务器")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-auth", action="store_true", help="Disable API key auth")
    parser.add_argument("--api-key", default=None, help="Custom API key")
    parser.add_argument("--model", default=None, help="Model file name (in models/ dir)")
    args = parser.parse_args()

    if args.api_key:
        os.environ["GRAIN_API_KEY"] = args.api_key
    if args.no_auth:
        set_config("require_api_key", False)
        print("[WARNING] API key auth DISABLED - anyone can access!")
    if args.model:
        from graincounter.config import get_project_root
        model_path = os.path.join(get_project_root(), "models", args.model)
        if os.path.exists(model_path):
            set_config("model_path", model_path)
        else:
            print(f"[WARNING] Model not found: {model_path}, using default")

    if args.host:
        set_config("host", args.host)
    if args.port:
        set_config("port", args.port)

    host = get_config("host")
    port = get_config("port")
    print(f"Starting Grain Detector on http://{host}:{port}")
    print(f"Model: {get_config('model_path')}")
    auth = "ON" if get_config("require_api_key") else "OFF"
    print(f"Auth: {auth}")
    print(f"Response Compression: {'ON' if get_config('enable_response_compression') else 'OFF'}")
    uvicorn.run(app, host=host, port=port, timeout_keep_alive=120)
