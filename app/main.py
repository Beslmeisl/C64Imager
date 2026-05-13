"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

# Ensure absolute import "app.*" works when running "python app/main.py".
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
