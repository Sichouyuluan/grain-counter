"""
小麦籽粒检测 Web 服务器
- 手机/平板/桌面浏览器访问
- 上传图片 → ONNX 推理 → 返回结果图+计数
- 安全：API Key 认证 + 限速 + 在线设备追踪 + 踢出
"""

import os
import sys
import io
import re
import time
import json
import base64
import secrets
import logging
import threading
from collections import defaultdict
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
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
    "rate_limit_per_minute": 60,
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


for _name in ("uvicorn.access", "uvicorn"):
    logging.getLogger(_name).addFilter(_PinHidingFilter())

# ============================================================
#  限速器
# ============================================================
class RateLimiter:
    def __init__(self, max_requests=60, window_seconds=60):
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
#  User-Agent 解析
# ============================================================
def parse_user_agent(ua_string: str) -> dict:
    """解析 User-Agent，返回 {brand, os, browser, raw}"""
    result = {"brand": "", "os": "", "browser": "", "raw": ua_string or ""}
    if not ua_string:
        return result
    ua = ua_string

    # --- 操作系统 ---
    if "Windows NT 10.0" in ua:
        result["os"] = "Windows 10"
    elif "Windows NT 11.0" in ua:
        result["os"] = "Windows 11"
    elif "Windows NT 6.1" in ua:
        result["os"] = "Windows 7"
    elif "Windows" in ua:
        result["os"] = "Windows"
    elif "Mac OS X" in ua:
        m = re.search(r'Mac OS X (\d+[._]\d+[._]?\d*)', ua)
        result["os"] = f"macOS {m.group(1).replace('_', '.')}" if m else "macOS"
    elif "Linux; Android" in ua:
        m = re.search(r'Android (\d+)', ua)
        result["os"] = f"Android {m.group(1)}" if m else "Android"
    elif "Linux" in ua:
        result["os"] = "Linux"
    elif "iPhone OS" in ua or "iPhone" in ua:
        m = re.search(r'iPhone OS (\d+_\d+)', ua)
        result["os"] = f"iOS {m.group(1).replace('_', '.')}" if m else "iOS"
    elif "iPad" in ua:
        m = re.search(r'OS (\d+_\d+)', ua)
        result["os"] = f"iPadOS {m.group(1).replace('_', '.')}" if m else "iPadOS"

    # --- 品牌 ---
    brand_detected = False
    brand_map = [
        (["XiaoMi", "MiuiBrowser", "MIUI", "Redmi", "Xiaomi"], "小米"),
        (["HUAWEI", "Huawei"], "华为"),
        (["Samsung", "SM-"], "三星"),
        (["OPPO", "ColorOS"], "OPPO"),
        (["vivo", "Vivo"], "vivo"),
        (["OnePlus"], "一加"),
        (["Realme"], "Realme"),
        (["Honor", "HONOR"], "荣耀"),
        (["iPhone", "iPad"], "Apple"),
    ]
    for keywords, brand in brand_map:
        if any(kw in ua for kw in keywords):
            result["brand"] = brand
            brand_detected = True
            break

    if not brand_detected:
        m = re.search(r';\s*(\w+)\s+\w+\)', ua)
        if m:
            known = {"Pixel": "Google", "Nokia": "Nokia", "LG": "LG", "Sony": "索尼", "Motorola": "摩托罗拉"}
            if m.group(1) in known:
                result["brand"] = known[m.group(1)]

    # --- 浏览器 ---
    if "Edg/" in ua:
        result["browser"] = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        result["browser"] = "Opera"
    elif "Quark/" in ua:
        m = re.search(r'Quark/(\d+)', ua)
        result["browser"] = f"夸克 {m.group(1)}" if m else "夸克"
    elif "UCBrowser" in ua or "UCWEB" in ua:
        result["browser"] = "UC浏览器"
    elif "MiuiBrowser/" in ua:
        m = re.search(r'MiuiBrowser/(\d+[\.\d]*)', ua)
        result["browser"] = f"小米浏览器 {m.group(1)}" if m else "小米浏览器"
    elif "Chrome/" in ua and "Safari/" in ua:
        m = re.search(r'Chrome/(\d+)', ua)
        result["browser"] = f"Chrome {m.group(1)}" if m else "Chrome"
    elif "Safari/" in ua and "Chrome/" not in ua:
        m = re.search(r'Version/(\d+[\.\d]*)', ua)
        result["browser"] = f"Safari {m.group(1)}" if m else "Safari"
    elif "Firefox/" in ua:
        m = re.search(r'Firefox/(\d+)', ua)
        result["browser"] = f"Firefox {m.group(1)}" if m else "Firefox"

    return result


def get_device_display_name(ua_info: dict) -> str:
    """生成设备显示名称：手机优先品牌，电脑用系统"""
    parts = []
    if ua_info["brand"]:
        parts.append(ua_info["brand"])
    elif ua_info["os"]:
        parts.append(ua_info["os"])
    if ua_info["browser"]:
        parts.append(ua_info["browser"])
    return " · ".join(parts) if parts else "未知设备"


