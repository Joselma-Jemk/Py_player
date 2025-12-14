from PySide6 import QtCore, QtGui, QtWidgets, QtMultimediaWidgets, QtMultimedia
from pathlib import Path
import src.main.python.ui.widget.constant as constant


class CustomSlider(QtWidgets.QSlider):
    """Slider personnalisé avec click direct sur la position"""

    # Signal personnalisé pour la position cliquée
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

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Gère le clic sur le slider pour aller directement à la position"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Obtenir la position relative du clic dans le slider
            pos = event.position().x()

            # Calculer la valeur correspondante
            if self.width() > 0:
                value = (self.maximum() - self.minimum()) * pos / self.width() + self.minimum()
                value = max(self.minimum(), min(self.maximum(), int(value)))

                # Émettre le signal avec la valeur calculée
                self.sliderClicked.emit(int(value))

                # Mettre à jour la position du slider
                self.setValue(int(value))
                # Ne pas émettre valueChanged ici - il sera émis automatiquement par setValue()

        # Appeler la méthode parente pour garder le comportement normal
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Gère le déplacement avec clic maintenu"""
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._seeking = False
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
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.setMinimumWidth(650)
        self.setMinimumHeight(400)

    def create_widgets(self):
        self.video_output = QtMultimediaWidgets.QVideoWidget()
        self.audio_output = QtMultimedia.QAudioOutput()
        self.video_player = QtMultimedia.QMediaPlayer()
        self.video_player.setVideoOutput(self.video_output)
        self.video_player.setAudioOutput(self.audio_output)

        # Utilisation du CustomSlider au lieu de QSlider
        self.slider = CustomSlider(QtCore.Qt.Orientation.Horizontal)
        self.placeholder_label = QtWidgets.QLabel()

    def configure_widgets(self):
        self.slider.setEnabled(False)

        icon_path = constant.py_player_icone(4) if hasattr(constant, 'py_player_icone') else ""
        if icon_path and Path(icon_path).exists():
            self.placeholder_label.setPixmap(QtGui.QPixmap(icon_path))
        self.placeholder_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet(f"background: {constant.PRINCIPAL_COLOR};")

    def create_layout(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 3, 0, 3)
        self.main_layout.setSpacing(0)

        self.main_layout.addWidget(self.placeholder_label)
        self.main_layout.addWidget(self.video_output)
        self.main_layout.addWidget(self.slider)

    def setup_connections(self):
        self.video_player.durationChanged.connect(self._on_duration_changed)
        self.video_player.positionChanged.connect(self._on_position_changed)
        self.video_player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Connexions simplifiées grâce au CustomSlider
        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)
        self.slider.valueChanged.connect(self._slider_value_changed)
        self.slider.sliderClicked.connect(self._slider_clicked)

        QtGui.QShortcut(QtCore.Qt.Key.Key_Left, self, lambda: self._seek(-10000))
        QtGui.QShortcut(QtCore.Qt.Key.Key_Right, self, lambda: self._seek(10000))

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
        if status == QtMultimedia.QMediaPlayer.MediaStatus.NoMedia or status == QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia:
            self._show_placeholder_mode()
            self.slider.setEnabled(False)
            self.slider.setValue(0)
        else:
            self._show_playing_mode()
            if self.video_player.duration() > 0:
                self.slider.setEnabled(True)

    # ===================================================================
    # GESTION SLIDER SIMPLIFIÉE
    # ===================================================================
    def _slider_pressed(self):
        self._seeking = True

    def _slider_released(self):
        self._seeking = False
        # On applique la position finale une seule fois à la fin du drag
        self.video_player.setPosition(self.slider.value())

    def _slider_value_changed(self, value):
        # NE mettre à jour le lecteur QUE pendant le drag (quand _seeking est True)
        # Pas pour les changements normaux venant du lecteur
        if self._seeking:
            self.video_player.setPosition(value)

    def _slider_clicked(self, value):
        """Appelé quand on clique n'importe où sur le slider"""
        self.video_player.setPosition(value)

    def _seek(self, delta_ms):
        target = self.video_player.position() + delta_ms
        target = max(0, min(target, self.video_player.duration()))
        self.video_player.setPosition(target)
        # Le slider suivra automatiquement via _on_position_changed

    # ===================================================================
    # AFFICHAGE
    # ===================================================================
    def _show_playing_mode(self):
        self.placeholder_label.setVisible(False)
        self.video_output.setVisible(True)

    def _show_placeholder_mode(self):
        self.placeholder_label.setVisible(True)
        self.video_output.setVisible(False)

    def position_to_hms(self, ms):
        seconds = ms // 1000
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def mouseDoubleClickEvent(self, event):
        self.signal_double_click.emit()
        super().mouseDoubleClickEvent(event)