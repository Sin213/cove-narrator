import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "whooshy"
_CONFIG_FILE = _CONFIG_DIR / "config.json"

_DEFAULTS = {
    "save_dir": str(Path.home() / "Music" / "Whooshy"),
    "last_voice": "af_heart",
    "window_width": 700,
    "window_height": 500,
}

def load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text())
            return {**_DEFAULTS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)

def save_config(config: dict):
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(config, indent=2))
