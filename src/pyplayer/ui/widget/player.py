from PySide6 import QtCore, QtGui, QtMultimedia, QtMultimediaWidgets, QtWidgets

from pyplayer.api import paths
from pyplayer.ui import theme

SEEK_STEP_MS = 10_000
SEEK_STEP_LONG_MS = 60_000
CLICK_DELAY_MS = 230  # délai pour distinguer un clic simple d'un double-clic


class CustomSlider(QtWidgets.QSlider):
    """Slider de position : un clic saute à l'endroit visé, puis on peut faire glisser."""

    sliderClicked = QtCore.Signal(int)

    def __init__(self, orientation=QtCore.Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setup_ui()

    def setup_ui(self):
        """Configure l'apparence du slider"""
        self.setStyleSheet("""
              QSlider::groove:horizontal {
                   background: #e0e0e0; /* Fond gris clair */
                   height: 4px; /* Hauteur réduite pour la groove */
                   border-radius: 2px; /* Coins arrondis */
                   margin: 2px 0; /* Marge minimale */}
              QSlider::handle:horizontal {
                   background: #f0f00f; /* Bleu clair pour le handle */
                   width: 7px; /* Largeur du handle, dépassant la groove */
                   height: 7px; /* Hauteur égale pour un cercle */
                   border-radius: 7px; /* Rayon maximal pour un cercle parfait */
                   margin: -2px 0; /* Dépassement vers le haut et le bas */}
              QSlider::sub-page:horizontal {
                   background: #2196F3;
                   margin: 2px 0;
                   border-radius: 2px; /* Coins arrondis */}
                   """)

    def _value_at(self, x: float) -> int:
        span = max(1, self.width())
        ratio = min(1.0, max(0.0, x / span))
        return int(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() != QtCore.Qt.MouseButton.LeftButton or not self.isEnabled():
            return super().mousePressEvent(event)
        value = self._value_at(event.position().x())
        self.setSliderDown(True)           # émet sliderPressed
        self.setSliderPosition(value)
        self.sliderClicked.emit(value)
        event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self.isSliderDown():
            self.setSliderPosition(self._value_at(event.position().x()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if self.isSliderDown() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setSliderDown(False)      # émet sliderReleased
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class PlayerWidget(QtWidgets.QWidget):
    signal_double_click = QtCore.Signal()
    clicked = QtCore.Signal()
    wheel_volume = QtCore.Signal(int)          # +1 / -1
    mouse_moved = QtCore.Signal()
    context_menu_requested = QtCore.Signal(QtCore.QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._seeking = False
        self._pending_seek: int | None = None
        self._click_timer = QtCore.QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(CLICK_DELAY_MS)
        self._click_timer.timeout.connect(self.clicked.emit)
        self._seek_timer = QtCore.QTimer(self)
        self._seek_timer.setSingleShot(True)
        self._seek_timer.setInterval(60)
        self._seek_timer.timeout.connect(self._apply_pending_seek)
        self.setup_ui()

    def setup_ui(self):
        self.customize_self()
        self.create_widgets()
        self.configure_widgets()
        self.create_layout()
        self.setup_connections()
        self.show_placeholder()

    def customize_self(self):
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.setMinimumWidth(650)
        self.setMinimumHeight(400)
        self.setMouseTracking(True)

    def create_widgets(self):
        self.video_output = QtMultimediaWidgets.QVideoWidget()
        self.audio_output = QtMultimedia.QAudioOutput()
        self.video_player = QtMultimedia.QMediaPlayer()
        self.video_player.setVideoOutput(self.video_output)
        self.video_player.setAudioOutput(self.audio_output)

        self.slider = CustomSlider(QtCore.Qt.Orientation.Horizontal)
        self.placeholder_label = QtWidgets.QLabel()
        self.subtitle_label = QtWidgets.QLabel()

    def configure_widgets(self):
        self.slider.setEnabled(False)

        icon_path = paths.placeholder_icon_path()
        if icon_path.exists():
            self.placeholder_label.setPixmap(QtGui.QPixmap(str(icon_path)))
        self.placeholder_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet(f"background: {theme.PRINCIPAL_COLOR};")

        self.subtitle_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet(
            "background: transparent; color: white; font-size: 20px; font-weight: 600; padding: 4px 12px;")
        self.subtitle_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.subtitle_label.setVisible(False)

        for widget in (self.video_output, self.placeholder_label):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    def create_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 3, 0, 3)
        self.main_layout.setSpacing(0)

        # Les sous-titres sont superposés à la vidéo.
        self.stage = QtWidgets.QWidget()
        stage_layout = QtWidgets.QStackedLayout(self.stage)
        stage_layout.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackAll)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        self.subtitle_holder = QtWidgets.QWidget()
        self.subtitle_holder.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        holder_layout = QtWidgets.QVBoxLayout(self.subtitle_holder)
        holder_layout.setContentsMargins(20, 0, 20, 28)
        holder_layout.addStretch(1)
        holder_layout.addWidget(self.subtitle_label)
        stage_layout.addWidget(self.video_output)
        stage_layout.addWidget(self.subtitle_holder)
        stage_layout.setCurrentWidget(self.subtitle_holder)

        self.main_layout.addWidget(self.placeholder_label)
        self.main_layout.addWidget(self.stage)
        self.main_layout.addWidget(self.slider)

    def setup_connections(self):
        player = self.video_player
        player.durationChanged.connect(self._on_duration_changed)
        player.positionChanged.connect(self._on_position_changed)
        player.mediaStatusChanged.connect(self._on_media_status_changed)
        player.hasVideoChanged.connect(self._refresh_display_mode)

        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)
        self.slider.sliderMoved.connect(self._slider_moved)

    # ===================================================================
    # GESTION MÉDIA
    # ===================================================================
    def _on_duration_changed(self, duration):
        self.slider.setRange(0, duration if duration > 0 else 0)

    def _on_position_changed(self, position):
        if not self._seeking:
            self.slider.blockSignals(True)
            self.slider.setValue(position)
            self.slider.blockSignals(False)

    def _on_media_status_changed(self, status):
        Status = QtMultimedia.QMediaPlayer.MediaStatus
        if status in (Status.NoMedia, Status.InvalidMedia):
            self.show_placeholder()
            self.slider.setEnabled(False)
            self.slider.setValue(0)
        elif status in (Status.LoadedMedia, Status.BufferedMedia, Status.BufferingMedia):
            self._refresh_display_mode()
            if self.video_player.duration() > 0:
                self.slider.setEnabled(True)
        elif status == Status.EndOfMedia:
            self.slider.setValue(self.slider.maximum())

    def _refresh_display_mode(self, *_):
        """Image du média si c'est une vidéo, logo si c'est un fichier audio ou s'il n'y a rien."""
        Status = QtMultimedia.QMediaPlayer.MediaStatus
        if self.video_player.mediaStatus() == Status.NoMedia:
            return
        if self.video_player.hasVideo():
            self.show_video()
        else:
            self.show_placeholder()

    # ===================================================================
    # SLIDER / RECHERCHE
    # ===================================================================
    def _slider_pressed(self):
        self._seeking = True

    def _slider_moved(self, value):
        # Pendant le glissement, on limite la fréquence des recherches (coûteuses).
        self._pending_seek = value
        if not self._seek_timer.isActive():
            self._seek_timer.start()

    def _slider_released(self):
        self._seeking = False
        self._seek_timer.stop()
        self._pending_seek = None
        self.video_player.setPosition(self.slider.value())

    def _apply_pending_seek(self):
        if self._pending_seek is not None and self._seeking:
            self.video_player.setPosition(self._pending_seek)
            self._pending_seek = None

    def seek_relative(self, delta_ms: int):
        player = self.video_player
        if player.duration() <= 0 or not player.isSeekable():
            return
        player.setPosition(max(0, min(player.position() + delta_ms, player.duration())))

    # ===================================================================
    # AFFICHAGE
    # ===================================================================
    def show_video(self):
        self.placeholder_label.setVisible(False)
        self.stage.setVisible(True)

    def show_placeholder(self):
        self.placeholder_label.setVisible(True)
        self.stage.setVisible(False)

    def set_subtitle_text(self, text: str):
        self.subtitle_label.setVisible(bool(text))
        if self.subtitle_label.text() != text:
            self.subtitle_label.setText(text)

    def set_aspect_mode(self, mode: str):
        modes = {
            "fit": QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            "stretch": QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
            "fill": QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        }
        self.video_output.setAspectRatioMode(modes.get(mode, modes["fit"]))

    def position_to_hms(self, ms):
        seconds = max(0, int(ms)) // 1000
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ===================================================================
    # SOURIS (vidéo et logo)
    # ===================================================================
    def eventFilter(self, obj, event):
        if obj in (self.video_output, self.placeholder_label):
            kind = event.type()
            Event = QtCore.QEvent.Type
            if kind == Event.MouseButtonDblClick and event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._click_timer.stop()
                self.signal_double_click.emit()
                return True
            if kind == Event.MouseButtonRelease and event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._click_timer.start()
                return True
            if kind == Event.MouseMove:
                self.mouse_moved.emit()
            elif kind == Event.Wheel:
                delta = event.angleDelta().y()
                if delta:
                    self.wheel_volume.emit(1 if delta > 0 else -1)
                return True
            elif kind == Event.ContextMenu:
                self.context_menu_requested.emit(event.globalPos())
                return True
        return super().eventFilter(obj, event)

    def mouseDoubleClickEvent(self, event):
        self.signal_double_click.emit()
        super().mouseDoubleClickEvent(event)
