import os
import site
import sys
from pathlib import Path

from portable import is_portable, portable_data_dir

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DISABLE_XET"] = "1"

if is_portable():
    _deps = Path(os.path.join(portable_data_dir("cove-narrator"), "deps"))
    if _deps.is_dir() and str(_deps) not in sys.path:
        site.addsitedir(str(_deps))
elif getattr(sys, 'frozen', False) and not sys.platform.startswith('linux'):
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
    _deps = Path.home() / ".local" / "share" / "cove-narrator" / "hd-deps"
    if _deps.is_dir():
        _deps_str = str(_deps)
        if _deps_str not in sys.path:
            sys.path.append(_deps_str)
            site.addsitedir(_deps_str)

if getattr(sys, 'frozen', False):
    import multiprocessing
    import shutil
    _sys_py = shutil.which('python3') or shutil.which('python')
    if _sys_py:
        multiprocessing.set_executable(_sys_py)
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
