import site
import sys
from pathlib import Path

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

from PySide6.QtWidgets import QApplication
from src.app import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
