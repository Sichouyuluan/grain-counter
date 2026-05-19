"""Unit tests for CLI harness core backends.

Run from project root:
    python -m pytest agent-harness/cli_anything/graincounter/tests/test_core.py -v
"""
import os
import sys
import json
import tempfile
from pathlib import Path

import pytest
import cv2
import numpy as np

# Ensure project root is importable (tests/ -> agent-harness/ -> project/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from cli_anything.graincounter.core.detector_backend import DetectorBackend
from cli_anything.graincounter.core.config_backend import ConfigBackend
from cli_anything.graincounter.core.server_backend import ServerBackend


def _create_test_image(path, size=(320, 320)):
    """Create a small test image with some shapes (simulated grains)."""
    img = np.zeros((*size, 3), dtype=np.uint8)
    for i in range(5):
        cx, cy = 50 + i * 60, 160
        cv2.circle(img, (cx, cy), 20, (200, 200, 200), -1)
    cv2.imwrite(path, img)
    return path


class TestDetectorBackend:
    def test_list_models(self):
        backend = DetectorBackend()
        models = backend.list_models()
        assert isinstance(models, list)
        if models:
            assert "name" in models[0]
            assert "size_mb" in models[0]

    def test_detect_nonexistent_image(self):
        backend = DetectorBackend()
        with pytest.raises(FileNotFoundError):
            backend.detect("/nonexistent/path/image.jpg")

    def test_detect_on_test_image(self):
        backend = DetectorBackend()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = f.name
        try:
            _create_test_image(img_path)
            result = backend.detect(img_path)
            assert "count" in result
            assert "elapsed_ms" in result
            assert "detections" in result
            assert "image_size" in result
            assert isinstance(result["count"], int)
            assert isinstance(result["elapsed_ms"], float)
        finally:
            os.unlink(img_path)

    def test_detect_with_output(self):
        backend = DetectorBackend()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            out_path = f.name
        try:
            _create_test_image(img_path)
            result = backend.detect(img_path, output=out_path)
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
        finally:
            for p in [img_path, out_path]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_detect_json_output(self):
        backend = DetectorBackend()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = f.name
        try:
            _create_test_image(img_path)
            result = backend.detect(img_path, json_only=True)
            assert "result_image" in result
            assert result["result_image"].startswith("data:image/jpeg;base64,")
        finally:
            os.unlink(img_path)


class TestConfigBackend:
    def test_show_all(self):
        backend = ConfigBackend()
        result = backend.show()
        assert "config" in result
        assert "defaults" in result
        assert "port" in result["config"]

    def test_show_single_key(self):
        backend = ConfigBackend()
        result = backend.show("port")
        assert "port" in result
        assert isinstance(result["port"], int)

    def test_show_unknown_key(self):
        backend = ConfigBackend()
        result = backend.show("nonexistent_key_xyz")
        assert "error" in result

    def test_set_bool(self):
        backend = ConfigBackend()
        original = backend.show("require_api_key")
        try:
            result = backend.set("require_api_key", "false", persist=False)
            assert result["ok"] is True
            assert result["value"] is False
        finally:
            backend.set("require_api_key", str(original["require_api_key"]), persist=False)

    def test_set_int(self):
        backend = ConfigBackend()
        original = backend.show("port")
        try:
            result = backend.set("port", "9999", persist=False)
            assert result["ok"] is True
            assert result["value"] == 9999
        finally:
            backend.set("port", str(original["port"]), persist=False)

    def test_reset_single(self):
        backend = ConfigBackend()
        backend.set("port", "12345", persist=False)
        result = backend.reset("port")
        assert result["ok"] is True
        assert result["value"] == 8000  # default

    def test_list_keys(self):
        backend = ConfigBackend()
        items = backend.list_keys()
        assert isinstance(items, list)
        assert len(items) > 5
        for item in items:
            assert "key" in item
            assert "value" in item
            assert "default" in item


class TestServerBackend:
    def test_status_stopped(self):
        backend = ServerBackend()
        status = backend.status()
        assert status["running"] is False
        assert "port" in status
        assert "model" in status

    def test_stop_when_not_running(self):
        backend = ServerBackend()
        result = backend.stop()
        assert result["ok"] is False
        assert "error" in result

    def test_url_when_not_running(self):
        backend = ServerBackend()
        result = backend.url()
        assert result["ok"] is False
