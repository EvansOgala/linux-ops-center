import json
from pathlib import Path

APP_DIR = Path.home() / ".config" / "linux_ops_center"
SETTINGS_PATH = APP_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "theme": "dark",
    "service_state_filter": "all",
    "service_search": "",
    "scan_path": str(Path.home()),
    "show_hidden": False,
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()

    merged = DEFAULT_SETTINGS.copy()
    merged.update(data)

    if merged.get("theme") not in {"dark", "light"}:
        merged["theme"] = DEFAULT_SETTINGS["theme"]

    if merged.get("service_state_filter") not in {"all", "running", "failed", "inactive"}:
        merged["service_state_filter"] = DEFAULT_SETTINGS["service_state_filter"]

    merged["service_search"] = str(merged.get("service_search", ""))
    merged["scan_path"] = str(merged.get("scan_path", str(Path.home())))
    merged["show_hidden"] = bool(merged.get("show_hidden", False))
    return merged


def save_settings(data: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
