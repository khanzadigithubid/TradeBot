"""
Settings Store
Saves and loads runtime settings to/from a JSON file
so API keys set via the UI persist across restarts
"""

import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")


def load_settings() -> dict:
    """Load saved settings from disk"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_settings(data: dict):
    """Save settings to disk"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    # Merge with existing
    current = load_settings()
    current.update(data)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(current, f, indent=2)


def get_setting(key: str, default=None):
    """Get a single setting value"""
    return load_settings().get(key, default)
