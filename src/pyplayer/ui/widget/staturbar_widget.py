from PySide6 import QtCore, QtWidgets


class StatusBar(QtWidgets.QStatusBar):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lbl_title = QtWidgets.QLabel()
        self.lbl_title.setText("   Pas de média en cours")
        self.lbl_title.setMinimumWidth(300)
        self.lbl_title.setFixedHeight(40)
        self.lbl_title.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.lbl_title.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        self.addWidget(self.lbl_title, 1)

        # Indicateurs à droite : vitesse, boucle A-B, etc.
        self.lbl_info = QtWidgets.QLabel()
        self.lbl_info.setStyleSheet("color: #4CAF50; font-weight: bold; padding-right: 12px;")
        self.addPermanentWidget(self.lbl_info)

    def set_info(self, text: str):
        if self.lbl_info.text() != text:
            self.lbl_info.setText(text)
