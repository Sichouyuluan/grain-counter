"""HTTP client for interacting with the Grain Counter API when server is running."""
import os
import json
import base64

import requests


class GrainAPIClient:
    """Thin HTTP wrapper around the Grain Counter FastAPI server."""

    def __init__(self, base_url=None, api_key=None):
        if base_url is None:
            port = os.environ.get("GRAIN_PORT", "8000")
            base_url = f"http://127.0.0.1:{port}"
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def _get(self, path, **kwargs):
        return self.session.get(f"{self.base_url}{path}", timeout=10, **kwargs)

    def _post(self, path, **kwargs):
        return self.session.post(f"{self.base_url}{path}", timeout=30, **kwargs)

    def _put(self, path, **kwargs):
        return self.session.put(f"{self.base_url}{path}", timeout=10, **kwargs)

    # ── Health / Info ──

    def health(self):
        r = self._get("/api/health")
        r.raise_for_status()
        return r.json()

    def ping(self):
        r = self._get("/api/ping")
        r.raise_for_status()
        return r.json()

    def public_config(self):
        r = self._get("/api/config")
        r.raise_for_status()
        return r.json()

    # ── Detection ──

    def detect(self, image_path, conf=None, iou=None):
        params = {}
        if conf is not None:
            params["conf"] = conf
        if iou is not None:
            params["iou"] = iou
        with open(image_path, "rb") as f:
            r = self._post("/api/detect", files={"file": f}, params=params)
        r.raise_for_status()
        return r.json()

    def save_image(self, image_path):
        with open(image_path, "rb") as f:
            r = self._post("/api/save-image", files={"file": f})
        r.raise_for_status()
        return r.json()

    # ── Models ──

    def list_models(self):
        r = self._get("/api/models")
        r.raise_for_status()
        return r.json()

    def select_model(self, model_name):
        r = self._post("/api/select-model", json={"model": model_name})
        r.raise_for_status()
        return r.json()

    def warm_model(self, model_name):
        r = self._post("/api/models/warm", json={"model": model_name})
        r.raise_for_status()
        return r.json()

    def warm_status(self):
        r = self._get("/api/models/warm-status")
        r.raise_for_status()
        return r.json()

    # ── Auth / Key ──

    def get_key(self):
        r = self._get("/api/key")
        r.raise_for_status()
        return r.json()

    def regenerate_key(self):
        r = self._post("/api/key/regenerate")
        r.raise_for_status()
        return r.json()

    def toggle_auth(self):
        r = self._post("/api/toggle-auth")
        r.raise_for_status()
        return r.json()

    # ── Stats / Security ──

    def stats(self):
        r = self._get("/api/stats")
        r.raise_for_status()
        return r.json()

    def attack_log(self, limit=50):
        r = self._get("/api/attack-log", params={"limit": limit})
        r.raise_for_status()
        return r.json()

    def scan_config(self):
        r = self._get("/api/scan-config")
        r.raise_for_status()
        return r.json()

    def update_scan_config(self, **kwargs):
        r = self._put("/api/scan-config", json=kwargs)
        r.raise_for_status()
        return r.json()

    # ── Devices ──

    def online_devices(self):
        r = self._get("/api/online-devices")
        r.raise_for_status()
        return r.json()

    def kick_device(self, device_id):
        r = self._post("/api/kick-device", json={"device_id": device_id})
        r.raise_for_status()
        return r.json()
