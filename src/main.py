import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    _deps = Path(sys.executable).parent / "dependencies"
    if _deps.is_dir() and str(_deps) not in sys.path:
        sys.path.insert(0, str(_deps))

from PySide6.QtWidgets import QApplication
from src.app import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
