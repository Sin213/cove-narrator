import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "cove-narrator"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_OLD_CONFIG_DIR = Path.home() / ".config" / "whooshy"

_DEFAULTS = {
    "save_dir": str(Path.home() / "Music" / "Cove Narrator"),
    "last_voice": "af_heart",
    "window_width": 700,
    "window_height": 500,
}


def _migrate_old_config():
    """Copy old Whooshy config and presets on first launch."""
    import shutil
    old_config = _OLD_CONFIG_DIR / "config.json"
    if not old_config.exists() or _CONFIG_FILE.exists():
        return
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for src in _OLD_CONFIG_DIR.rglob("*"):
        if not src.is_file():
            continue
        dst = _CONFIG_DIR / src.relative_to(_OLD_CONFIG_DIR)
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))


def load_config() -> dict:
    _migrate_old_config()
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
