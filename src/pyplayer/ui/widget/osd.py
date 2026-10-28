"""Messages superposés à la vidéo (OSD) : une carte de notification et des indicateurs.

  * en bas au centre, une CARTE de notification. Elle annonce la lecture (« Lecture » et le titre),
    la pause (« Pause » et le titre, tant qu'on est en pause) et chaque action (volume, vitesse,
    capture…). La lecture reprise s'efface seule ; la pause reste jusqu'à la reprise ; une action
    passe devant la pause et la retrouve ensuite ;
  * en haut à droite, des indicateurs persistants (vitesse, boucle A-B, répétition).

Ni la carte ni les indicateurs ne reçoivent la souris.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from pyplayer.ui import theme

MARGIN = 14
BOTTOM_MARGIN = 28
CARD_MAX_WIDTH = 560
DEFAULT_TIMEOUT_MS = 3500
PLAYBACK_TIMEOUT_MS = 2500  # une reprise de lecture s'annonce quelques secondes
FADE_MS = 260

PLAYING, PAUSED, STOPPED = "playing", "paused", "stopped"


def playback_notice(state: str, title: str) -> tuple[str, str, str] | None:
    """Ce que la carte annonce pour un état de lecture : (icône, titre, sous-titre), ou None (rien)."""
    if state == PLAYING:
        return ("play", "Lecture", title)
    if state == PAUSED:
        return ("pause", "Pause", title)
    return None


class NoticeCard(QtWidgets.QFrame):
    """La carte : une pastille d'icône, un titre et un sous-titre facultatif."""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("notice")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(f"""
            QFrame#notice {{
                background-color: rgba(22, 22, 24, 220);
                border: 1px solid rgba(76, 175, 80, 0.45);
                border-radius: 12px;
            }}
            QLabel#noticeIcon {{
                background-color: {theme.GREEN};
                color: #ffffff;
                border-radius: 16px;
            }}
            QLabel#noticeTitle {{
                background: transparent;
                color: {theme.PRINCIPAL_TEXT_COLOR};
                font-size: 14px;
                font-weight: 700;
            }}
            QLabel#noticeSub {{
                background: transparent;
                color: #a6a6ac;
                font-size: 12px;
            }}
        """)
        self.icon = QtWidgets.QLabel(self)
        self.icon.setObjectName("noticeIcon")
        self.icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.icon.setFixedSize(32, 32)
        self.title = QtWidgets.QLabel(self)
        self.title.setObjectName("noticeTitle")
        self.title.setWordWrap(True)
        self.sub = QtWidgets.QLabel(self)
        self.sub.setObjectName("noticeSub")
        self.sub.setWordWrap(True)

        texts = QtWidgets.QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(self.title)
        texts.addWidget(self.sub)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(14, 10, 20, 10)
        row.setSpacing(12)
        row.addWidget(self.icon, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(texts)
        self.hide()

    def set_content(self, glyph: str, headline: str, subtitle: str = "") -> None:
        self.icon.setFont(theme.load_icon_font(18))
        self.icon.setText(theme.GLYPHS.get(glyph, ""))
        self.title.setText(headline)
        self.sub.setText(subtitle)
        self.sub.setVisible(bool(subtitle))
        self.adjustSize()


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
    """Gère la carte et les indicateurs sur un widget hôte (la scène vidéo) et les repositionne
    quand il change de taille."""

    def __init__(self, host: QtWidgets.QWidget) -> None:
        super().__init__(host)
        self.host = host
        self.message = NoticeCard(host)
        self.info = _Bubble(host, color=theme.GREEN, bold=True)
        self._text = ""                    # message d'action affiché (currentMessage)
        self._playback: tuple[str, str] | None = None   # état de lecture et titre, pour la pause
        self._announce_after_action = False             # un changement d'état est survenu pendant une action
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
        """Une action (volume, vitesse, capture…) : elle passe devant l'état de lecture."""
        self._text = text
        self._display("info", text, "", timeout_ms)

    def show_playback(self, state: str, title: str) -> None:
        """La lecture change d'état. Pendant une action, on attend qu'elle soit finie."""
        self._playback = (state, title)
        if self._text:
            self._announce_after_action = True   # annoncé une fois l'action finie, pas avant
        else:
            self._show_playback_notice()

    def currentMessage(self) -> str:
        return self._text

    def clear(self) -> None:
        self._timer.stop()
        self._fade.stop()
        self._text = ""
        self._announce_after_action = False
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
    def _display(self, glyph: str, headline: str, subtitle: str, timeout_ms: int) -> None:
        self._fade.stop()
        self._effect.setOpacity(1.0)
        self.message.set_content(glyph, headline, subtitle)
        self.message.show()
        self.message.raise_()
        self._layout()
        if timeout_ms > 0:
            self._timer.start(timeout_ms)
        else:
            self._timer.stop()

    def _show_playback_notice(self) -> None:
        notice = playback_notice(*self._playback) if self._playback else None
        if notice is None:
            self._timer.stop()
            self._fade.stop()
            self.message.hide()
            return
        glyph, headline, subtitle = notice
        # La pause reste affichée jusqu'à la reprise ; une reprise de lecture s'efface seule.
        timeout = PLAYBACK_TIMEOUT_MS if glyph == "play" else 0
        self._display(glyph, headline, subtitle, timeout)

    def _start_fade(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _after_fade(self) -> None:
        if self._effect.opacity() > 0.01:
            return
        self._text = ""
        paused = self._playback is not None and self._playback[0] == PAUSED
        if self._announce_after_action or paused:
            # Une pause retrouve sa carte ; une lecture ne s'annonce que si elle a été reprise
            # pendant l'action. Un simple réglage pendant la lecture ne fait donc pas réapparaître « Lecture ».
            self._announce_after_action = False
            self._show_playback_notice()
        else:
            self.message.hide()

    def _layout(self) -> None:
        width, height = self.host.width(), self.host.height()
        self.message.setMaximumWidth(min(CARD_MAX_WIDTH, max(160, width - 2 * MARGIN)))
        self.message.adjustSize()
        self.message.move(max(MARGIN, (width - self.message.width()) // 2),
                          max(MARGIN, height - self.message.height() - BOTTOM_MARGIN))
        self.info.adjustSize()
        self.info.move(max(MARGIN, width - self.info.width() - MARGIN), MARGIN)

    def eventFilter(self, obj, event):
        if obj is self.host and event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show):
            self._layout()
        return super().eventFilter(obj, event)
