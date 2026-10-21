"""Bulle « Lien détecté » : propose de télécharger ou lire un lien copié, sans jamais interrompre la lecture."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from pyplayer.api.links import Link
from pyplayer.ui import theme

AUTO_HIDE_MS = 15_000
MARGIN = 14


class LinkToast(QtWidgets.QFrame):
    download_requested = QtCore.Signal(str)
    play_requested = QtCore.Signal(str)
    dismissed = QtCore.Signal()

    def __init__(self, host: QtWidgets.QWidget) -> None:
        super().__init__(host)
        self.host = host
        self.link: Link | None = None
        self.setStyleSheet(f"""
            QFrame#toast {{ background-color: rgba(28, 28, 30, 235); border: 1px solid {theme.HOVER_COLOR};
                           border-radius: 10px; }}
            QLabel {{ color: {theme.PRINCIPAL_TEXT_COLOR}; background: transparent; }}
            QPushButton {{ border: none; border-radius: 6px; padding: 6px 12px; font-weight: 700;
                          background-color: {theme.THIRD_COLOR}; color: {theme.PRINCIPAL_TEXT_COLOR}; }}
            QPushButton:hover {{ background-color: {theme.HOVER_COLOR}; }}
            QPushButton#primary {{ background-color: {theme.GREEN}; color: white; }}
            QPushButton#primary:hover {{ background-color: #66BB6A; }}
        """)
        self.setObjectName("toast")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        self.title = QtWidgets.QLabel("Lien détecté")
        self.title.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.detail = QtWidgets.QLabel("")
        self.detail.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        self.detail.setMaximumWidth(340)
        row = QtWidgets.QHBoxLayout()
        self.btn_download = QtWidgets.QPushButton("Télécharger")
        self.btn_download.setObjectName("primary")
        self.btn_play = QtWidgets.QPushButton("Lire")
        self.btn_ignore = QtWidgets.QPushButton("Ignorer")
        for button in (self.btn_download, self.btn_play, self.btn_ignore):
            row.addWidget(button)
        layout.addWidget(self.title)
        layout.addWidget(self.detail)
        layout.addLayout(row)
        self.btn_download.clicked.connect(lambda: self._choose(self.download_requested))
        self.btn_play.clicked.connect(lambda: self._choose(self.play_requested))
        self.btn_ignore.clicked.connect(self.dismiss)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        host.installEventFilter(self)
        self.hide()

    def offer(self, link: Link) -> None:
        self.link = link
        self.title.setText("Playlist détectée" if link.kind == "playlist" else "Lien détecté")
        self.detail.setText(link.label)
        self.btn_download.setText("Télécharger la playlist" if link.kind == "playlist" else "Télécharger")
        self.btn_play.setVisible(link.kind != "playlist")
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(AUTO_HIDE_MS)

    def dismiss(self) -> None:
        self._timer.stop()
        self.link = None
        if self.isVisible():
            self.hide()
            self.dismissed.emit()

    def _choose(self, signal) -> None:
        link = self.link
        self.dismiss()
        if link is not None:
            signal.emit(link.url)

    def _place(self) -> None:
        self.move(max(MARGIN, self.host.width() - self.width() - MARGIN),
                  max(MARGIN, self.host.height() - self.height() - 48))     # au-dessus de la barre de progression

    def eventFilter(self, obj, event):  # noqa: N802 -- surcharge Qt
        if obj is self.host and event.type() == QtCore.QEvent.Type.Resize and self.isVisible():
            self._place()
        return super().eventFilter(obj, event)
