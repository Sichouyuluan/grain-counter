"""
小麦籽粒检测 Web 服务器
- FastAPI + YOLOv8 ONNX 推理
- 路由拆分到 graincounter/routes/
- 状态管理集中到 graincounter/state.py
"""
import os
import secrets
import logging
import asyncio
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from graincounter.config import load_config, get_config, set_config, get_project_root
from graincounter.logger import setup_logger
from graincounter.rate_limiter import RateLimiter
from graincounter.device_tracker import OnlineDeviceTracker
from graincounter.detector import GrainDetector
from graincounter.valuable import ValuablePhotoSaver
from graincounter.guard import ScanGuard, set_guard
from graincounter.state import app_state
from graincounter.middleware import rate_limit_middleware

# ── 初始化 ──
cfg = load_config()
logger = setup_logger("grain_web")

# 注入全局状态（模块级单例，供所有路由模块访问）
app_state.rate_limiter = RateLimiter(
    max_requests=get_config("rate_limit_per_minute", 60),
    window_seconds=60,
)
app_state.detect_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)
app_state.device_tracker = OnlineDeviceTracker(offline_threshold=30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：加载模型 → 预热 GPU → 初始化扫描防护"""
    detector = GrainDetector(
        model_path=get_config("model_path"),
        input_size=get_config("input_size", 640),
        score_threshold=get_config("score_threshold", 0.25),
        nms_threshold=get_config("nms_threshold", 0.5),
    )
    app_state.detector = detector

    logger.info("GPU 预热中...")
    warm_img = np.zeros((640, 640, 3), dtype=np.uint8)
    detector.detect(warm_img)
    logger.info("GPU 预热完成")

    app_state.valuable_saver = ValuablePhotoSaver()

    def _stop_uvicorn():
        logger.error("[GUARD] 多次扫描攻击，停止服务...")
        import signal
        os.kill(os.getpid(), signal.SIGTERM)

    set_guard(ScanGuard(stop_callback=_stop_uvicorn))
    app_state.api_key = _load_or_generate_api_key()
    logger.info(f"API Key: {app_state.api_key[:4]}...***PIN***")
    logger.info(f"服务启动: http://0.0.0.0:{get_config('port', 8000)}")
    yield
    logger.info("服务关闭")


def _load_or_generate_api_key() -> str:
    key = os.environ.get("GRAIN_API_KEY")
    if key:
        return key
    key_file = os.path.join(get_project_root(), ".api_key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            key = f.read().strip()
    if not key:
        key = secrets.token_urlsafe(32)
        with open(key_file, "w") as f:
            f.write(key)
    return key


# ── FastAPI 应用 ──
app = FastAPI(title="小麦籽粒检测", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(rate_limit_middleware)

# 注册所有路由模块
from graincounter.routes.admin import router as admin_router
from graincounter.routes.models import router as models_router
from graincounter.routes.devices import router as devices_router
from graincounter.routes.detect import router as detect_router
from graincounter.routes.pages import router as pages_router

app.include_router(admin_router)
app.include_router(models_router)
app.include_router(devices_router)
app.include_router(detect_router)
app.include_router(pages_router)


# ── 启动 ──
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
    uvicorn.run(app, host=host, port=port, timeout_keep_alive=120, timeout_graceful_shutdown=30)
