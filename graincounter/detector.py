"""YOLOv8 检测器 — ONNX 推理 + 结果绘制"""
import os
import time
import cv2
import numpy as np
from graincounter.logger import get_logger

logger = get_logger()


class GrainDetector:
    """YOLOv8 ONNX 推理封装"""

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
        """执行检测，返回 [{"bbox": [x1,y1,x2,y2], "confidence": float}]"""
        h, w = img_bgr.shape[:2]
        score = conf if conf is not None else self.score_threshold
        nms = iou if iou is not None else self.nms_threshold
        logger.info(f"检测开始: img={w}x{h} conf={score} iou={nms}")
        t0 = time.perf_counter()
        results = self.model.predict(
            img_bgr, conf=score, iou=nms, imgsz=self.input_size, max_det=1000, verbose=False,
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
    """在图片上绘制检测框和计数"""
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
