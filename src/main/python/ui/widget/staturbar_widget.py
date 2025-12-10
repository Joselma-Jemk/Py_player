from PySide6 import QtGui, QtCore, QtWidgets

class StatusBar(QtWidgets.QStatusBar):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = "Pas de média en cours"
        self.lbl_title=QtWidgets.QLabel()
        self.lbl_title.setText("Pas de média en cours")
        self.lbl_title.setFixedWidth(800)
        self.lbl_title.setFixedHeight(40)
        self.addWidget(self.lbl_title)