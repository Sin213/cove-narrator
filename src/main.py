import os
import site
import sys
from pathlib import Path

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DISABLE_XET"] = "1"

if getattr(sys, 'frozen', False):
    _base = Path(sys.executable).parent
    _deps = _base / "dependencies" / "cove-narrator"
    if _deps.is_dir() and str(_deps) not in sys.path:
        site.addsitedir(str(_deps))
    _pydir = _base / "dependencies" / "_python"
    if _pydir.is_dir():
        for _zf in _pydir.glob("python*.zip"):
            if str(_zf) not in sys.path:
                sys.path.append(str(_zf))
elif sys.platform.startswith('linux'):
    _xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    _deps = Path(_xdg) / "cove-narrator" / "hd-deps"
    if _deps.is_dir():
        _deps_str = str(_deps)
        if _deps_str in sys.path:
            sys.path.remove(_deps_str)
        sys.path.insert(0, _deps_str)
        site.addsitedir(_deps_str)

from PySide6.QtWidgets import QApplication
from src.app import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
