from PySide6 import QtCore, QtWidgets

HIDE_DELAY_MS = 4000      # la barre s'efface après 4 s sans activité pendant la lecture
FADE_MS = 220


class StatusBar(QtWidgets.QStatusBar):
    """Barre d'état : titre du média, indicateurs (vitesse, boucle A-B…).

    Pendant la lecture elle s'efface en fondu après 4 s et revient dès qu'on la survole, qu'un message s'affiche ou
    que le titre change. Sa hauteur reste réservée : l'image de la vidéo ne bouge jamais. En pause, à l'arrêt ou si
    l'option est désactivée, elle reste visible.
    """

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

        self._enabled = True          # option « masquer automatiquement »
        self._playing = False         # le masquage n'a lieu que pendant la lecture
        self._hover = False           # le pointeur est sur la barre
        self._effect = QtWidgets.QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QtCore.QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(FADE_MS)
        self._idle = QtCore.QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(HIDE_DELAY_MS)
        self._idle.timeout.connect(self._fade_out)

        self.setMouseTracking(True)
        for widget in (self, self.lbl_title, self.lbl_info):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    # ------------------------------------------------------------------ contenu
    def set_info(self, text: str):
        if self.lbl_info.text() != text:
            self.lbl_info.setText(text)

    def set_title(self, text: str):
        if self.lbl_title.text() != text:
            self.lbl_title.setText(text)
            self.reveal()

    def showMessage(self, message: str, timeout: int = 0):  # noqa: N802 -- surcharge Qt
        super().showMessage(message, timeout)
        self.reveal()

    # ------------------------------------------------------------------ masquage automatique
    @property
    def opacity(self) -> float:
        return self._effect.opacity()

    def set_auto_hide(self, enabled: bool):
        self._enabled = bool(enabled)
        self.reveal()

    def set_playing(self, playing: bool):
        self._playing = bool(playing)
        self.reveal()

    def _should_hide(self) -> bool:
        return self._enabled and self._playing

    def reveal(self):
        """Réaffiche la barre ; si elle peut se masquer, relance le délai de 4 s."""
        self._animate_to(1.0)
        if self._should_hide() and not self._hover:
            self._idle.start()
        else:
            self._idle.stop()

    def _fade_out(self):
        if self._should_hide() and not self._hover:
            self._animate_to(0.0)

    def _animate_to(self, value: float):
        if abs(self._effect.opacity() - value) < 0.001 and self._fade.state() != QtCore.QAbstractAnimation.State.Running:
            return
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(value)
        self._fade.start()

    def eventFilter(self, obj, event):  # noqa: N802 -- surcharge Qt
        kind = event.type()
        if kind in (QtCore.QEvent.Type.Enter, QtCore.QEvent.Type.MouseMove):
            self._hover = True
            self._animate_to(1.0)
            self._idle.stop()                         # tant qu'on survole, la barre reste
        elif kind == QtCore.QEvent.Type.Leave and obj is self:
            self._hover = False
            if self._should_hide():
                self._idle.start()
        return super().eventFilter(obj, event)