# ============================================================
#  在线设备追踪器
# ============================================================
class OnlineDeviceTracker:
    def __init__(self, offline_threshold=30):
        self._lock = threading.RLock()  # 可重入锁，避免 get_online_devices 内调 is_kicked 死锁
        self._devices = {}
        self._kicked = {}
        self.offline_threshold = offline_threshold
        self.kick_duration = 300

    def update_activity(self, client_ip: str, user_agent: str = ""):
        now = time.time()
        with self._lock:
            if client_ip in self._devices:
                self._devices[client_ip]["last_seen"] = now
            else:
                ua_info = parse_user_agent(user_agent)
                self._devices[client_ip] = {
                    "first_seen": now,
                    "last_seen": now,
                    "detect_count": 0,
                    "ua_info": ua_info,
                    "display_name": get_device_display_name(ua_info),
                }
                logger.info(f"新设备连接: {client_ip} ({self._devices[client_ip]['display_name']})")

    def increment_detect(self, client_ip: str):
        with self._lock:
            if client_ip in self._devices:
                self._devices[client_ip]["detect_count"] += 1

    def is_kicked(self, client_ip: str) -> bool:
        with self._lock:
            if client_ip in self._kicked:
                if time.time() < self._kicked[client_ip]:
                    return True
                else:
                    del self._kicked[client_ip]
            return False

    def kick(self, client_ip: str):
        with self._lock:
            self._kicked[client_ip] = time.time() + self.kick_duration
            logger.info(f"设备被踢出: {client_ip}，5分钟后自动恢复")

    def get_online_devices(self) -> list:
        now = time.time()
        online = []
        with self._lock:
            for ip, info in self._devices.items():
                if now - info["last_seen"] <= self.offline_threshold:
                    online.append({
                        "ip": ip,
                        "display_name": info["display_name"],
                        "os": info["ua_info"]["os"],
                        "browser": info["ua_info"]["browser"],
                        "brand": info["ua_info"]["brand"],
                        "connected_seconds": round(now - info["first_seen"]),
                        "detect_count": info["detect_count"],
                        "last_seen_seconds_ago": round(now - info["last_seen"]),
                        "kicked": self.is_kicked(ip),
                    })
        online.sort(key=lambda x: x["last_seen_seconds_ago"])
        return online

    def get_online_count(self) -> int:
        now = time.time()
        count = 0
        with self._lock:
            for ip, info in self._devices.items():
                if now - info["last_seen"] <= self.offline_threshold:
                    count += 1
        return count


device_tracker = OnlineDeviceTracker(offline_threshold=30)


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
            img_bgr, conf=score, iou=nms, imgsz=self.input_size, verbose=False,
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
    for r in results:
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
        key_file = os.path.join(os.path.dirname(__file__), ".api_key")
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                api_key = f.read().strip()
        if not api_key:
            api_key = secrets.token_urlsafe(32)
            with open(key_file, "w") as f:
                f.write(api_key)
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
#  认证 & 限速 & 设备追踪中间件
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
    path = request.url.path

    # 1. 踢出检查
    if path not in ("/api/online-devices", "/api/kick-device") and device_tracker.is_kicked(client_ip):
        return JSONResponse(status_code=403, content={"error": "你已被暂时移除，请5分钟后再试"})

    # 2. 限速（ping 和管理接口豁免）
    if path not in ("/api/ping", "/api/online-devices", "/api/kick-device") and not rate_limiter.is_allowed(client_ip):
        return JSONResponse(status_code=429, content={"error": "请求过于频繁，请稍后再试"})

    # 3. 更新设备活跃状态（跳过 localhost，避免面板轮询被记录为"幽灵设备"）
    if client_ip not in ("127.0.0.1", "::1"):
        user_agent = request.headers.get("user-agent", "")
        device_tracker.update_activity(client_ip, user_agent)

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
    return {"ok": True, "auth": CONFIG.get("require_api_key", True)}



@app.post("/api/toggle-auth")
async def toggle_auth():
    CONFIG["require_api_key"] = not CONFIG.get("require_api_key", True)
    state = "ON" if CONFIG["require_api_key"] else "OFF"
    logger.info(f"API auth toggled to: {state}")
    return {"ok": True, "auth": CONFIG["require_api_key"]}


@app.post("/api/toggle-hide-pin")
async def toggle_hide_pin():
    return {"ok": True}


@app.get("/api/key")
async def get_api_key():
    return {"key": api_key}


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
    parser.add_argument("--api-key", default=None, help="Custom API key (overrides auto-generated)")
    args = parser.parse_args()
    if args.api_key:
        os.environ["GRAIN_API_KEY"] = args.api_key
    if args.no_auth:
        CONFIG["require_api_key"] = False
        print("[WARNING] API key auth DISABLED - anyone can access!")
    print(f"Starting Grain Detector on http://{args.host}:{args.port}")
    model = CONFIG["model_path"]
    print(f"Model: {model}")
    auth = "ON" if CONFIG["require_api_key"] else "OFF"
    print(f"Auth: {auth}")
    uvicorn.run(app, host=args.host, port=args.port)
