"""Messages superposés à la vidéo (OSD) : remplace l'ancienne barre d'état.

Deux zones, dessinées au-dessus de l'image et transparentes à la souris :
  * en haut à gauche, un message temporaire (« Reprise à 03:13 », titre du média…) qui s'efface en fondu ;
  * en haut à droite, des indicateurs persistants (vitesse, boucle A-B, répétition).
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from pyplayer.ui import theme

MARGIN = 14
DEFAULT_TIMEOUT_MS = 3500
FADE_MS = 260


class _Bubble(QtWidgets.QLabel):
    def __init__(self, parent, *, color: str, bold: bool) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        weight = "700" if bold else "500"
        self.setStyleSheet(f"""
            QLabel {{ background-color: rgba(20, 20, 22, 190); color: {color}; border-radius: 8px;
                      padding: 6px 12px; font-size: 14px; font-weight: {weight}; }}
        """)
        self.setWordWrap(False)
        self.hide()


class Osd(QtCore.QObject):
    """Gère les deux bulles sur un widget hôte (la scène vidéo) et les repositionne quand il change de taille."""

    def __init__(self, host: QtWidgets.QWidget) -> None:
        super().__init__(host)
        self.host = host
        self.message = _Bubble(host, color=theme.PRINCIPAL_TEXT_COLOR, bold=False)
        self.info = _Bubble(host, color=theme.GREEN, bold=True)
        self._text = ""
        self._effect = QtWidgets.QGraphicsOpacityEffect(self.message)
        self._effect.setOpacity(1.0)
        self.message.setGraphicsEffect(self._effect)
        self._fade = QtCore.QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(FADE_MS)
        self._fade.finished.connect(self._after_fade)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_fade)
        host.installEventFilter(self)

    # ------------------------------------------------------------------ API
    def show_message(self, text: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
        self._text = text
        self.message.setText(text)
        self._fade.stop()
        self._effect.setOpacity(1.0)
        self.message.show()
        self.message.raise_()
        self._layout()
        if timeout_ms > 0:
            self._timer.start(timeout_ms)
        else:
            self._timer.stop()

    def currentMessage(self) -> str:  # noqa: N802 -- même nom que QStatusBar : les appelants n'ont rien à changer
        return self._text

    def clear(self) -> None:
        self._timer.stop()
        self._fade.stop()
        self._text = ""
        self.message.hide()

    def set_info(self, text: str) -> None:
        text = text.strip()
        if text:
            if self.info.text() != text:
                self.info.setText(text)
            self.info.show()
            self.info.raise_()
            self._layout()
        else:
            self.info.setText("")
            self.info.hide()

    @property
    def info_text(self) -> str:
        return self.info.text()

    # ------------------------------------------------------------------ interne
    def _start_fade(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _after_fade(self) -> None:
        if self._effect.opacity() <= 0.01:
            self.message.hide()
            self._text = ""

    def _layout(self) -> None:
        width = self.host.width()
        self.message.setMaximumWidth(max(120, width - 2 * MARGIN - (self.info.width() + MARGIN if self.info.isVisible() else 0)))
        self.message.adjustSize()
        self.info.adjustSize()
        self.message.move(MARGIN, MARGIN)
        self.info.move(max(MARGIN, width - self.info.width() - MARGIN), MARGIN)

    def eventFilter(self, obj, event):  # noqa: N802 -- surcharge Qt
        if obj is self.host and event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show):
            self._layout()
        return super().eventFilter(obj, event)
