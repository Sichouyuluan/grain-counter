"""Configuration backend — read/write config.yaml directly."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from graincounter.config import load_config, get_config, set_config, DEFAULT_CONFIG, get_project_root


class ConfigBackend:
    """Manages configuration outside the server process."""

    def __init__(self):
        load_config()

    def show(self, key=None):
        """Show all or one config value."""
        if key:
            val = get_config(key)
            if val is None:
                return {"error": f"Unknown key: {key}"}
            return {key: val}
        cfg = get_config()
        return {
            "config": dict(cfg),
            "defaults": DEFAULT_CONFIG,
        }

    def set(self, key, value, persist=True):
        """Set a config value with type coercion."""
        if key in DEFAULT_CONFIG:
            default_val = DEFAULT_CONFIG[key]
            if isinstance(default_val, bool):
                value = value.lower() in ("true", "1", "yes", "on")
            elif isinstance(default_val, int):
                value = int(value)
            elif isinstance(default_val, float):
                value = float(value)
        set_config(key, value, persist=persist)
        return {"ok": True, "key": key, "value": get_config(key)}

    def reset(self, key=None):
        """Reset one or all config keys to defaults."""
        if key:
            if key in DEFAULT_CONFIG:
                set_config(key, DEFAULT_CONFIG[key], persist=True)
                return {"ok": True, "key": key, "value": DEFAULT_CONFIG[key]}
            return {"error": f"Unknown key: {key}"}
        for k, v in DEFAULT_CONFIG.items():
            set_config(k, v, persist=True)
        return {"ok": True, "message": "All config reset to defaults"}

    def list_keys(self):
        """List all config keys with current values."""
        cfg = get_config()
        return [
            {"key": k, "value": cfg.get(k), "default": DEFAULT_CONFIG.get(k)}
            for k in DEFAULT_CONFIG
        ]
