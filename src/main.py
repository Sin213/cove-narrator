import os
import site
import sys
from pathlib import Path

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DISABLE_XET"] = "1"

if getattr(sys, 'frozen', False) and not sys.platform.startswith('linux'):
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
        if _deps_str not in sys.path:
            sys.path.append(_deps_str)
            site.addsitedir(_deps_str)

try:
    import torch
except ImportError:
    pass

from PySide6.QtWidgets import QApplication, QMessageBox
from src.app import MainWindow


def _global_exception_handler(exc_type, exc_value, exc_tb):
    import traceback
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Cove Narrator — Unexpected Error")
        box.setText(str(exc_value))
        box.setDetailedText(msg)
        box.exec()
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)
    sys.excepthook = _global_exception_handler
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
