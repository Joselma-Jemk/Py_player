from pathlib import Path

from PySide6 import QtCore, QtGui, QtMultimedia, QtMultimediaWidgets, QtWidgets

from src.pyplayer.ui.theme import PRINCIPAL_COLOR, py_player_icone
from src.pyplayer.infrastructure.filesystem import find_path


class CustomSlider(QtWidgets.QSlider):
    """Slider personnalise avec click direct sur la position."""

    sliderClicked = QtCore.Signal(int)

    def __init__(self, orientation=QtCore.Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet(
            """
              QSlider::groove:horizontal {
                   background: rgba(86, 92, 99, 0.55);
                   height: 6px;
                   border-radius: 3px;
                   margin: 4px 0;}
              QSlider::handle:horizontal {
                   background: #f5f7fa;
                   border: 2px solid #62d66b;
                   width: 12px;
                   height: 12px;
                   border-radius: 8px;
                   margin: -5px 0;}
              QSlider::sub-page:horizontal {
                   background: #4CAF50;
                   margin: 4px 0;
                   border-radius: 3px;}
              QSlider::add-page:horizontal {
                   background: rgba(58, 63, 69, 0.45);
                   margin: 4px 0;
                   border-radius: 3px;}
              QSlider::handle:horizontal:hover {
                   background: white;
                   border: 2px solid #8CF095;}
                   """
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            pos = event.position().x()

            if self.width() > 0:
                value = (self.maximum() - self.minimum()) * pos / self.width() + self.minimum()
                value = max(self.minimum(), min(self.maximum(), int(value)))
                self.sliderClicked.emit(int(value))
                self.setValue(int(value))

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton and self.isSliderDown():
            pos = event.position().x()
            if self.width() > 0:
                value = (self.maximum() - self.minimum()) * pos / self.width() + self.minimum()
                value = max(self.minimum(), min(self.maximum(), int(value)))

                self.setValue(value)
                self.valueChanged.emit(value)

        super().mouseMoveEvent(event)


class PlayerWidget(QtWidgets.QWidget):
    signal_double_click = QtCore.Signal()
    player_initialized = QtCore.Signal()  # Signal emitted when player is ready

    def __init__(self, parent=None):
        super().__init__(parent)
        self._seeking = False
        self._player_initialized = False  # Lazy initialization flag
        self._initializing = False  # Prevent concurrent initialization
        self._ready_callbacks = []
        self._video_output = None
        self._audio_output = None
        self._video_player = None
        self._pending_volume = None  # Store volume until audio output is created
        self._pending_mute = None  # Store mute state until audio output is created
        self.setup_ui()

    def setup_ui(self):
        self.customize_self()
        self.create_widgets()
        self.configure_widgets()
        self.create_layout()
        self.setup_connections()
        self._show_placeholder_mode()

    def customize_self(self):
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.setMinimumWidth(650)
        self.setMinimumHeight(400)
        self.setStyleSheet("background-color: #141618;")

    def create_widgets(self):
        # Don't create QtMultimedia widgets here - lazy init
        self.slider = CustomSlider(QtCore.Qt.Orientation.Horizontal)
        self.placeholder_label = QtWidgets.QLabel()

    def configure_widgets(self):
        self.slider.setEnabled(False)
        self.slider.setFixedHeight(22)

        icon_path = py_player_icone(4) if py_player_icone else ""
        if icon_path and Path(icon_path).exists():
            self.placeholder_label.setPixmap(QtGui.QPixmap(icon_path))
        else:
            # Fallback text if no icon
            self.placeholder_label.setText(
                "<div style='text-align: center; padding: 20px;'>"
                "<h2>PyPlayer</h2>"
                "<p>Select a video from the playlist to start watching</p>"
                "</div>"
            )
        self.placeholder_label.setWordWrap(True)
        self.placeholder_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.placeholder_label.setStyleSheet(
            f"""
            QLabel {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a2d31,
                    stop:0.55 #24272b,
                    stop:1 #141618
                );
                color: #f5f7fa;
                border: 1px solid rgba(255,255,255,0.04);
            }}
            """
        )

    def create_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 4, 8)
        self.main_layout.setSpacing(8)

        # Only add placeholder initially - video output will be added when initialized
        self.main_layout.addWidget(self.placeholder_label, 1)
        self.main_layout.addWidget(self.slider)

    def setup_connections(self):
        # Don't connect video_player signals here - will connect in _ensure_player_initialized()
        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)
        self.slider.valueChanged.connect(self._slider_value_changed)
        self.slider.sliderClicked.connect(self._slider_clicked)

        # Keyboard shortcuts will trigger lazy init via _seek
        QtGui.QShortcut(QtCore.Qt.Key.Key_Left, self, lambda: self._seek(-10000))
        QtGui.QShortcut(QtCore.Qt.Key.Key_Right, self, lambda: self._seek(10000))

    def _ensure_player_initialized(self):
        """Lazy initialization of QtMultimedia widgets on first use."""
        if self._player_initialized:
            return

        if self._initializing:
            return

        self._initializing = True

        # Show loading state (without blocking processEvents)
        self.placeholder_label.setText(
            """
            <div style='text-align: center; padding: 36px 24px;'>
                <div style='font-size: 42px; color: #66d46f; margin-bottom: 10px;'>◌</div>
                <h3 style='margin: 0; color: #f5f7fa; font-size: 24px; font-weight: 700;'>Initialisation du lecteur</h3>
                <p style='margin-top: 10px; color: #a9b1b8; font-size: 14px;'>Chargement multimédia unique. Le lecteur sera prêt dans un instant.</p>
            </div>
            """
        )
        self.placeholder_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2b3034,
                    stop:0.5 #1f2225,
                    stop:1 #101214
                );
                color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
                border: 1px solid rgba(255,255,255,0.04);
            }
        """)

        # Non-blocking initialization via timer
        QtCore.QTimer.singleShot(0, self._do_player_initialization)

    def _do_player_initialization(self):
        """Actual initialization logic, called after timer."""
        # Create QtMultimedia widgets (this takes ~300-3300ms depending on backend)
        self._video_output = QtMultimediaWidgets.QVideoWidget()
        self._audio_output = QtMultimedia.QAudioOutput()
        self._video_player = QtMultimedia.QMediaPlayer()

        # Connect widgets to player
        self._video_player.setVideoOutput(self._video_output)
        self._video_player.setAudioOutput(self._audio_output)

        # Connect player signals
        self._video_player.durationChanged.connect(self._on_duration_changed)
        self._video_player.positionChanged.connect(self._on_position_changed)
        self._video_player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Apply pending volume/mute state if set
        if self._pending_volume is not None:
            self._audio_output.setVolume(self._pending_volume)
            self._pending_volume = None
        if self._pending_mute is not None:
            self._audio_output.setMuted(self._pending_mute)
            self._pending_mute = None

        # Add video output to layout (insert after placeholder)
        placeholder_index = self.main_layout.indexOf(self.placeholder_label)
        self._video_output.setStyleSheet("background-color: #050607; border-radius: 14px;")
        self.main_layout.insertWidget(placeholder_index + 1, self._video_output, 1)

        self._player_initialized = True
        self._initializing = False

        # Emit signal instead of calling parent directly (decoupling)
        self.player_initialized.emit()

        callbacks = self._ready_callbacks[:]
        self._ready_callbacks.clear()
        for callback in callbacks:
            QtCore.QTimer.singleShot(0, callback)

    @property
    def player_ready(self) -> bool:
        return self._player_initialized and self._video_player is not None

    def ensure_player_ready(self, callback=None) -> bool:
        """Start lazy init if needed and optionally run a callback once ready."""
        if self.player_ready:
            if callback is not None:
                QtCore.QTimer.singleShot(0, callback)
            return True

        if callback is not None:
            self._ready_callbacks.append(callback)

        self._ensure_player_initialized()
        return False

    @property
    def video_player(self):
        """Current player instance or None while lazy init is still running."""
        return self._video_player

    @property
    def audio_output(self):
        """Current audio output instance or None while lazy init is still running."""
        return self._audio_output

    @property
    def video_output(self):
        """Current video output instance or None while lazy init is still running."""
        return self._video_output

    def set_volume(self, volume: float):
        """Set volume, storing pending value if audio output not yet created."""
        if self._player_initialized and self._audio_output is not None:
            self._audio_output.setVolume(volume)
        else:
            self._pending_volume = volume

    def set_muted(self, muted: bool):
        """Set mute state, storing pending value if audio output not yet created."""
        if self._player_initialized and self._audio_output is not None:
            self._audio_output.setMuted(muted)
        else:
            self._pending_mute = muted

    def _on_duration_changed(self, duration):
        self.slider.setRange(0, duration if duration > 0 else 0)

    def _on_position_changed(self, position):
        if not self._seeking:
            self.slider.blockSignals(True)
            self.slider.setValue(position)
            self.slider.blockSignals(False)

    def _on_media_status_changed(self, status):
        if (
            status == QtMultimedia.QMediaPlayer.MediaStatus.NoMedia
            or status == QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia
        ):
            self._show_placeholder_mode()
            self.slider.setEnabled(False)
            self.slider.setValue(0)
        else:
            self._show_playing_mode()
            if self.video_player.duration() > 0:
                self.slider.setEnabled(True)

    def _slider_pressed(self):
        self._seeking = True

    def _slider_released(self):
        self._seeking = False
        if self.video_player is not None:
            self.video_player.setPosition(self.slider.value())

    def _slider_value_changed(self, value):
        if self._seeking and self.video_player is not None:
            self.video_player.setPosition(value)

    def _slider_clicked(self, value):
        if self.video_player is not None:
            self.video_player.setPosition(value)

    def _seek(self, delta_ms):
        if not self.ensure_player_ready():
            return
        target = self.video_player.position() + delta_ms
        target = max(0, min(target, self.video_player.duration()))
        self.video_player.setPosition(target)

    def _show_playing_mode(self):
        self.placeholder_label.setVisible(False)
        if self._video_output:
            self._video_output.setVisible(True)

    def _show_placeholder_mode(self):
        self.placeholder_label.setVisible(True)
        if self._video_output:
            self._video_output.setVisible(False)

    def position_to_hms(self, ms):
        seconds = ms // 1000
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def mouseDoubleClickEvent(self, event):
        self.signal_double_click.emit()
        super().mouseDoubleClickEvent(event)


__all__ = ["CustomSlider", "PlayerWidget"]
