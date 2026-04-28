"""
小麦籽粒检测 Web 服务器
- 手机/平板/桌面浏览器访问
- 上传图片 → ONNX 推理 → 返回结果图+计数
- 安全：API Key 认证 + 限速 + HTTPS 建议
"""

import os
import sys
import io
import time
import base64
import secrets
import logging
from collections import defaultdict
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ============================================================
#  配置
# ============================================================
CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "model_path": "models/grain_v8m_v10.onnx",
    "input_size": 640,
    "score_threshold": 0.25,
    "nms_threshold": 0.5,
    "max_upload_mb": 10,
    "rate_limit_per_minute": 30,
    "require_api_key": True,
}

# ============================================================
#  日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("web_server.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("grain_web")


class _PinHidingFilter(logging.Filter):
    """Hide API key fragments in uvicorn access logs."""
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


# Attach filter to uvicorn access logger
for _name in ("uvicorn.access", "uvicorn"):
    logging.getLogger(_name).addFilter(_PinHidingFilter())

# ============================================================
#  限速器
# ============================================================
class RateLimiter:
    def __init__(self, max_requests=30, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > cutoff]
        if len(self.requests[client_ip]) >= self.max_requests:
            return False
        self.requests[client_ip].append(now)
        return True

rate_limiter = RateLimiter(max_requests=CONFIG["rate_limit_per_minute"], window_seconds=60)

# ============================================================
#  检测器
# ============================================================
class GrainDetector:
    def __init__(self, model_path, input_size=640, score_threshold=0.25, nms_threshold=0.5):
        self.input_size = input_size
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        abs_path = os.path.abspath(model_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"模型文件不存在: {abs_path}")
        logger.info(f"加载模型: {abs_path}")
        t0 = time.perf_counter()
        from ultralytics import YOLO
        self.model = YOLO(abs_path)
        logger.info(f"模型加载完成, 耗时 {time.perf_counter()-t0:.2f}s")

    def detect(self, img_bgr, conf=None, iou=None):
        h, w = img_bgr.shape[:2]
        score = conf if conf is not None else self.score_threshold
        nms = iou if iou is not None else self.nms_threshold
        logger.info(f"检测开始: img={w}x{h} conf={score} iou={nms}")
        t0 = time.perf_counter()
        results = self.model.predict(
            img_bgr,
            conf=score,
            iou=nms,
            imgsz=self.input_size,
            verbose=False,
        )
        boxes = results[0].boxes
        elapsed = time.perf_counter() - t0
        if len(boxes) == 0:
            logger.info(f"检测完成: 0 个, 耗时 {elapsed:.3f}s")
            return []
        xyxy = boxes.xyxy.cpu().numpy().astype(int)
        confs = boxes.conf.cpu().numpy()
        dets = [
            {"bbox": [int(x1), int(y1), int(x2), int(y2)], "confidence": float(c)}
            for x1, y1, x2, y2, c in zip(xyxy[:, 0], xyxy[:, 1], xyxy[:, 2], xyxy[:, 3], confs)
        ]
        logger.info(f"检测完成: {len(dets)} 个, 耗时 {elapsed:.3f}s")
        return dets


def draw_results(img_bgr, results):
    vis = img_bgr.copy()
    for i, r in enumerate(results):
        x1, y1, x2, y2 = r["bbox"]
        conf = r["confidence"]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(vis, (x1, y1 - th - 8), (x1 + tw + 4, y1), (0, 255, 0), -1)
        cv2.putText(vis, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    count = len(results)
    label = f"Grain: {count}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 2)
    cv2.rectangle(vis, (5, 5), (15 + tw, 15 + th), (0, 0, 0), -1)
    cv2.putText(vis, label, (10, 10 + th), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
    return vis


# ============================================================
#  全局状态
# ============================================================
detector = None
api_key = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector, api_key
    detector = GrainDetector(
        model_path=CONFIG["model_path"],
        input_size=CONFIG["input_size"],
        score_threshold=CONFIG["score_threshold"],
        nms_threshold=CONFIG["nms_threshold"],
    )
    api_key = os.environ.get("GRAIN_API_KEY")
    if not api_key:
        api_key = secrets.token_urlsafe(32)
    logger.info(f"API Key: {api_key[:4]}...***PIN***")
    logger.info(f"服务启动: http://0.0.0.0:{CONFIG['port']}")
    yield
    logger.info("服务关闭")


app = FastAPI(title="小麦籽粒检测", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
#  认证 & 限速
# ============================================================
async def verify_api_key(authorization: str = Header(None)):
    if not CONFIG.get("require_api_key", True):
        return
    if not api_key:
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="需要 API Key")
    token = authorization.replace("Bearer ", "").strip()
    if not secrets.compare_digest(token, api_key):
        raise HTTPException(status_code=403, detail="API Key 无效")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    if not rate_limiter.is_allowed(client_ip):
        return JSONResponse(status_code=429, content={"error": "请求过于频繁，请稍后再试"})
    return await call_next(request)


# ============================================================
#  路由
# ============================================================
_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "index.html")
with open(_HTML_PATH, "r", encoding="utf-8") as _f:
    HTML_PAGE = _f.read()


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_PAGE


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": CONFIG["model_path"], "auth": CONFIG.get("require_api_key", True)}


@app.get("/api/ping")
async def ping():
    """Lightweight heartbeat endpoint for connection status detection."""
    return {"ok": True, "auth": CONFIG.get("require_api_key", True)}


@app.get("/api/key")
async def get_api_key():
    return {"key": api_key}


from fastapi import Query

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
    max_bytes = CONFIG["max_upload_mb"] * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"文件过大，最大 {CONFIG['max_upload_mb']}MB")
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="无法解析图片")
    t0 = time.perf_counter()
    results = detector.detect(img, conf=conf, iou=iou)
    elapsed = time.perf_counter() - t0
    vis = draw_results(img, results)
    _, buffer = cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 90])
    vis_b64 = base64.b64encode(buffer).decode("utf-8")
    return {
        "count": len(results),
        "elapsed_ms": round(elapsed * 1000, 1),
        "detections": results,
        "result_image": f"data:image/jpeg;base64,{vis_b64}",
        "image_size": {"width": img.shape[1], "height": img.shape[0]},
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-auth", action="store_true", help="Disable API key auth")
    args = parser.parse_args()
    if args.no_auth:
        CONFIG["require_api_key"] = False
        print("[WARNING] API key auth DISABLED - anyone can access!")
    print(f"Starting Grain Detector on http://{args.host}:{args.port}")
    model = CONFIG["model_path"]
    print(f"Model: {model}")
    auth = "ON" if CONFIG["require_api_key"] else "OFF"
    print(f"Auth: {auth}")
    uvicorn.run(app, host=args.host, port=args.port)
