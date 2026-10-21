from PySide6 import QtCore, QtGui, QtMultimedia, QtMultimediaWidgets, QtWidgets

from pyplayer.api import paths
from pyplayer.ui import theme
from pyplayer.ui.widget.thumbnails import ThumbnailBubble, ThumbnailProvider

SEEK_STEP_MS = 10_000
SEEK_STEP_LONG_MS = 60_000
CLICK_DELAY_MS = 230  # délai pour distinguer un clic simple d'un double-clic


class CustomSlider(QtWidgets.QSlider):
    """Slider de position : un clic saute à l'endroit visé, puis on peut faire glisser."""

    sliderClicked = QtCore.Signal(int)
    hovered = QtCore.Signal(int, int)       # (valeur survolée, abscisse dans le widget)
    hover_left = QtCore.Signal()

    BAR_HEIGHT = 20
    TRACK_REST = 4.0                        # épaisseur au repos, qui grossit au survol
    TRACK_HOVER = 7.0

    def __init__(self, orientation=QtCore.Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self._grow = 0.0                    # 0 = au repos, 1 = survolé (animé)
        self._hover_x: float | None = None
        self._loop: tuple[int | None, int | None] = (None, None)
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(130)
        self._anim.valueChanged.connect(self._on_grow)
        self.setup_ui()

    def setup_ui(self):
        """Apparence : tout est dessiné par ``paintEvent`` (fine au repos, plus épaisse au survol)."""
        self.setFixedHeight(self.BAR_HEIGHT)
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------ état visuel
    def set_loop(self, a_ms: int | None, b_ms: int | None) -> None:
        """Boucle A-B affichée sur la barre (bande verte entre A et B)."""
        if self._loop != (a_ms, b_ms):
            self._loop = (a_ms, b_ms)
            self.update()

    def _on_grow(self, value) -> None:
        self._grow = float(value)
        self.update()

    def _animate_grow(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._grow)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event):
        self._animate_grow(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.isSliderDown():
            self._animate_grow(0.0)
        self._hover_x = None
        self.update()
        self.hover_left.emit()
        super().leaveEvent(event)

    def _x_of(self, value: int) -> float:
        span = self.maximum() - self.minimum()
        return 0.0 if span <= 0 else (value - self.minimum()) / span * self.width()

    def paintEvent(self, event):  # noqa: N802 -- surcharge Qt
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        width, centre = float(self.width()), self.height() / 2
        thickness = self.TRACK_REST + (self.TRACK_HOVER - self.TRACK_REST) * self._grow
        track = QtCore.QRectF(0, centre - thickness / 2, width, thickness)
        radius = thickness / 2
        enabled = self.isEnabled()

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(theme.HOVER_COLOR if enabled else theme.THIRD_COLOR))
        painter.drawRoundedRect(track, radius, radius)
        if not enabled:
            return

        a, b = self._loop                                         # bande de la boucle A-B
        if a is not None:
            ax = self._x_of(a)
            bx = self._x_of(b) if b is not None else ax
            band = QtCore.QRectF(ax, centre - thickness / 2 - 2, max(2.0, bx - ax), thickness + 4)
            painter.setBrush(QtGui.QColor(76, 175, 80, 120))
            painter.drawRoundedRect(band, 2, 2)
            painter.setBrush(QtGui.QColor(theme.GREEN))
            for x in (ax, bx) if b is not None else (ax,):
                painter.drawRoundedRect(QtCore.QRectF(x - 1, centre - 7, 2, 14), 1, 1)

        position = self._x_of(self.sliderPosition())
        if position > 0:                                           # partie lue
            played = QtCore.QRectF(0, track.top(), position, thickness)
            painter.setBrush(QtGui.QColor(theme.OK_ONE_COLOR))
            painter.drawRoundedRect(played, radius, radius)

        if self._hover_x is not None and not self.isSliderDown():  # repère de survol
            painter.setBrush(QtGui.QColor(255, 255, 255, 150))
            painter.drawRoundedRect(QtCore.QRectF(self._hover_x - 1, centre - 8, 2, 16), 1, 1)

        if self._grow > 0.01 or self.isSliderDown():               # poignée : visible seulement au survol / glissement
            handle = 4.0 + 3.5 * max(self._grow, 1.0 if self.isSliderDown() else 0.0)
            x = min(max(position, handle), width - handle)
            painter.setBrush(QtGui.QColor("white"))
            painter.drawEllipse(QtCore.QPointF(x, centre), handle, handle)
            painter.setBrush(QtGui.QColor(theme.OK_ONE_COLOR))
            painter.drawEllipse(QtCore.QPointF(x, centre), handle - 2.5, handle - 2.5)

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
        x = event.position().x()
        self._hover_x = min(max(0.0, x), float(self.width()))
        if self.isEnabled():
            self.hovered.emit(self._value_at(x), int(self._hover_x))
        if self.isSliderDown():
            self.setSliderPosition(self._value_at(x))
            event.accept()
        else:
            self.update()
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if self.isSliderDown() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setSliderDown(False)      # émet sliderReleased
            if not self.rect().contains(event.position().toPoint()):
                self._animate_grow(0.0)    # relâché hors de la barre : plus de survol
                self.hover_left.emit()
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
        self.thumbnails = ThumbnailProvider(self)
        self.bubble = ThumbnailBubble()
        self.thumbnails_enabled = True
        self._hover_bucket: int | None = None
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
        self.slider.hovered.connect(self._on_slider_hover)
        self.slider.hover_left.connect(self._on_slider_hover_left)
        self.thumbnails.thumbnail_ready.connect(self._on_thumbnail_ready)

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
    def set_thumbnail_source(self, path: str | None, duration_ms: int = 0):
        """Média dont on affiche des miniatures au survol de la barre (``None`` : audio, flux réseau ou aucun média)."""
        self.thumbnails.set_source(path if self.thumbnails_enabled else None, duration_ms)
        if not path:
            self.bubble.hide()

    def set_thumbnails_enabled(self, enabled: bool):
        self.thumbnails_enabled = bool(enabled)
        if not enabled:
            self.thumbnails.set_source(None)
            self.bubble.hide()

    def _on_slider_hover(self, value: int, x: int):
        self.bubble.set_time(self.position_to_hms(value))
        if self.thumbnails.has_source:
            bucket = self.thumbnails.cache.bucket(value)
            if bucket != self._hover_bucket:
                self._hover_bucket = bucket
                cached = self.thumbnails.cache.get(bucket)
                self.bubble.set_image(cached)
            self.thumbnails.request(value)
        else:
            self._hover_bucket = None
            self.bubble.set_image(None)
        self.bubble.show_above(self.slider, x)

    def _on_slider_hover_left(self):
        if self.slider.isSliderDown():
            return                                    # pendant un glissement, la bulle suit le curseur même hors de la barre
        self.bubble.hide()
        self.thumbnails.cancel()
        self._hover_bucket = None

    def _on_thumbnail_ready(self, bucket: int, image):
        if bucket == self._hover_bucket and self.bubble.isVisible():
            self.bubble.set_image(image)
            self.bubble.show_above(self.slider, int(self.slider._hover_x or 0))

    def _slider_pressed(self):
        self._seeking = True

    def _slider_moved(self, value):
        # Pendant le glissement, on limite la fréquence des recherches (coûteuses).
        self._pending_seek = value
        if not self._seek_timer.isActive():
            self._seek_timer.start()

    def _slider_released(self):
        self._seeking = False
        if not self.slider.underMouse():
            self.bubble.hide()
            self.thumbnails.cancel()
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
