"""Application bootstrap — wires Qt app, config, and main window."""

import sys
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from src.pyplayer.infrastructure.config.settings import CONFIG
from src.pyplayer.ui.main_window import MainWindow


def run() -> None:
    """Install-ready entry point."""
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseOpenGLES)
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    run()