"""优质训练照片筛选器 — 自动保存低置信度图片到训练集"""
import os
import time
import threading
from datetime import datetime
import cv2
from graincounter.logger import get_logger
from graincounter.config import get_config

logger = get_logger()


class ValuablePhotoSaver:
    """检测完成后分析置信度分布，自动保存低置信度图片到优质训练照片目录"""

    def __init__(self):
        self._lock = threading.Lock()
        self._saved_count = 0
        self._valuable_dir = get_config("valuable_dir", "Valuable photos")
        os.makedirs(self._valuable_dir, exist_ok=True)
        logger.info(f"优质训练照片目录: {self._valuable_dir}")

    @property
    def saved_count(self):
        with self._lock:
            return self._saved_count

    def increment_count(self):
        with self._lock:
            self._saved_count += 1

    def reset_count(self):
        with self._lock:
            self._saved_count = 0

    def check_and_save(self, img_bgr, detections, filename="image.jpg"):
        """分析检测结果，如果满足筛选条件则保存原图"""
        if not get_config("valuable_enable", True):
            return False

        n = len(detections)
        if n == 0:
            return False

        confs = [d["confidence"] for d in detections]
        very_low_threshold = get_config("valuable_very_low_threshold", 0.3)
        low_threshold = get_config("valuable_low_threshold", 0.5)
        very_low_ratio_threshold = get_config("valuable_very_low_ratio", 0.08)
        low_ratio_threshold = get_config("valuable_low_ratio", 0.20)

        very_low_count = sum(1 for c in confs if c < very_low_threshold)
        low_count = sum(1 for c in confs if very_low_threshold <= c < low_threshold)

        very_low_ratio = very_low_count / n
        low_ratio = (very_low_count + low_count) / n

        # 判断是否触发筛选
        triggered = False
        reason = ""
        if low_ratio >= low_ratio_threshold:
            triggered = True
            reason = f"低置信度占比 {low_ratio:.1%} >= {low_ratio_threshold:.0%}"
        if very_low_ratio >= very_low_ratio_threshold:
            triggered = True
            reason = f"极低置信度占比 {very_low_ratio:.1%} >= {very_low_ratio_threshold:.0%}"

        if not triggered:
            logger.info(
                f"筛选跳过: {filename} | {n}框, 极低{very_low_count}({very_low_ratio:.1%}), 低{low_count}({low_ratio:.1%})"
            )
            return False

        # 保存原图
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(filename)[0]
            save_name = f"{base_name}_{timestamp}.jpg"
            save_path = os.path.join(self._valuable_dir, save_name)
            cv2.imwrite(save_path, img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
            with self._lock:
                self._saved_count += 1
            logger.info(
                f"[VALUABLE] saved: {save_name} | reason: {reason} | "
                f"{n}框, 极低{very_low_count}({very_low_ratio:.1%}), 低{low_count}({low_ratio:.1%})"
            )
            return True
        except Exception as e:
            logger.error(f"保存优质照片失败: {e}")
            return False
