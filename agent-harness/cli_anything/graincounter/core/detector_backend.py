"""Direct detection backend — uses GrainDetector without a running server."""
import os
import sys
import time
import json
import base64
from pathlib import Path

import cv2
import numpy as np

# Resolve project root relative to this file (agent-harness/cli_anything/graincounter/core/ -> 5 levels up)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from graincounter.config import load_config, get_config
from graincounter.detector import GrainDetector, draw_results


class DetectorBackend:
    """One-shot detection without a running web server."""

    def __init__(self):
        load_config()
        self._detector = None
        self._current_model = None

    def _get_detector(self, model_name=None):
        if model_name:
            model_path = os.path.normpath(os.path.join(_PROJECT_ROOT, "models", model_name))
        else:
            model_path = get_config("model_path")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")

        if self._detector is None or model_name != self._current_model:
            self._detector = GrainDetector(
                model_path=model_path,
                input_size=get_config("input_size", 640),
                score_threshold=get_config("score_threshold", 0.25),
                nms_threshold=get_config("nms_threshold", 0.5),
            )
            self._current_model = model_name
        return self._detector

    def detect(self, image_path, conf=None, iou=None, output=None, json_only=False):
        """Run detection on an image file."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        detector = self._get_detector()
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        t0 = time.perf_counter()
        results = detector.detect(img, conf=conf, iou=iou)
        elapsed = time.perf_counter() - t0

        output_data = {
            "count": len(results),
            "elapsed_ms": round(elapsed * 1000, 1),
            "detections": results,
            "image_size": {"width": img.shape[1], "height": img.shape[0]},
            "source": os.path.basename(image_path),
        }

        if output and not json_only:
            vis = draw_results(img, results)
            cv2.imwrite(output, vis, [cv2.IMWRITE_JPEG_QUALITY, 90])
            output_data["output"] = output

        if json_only:
            vis = draw_results(img, results)
            _, buffer = cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 90])
            output_data["result_image"] = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

        return output_data

    def list_models(self):
        """List available ONNX models."""
        models_dir = os.path.join(_PROJECT_ROOT, "models")
        if not os.path.isdir(models_dir):
            return []
        files = [f for f in os.listdir(models_dir) if f.endswith(".onnx")]
        files.sort()
        current = os.path.basename(get_config("model_path"))
        result = []
        for f in files:
            full = os.path.join(models_dir, f)
            size_mb = round(os.path.getsize(full) / 1024 / 1024, 1)
            result.append({"name": f, "size_mb": size_mb, "active": f == current})
        return result
