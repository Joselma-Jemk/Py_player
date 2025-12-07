from PySide6 import QtCore, QtGui, QtWidgets, QtMultimediaWidgets, QtMultimedia
from pathlib import Path
import src.main.python.ui.widget.constant as constant


class PlayerWidget(QtWidgets.QWidget):
    signal_double_click = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slider_pressed = False
        self.setup_ui()

    def setup_ui(self):
        self.create_widgets()
        self.configure_widgets()
        self.create_layout()
        self.setup_connections()

        # État initial : afficher seulement le placeholder
        self._show_placeholder_mode()

    def create_widgets(self):
        self.video_output = QtMultimediaWidgets.QVideoWidget()
        self.audio_output = QtMultimedia.QAudioOutput()
        self.video_player = QtMultimedia.QMediaPlayer()
        self.video_player.setVideoOutput(self.video_output)
        self.video_player.setAudioOutput(self.audio_output)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.placeholder_label = QtWidgets.QLabel()

    def configure_widgets(self):
        # Configuration du slider
        self.slider.setEnabled(True)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #e0e0e0;
                height: 4px;
                border-radius: 2px;
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: #f0f00f;
                width: 7px;
                height: 7px;
                border-radius: 7px;
                margin: -2px 0;
            }
            QSlider::sub-page:horizontal {
                background: #063231;
                margin: 2px 0;
                border-radius: 2px;
            }
        """)

        # Configuration du label placeholder
        icon_path = constant.py_player_icone(4) if hasattr(constant, 'py_player_icone') else ""
        if icon_path and Path(icon_path).exists():
            self.placeholder_label.setPixmap(QtGui.QPixmap(icon_path))
        self.placeholder_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet(f"background: {constant.PRINCIPAL_COLOR};")

    def create_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Ajouter tous les widgets
        self.main_layout.addWidget(self.placeholder_label)
        self.main_layout.addWidget(self.video_output)
        self.main_layout.addWidget(self.slider)

    def setup_connections(self):
        # Signaux du lecteur
        self.video_player.durationChanged.connect(self._on_duration_changed)
        self.video_player.positionChanged.connect(self._on_position_changed)
        self.video_player.playbackStateChanged.connect(self._on_playback_state_changed)

        # Signaux du slider
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.sliderMoved.connect(self._on_slider_moved)

        # Raccourcis clavier
        QtGui.QShortcut(QtCore.Qt.Key_Left, self,
                        lambda: self._seek_relative(-10000))
        QtGui.QShortcut(QtCore.Qt.Key_Right, self,
                        lambda: self._seek_relative(10000))

    def _on_duration_changed(self, duration):
        self.slider.setMaximum(duration)
        self.slider.setEnabled(duration > 0)

    def _on_position_changed(self, position):
        if not self.slider_pressed:
            self.slider.setValue(position)

    def _on_playback_state_changed(self, state):
        """Montre/cache les éléments selon l'état de lecture"""
        if state == QtMultimedia.QMediaPlayer.PlayingState:
            self._show_playing_mode()
        else:
            self._show_placeholder_mode()

    def _on_slider_pressed(self):
        self.slider_pressed = True

    def _on_slider_released(self):
        self.slider_pressed = False
        self.video_player.setPosition(self.slider.value())

    def _on_slider_moved(self, position):
        if self.slider_pressed:
            self.video_player.setPosition(position)

    def _seek_relative(self, delta_ms):
        new_position = self.video_player.position() + delta_ms
        new_position = max(0, min(new_position, self.video_player.duration()))
        self.video_player.setPosition(new_position)

    def _show_playing_mode(self):
        """Mode lecture : montre la vidéo et le slider"""
        self.placeholder_label.setVisible(False)
        self.video_output.setVisible(True)

    def _show_placeholder_mode(self):
        """Mode attente : montre seulement le placeholder"""
        self.placeholder_label.setVisible(True)
        self.video_output.setVisible(False)

    def mouseDoubleClickEvent(self, event):
        self.signal_double_click.emit()
        super().mouseDoubleClickEvent(event)