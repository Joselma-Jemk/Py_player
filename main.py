"""

        ██████╗ ██╗   ██╗██████╗ ██╗      █████╗ ██╗   ██╗███████╗██████╗
        ██╔══██╗╚██╗ ██╔╝██╔══██╗██║     ██╔══██╗╚██╗ ██╔╝██╔════╝██╔══██╗
        ██████╔╝ ╚████╔╝ ██████╔╝██║     ███████║ ╚████╔╝ █████╗  ██████╔╝
        ██╔═══╝   ╚██╔╝  ██╔═══╝ ██║     ██╔══██║  ╚██╔╝  ██╔══╝  ██╔══██╗
        ██║        ██║   ██║     ███████╗██║  ██║   ██║   ███████╗██║  ██║
        ╚═╝        ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝

"""
import sys
from PySide6 import QtCore, QtWidgets
from src.main.python.ui.main_window import MainWindow

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())