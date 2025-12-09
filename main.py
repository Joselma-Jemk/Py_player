"""

        ██████╗ ██╗   ██╗██████╗ ██╗      █████╗ ██╗   ██╗███████╗██████╗
        ██╔══██╗╚██╗ ██╔╝██╔══██╗██║     ██╔══██╗╚██╗ ██╔╝██╔════╝██╔══██╗
        ██████╔╝ ╚████╔╝ ██████╔╝██║     ███████║ ╚████╔╝ █████╗  ██████╔╝
        ██╔═══╝   ╚██╔╝  ██╔═══╝ ██║     ██╔══██║  ╚██╔╝  ██╔══╝  ██╔══██╗
        ██║        ██║   ██║     ███████╗██║  ██║   ██║   ███████╗██║  ██║
        ╚═╝        ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝

"""
import sys
from PySide6 import QtCore, QtGui, QtWidgets
from src.main.python.ui.main_window import MainWindow

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, True)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())