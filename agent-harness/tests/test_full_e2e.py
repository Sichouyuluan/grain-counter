"""End-to-end tests for the CLI harness via subprocess invocation."""
import os
import sys
import json
import shlex
import tempfile
import subprocess

import pytest
import cv2
import numpy as np

# From tests/ -> agent-harness/ -> project/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run(*args):
    """Run the CLI as a subprocess."""
    cmd = [sys.executable, "-m", "cli_anything.graincounter", "--json"] + list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=_PROJECT_ROOT, timeout=60,
    )
    return result


def _parse_json(output):
    """Extract the outermost JSON object/array from mixed logger+JSON output."""
    if not output:
        raise ValueError("Empty output")
    # Strip log lines (format: "YYYY-MM-DD HH:MM:SS [LEVEL] ...")
    lines = output.split("\n")
    json_lines = []
    in_json = False
    for line in lines:
        if not in_json:
            # Check if this line starts JSON
            stripped = line.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                in_json = True
                json_lines.append(line)
            # Skip log lines (start with date pattern)
            continue
        json_lines.append(line)
    clean = "\n".join(json_lines).strip()
    if not clean:
        raise ValueError(f"No JSON found in output: {output[:200]}")
    return json.loads(clean)


def _create_test_image(path, size=(320, 320)):
    img = np.zeros((*size, 3), dtype=np.uint8)
    for i in range(5):
        cx, cy = 50 + i * 60, 160
        cv2.circle(img, (cx, cy), 20, (200, 200, 200), -1)
    cv2.imwrite(path, img)
    return path


class TestCLIDetect:
    def test_detect_json_output(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = f.name
        try:
            _create_test_image(img_path)
            result = _run("detect", img_path)
            assert result.returncode == 0, result.stderr
            data = _parse_json(result.stdout)
            assert "count" in data
            assert "elapsed_ms" in data
            assert isinstance(data["count"], int)
        finally:
            os.unlink(img_path)

    def test_detect_with_output(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = f.name
        out_path = img_path.replace(".jpg", "_out.jpg")
        try:
            _create_test_image(img_path)
            result = _run("detect", img_path, "-o", out_path)
            assert result.returncode == 0, result.stderr
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
        finally:
            for p in [img_path, out_path]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_detect_nonexistent_image(self):
        result = _run("detect", "/nonexistent/file.jpg")
        assert result.returncode != 0


class TestCLIConfig:
    def test_config_show_json(self):
        result = _run("config", "show")
        assert result.returncode == 0, result.stderr
        data = _parse_json(result.stdout)
        assert "config" in data
        assert "port" in data["config"]

    def test_config_show_key(self):
        result = _run("config", "show", "port")
        assert result.returncode == 0, result.stderr
        data = _parse_json(result.stdout)
        assert "port" in data
        assert isinstance(data["port"], int)

    def test_config_list(self):
        result = _run("config", "list")
        assert result.returncode == 0, result.stderr
        data = _parse_json(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_config_set_no_persist(self):
        result = _run("config", "set", "port", "9000", "--no-persist")
        assert result.returncode == 0, result.stderr
        data = _parse_json(result.stdout)
        assert data["ok"] is True
        assert data["value"] == 9000


class TestCLIServer:
    def test_server_status_json(self):
        result = _run("server", "status")
        assert result.returncode == 0, result.stderr
        data = _parse_json(result.stdout)
        assert "running" in data
        assert "port" in data

    def test_server_stop_not_running(self):
        result = _run("server", "stop")
        data = _parse_json(result.stdout)
        assert data["ok"] is False


class TestCLIModel:
    def test_model_list_json(self):
        result = _run("model", "list")
        assert result.returncode == 0, result.stderr
        data = _parse_json(result.stdout)
        assert "models" in data
        assert isinstance(data["models"], list)


class TestCLIHelp:
    def test_help(self):
        result = _run("--help")
        assert result.returncode == 0
        assert "detect" in result.stdout
        assert "server" in result.stdout
        assert "config" in result.stdout
        assert "model" in result.stdout
