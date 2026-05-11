"""配置管理 — 全局 CONFIG 字典加载/保存"""
import os
import yaml

_CONFIG_PATH = None
_CONFIG = {}


def get_config_path():
    global _CONFIG_PATH
    if _CONFIG_PATH is None:
        _CONFIG_PATH = os.environ.get(
            "GRAIN_CONFIG_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"),
        )
    return _CONFIG_PATH


DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "model_path": "models/grain_v8m_v10.onnx",
    "input_size": 640,
    "score_threshold": 0.25,
    "nms_threshold": 0.5,
    "max_upload_mb": 10,
    "rate_limit_per_minute": 60,
    "require_api_key": True,
    "valuable_dir": "Valuable photos",
    "valuable_enable": True,
    "valuable_low_threshold": 0.5,
    "valuable_very_low_threshold": 0.3,
    "valuable_low_ratio": 0.20,
    "valuable_very_low_ratio": 0.08,
    "response_compress_min_size": 1000,
    "upload_timeout_seconds": 120,
    "inference_timeout_seconds": 300,
    "enable_response_compression": True,
}


def load_config(config_path=None, overrides: dict = None) -> dict:
    """加载 YAML 配置，合并默认值和覆盖项"""
    global _CONFIG
    path = config_path or get_config_path()
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        cfg.update(loaded)
    if overrides:
        cfg.update(overrides)
    _CONFIG = cfg


    # 将模型路径转为绝对路径（基于项目根目录）
    if not os.path.isabs(cfg["model_path"]):
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg["model_path"] = os.path.join(project_dir, cfg["model_path"])

    # 将 valuable_dir 转为绝对路径
    if not os.path.isabs(cfg["valuable_dir"]):
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg["valuable_dir"] = os.path.join(project_dir, cfg["valuable_dir"])

    return cfg


def get_config(key=None, default=None):
    """获取配置项"""
    if not _CONFIG:
        load_config()
    if key is None:
        return _CONFIG
    return _CONFIG.get(key, default)


def set_config(key, value):
    """设置配置项（运行时热更新）"""
    _CONFIG[key] = value


def get_project_root():
    """获取项目根目录"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
