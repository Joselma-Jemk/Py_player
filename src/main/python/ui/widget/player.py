from PySide6 import QtCore, QtGui, QtWidgets, QtMultimediaWidgets, QtMultimedia
from pathlib import Path
import src.main.python.ui.widget.constant as constant


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

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.placeholder_label = QtWidgets.QLabel()

    def configure_widgets(self):
        self.slider.setEnabled(False)
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
                background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2196F3, stop:1 #2196F3);
                background: #2196F3;
                margin: 2px 0;
                border-radius: 2px;
            }
        """)

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

        # NOUVEAU SYSTÈME SLIDER — Tout est ici
        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)
        self.slider.valueChanged.connect(self._slider_value_changed)

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
        if status == QtMultimedia.QMediaPlayer.MediaStatus.NoMedia:
            self._show_placeholder_mode()
            self.slider.setEnabled(False)
        else:
            self._show_playing_mode()
            if self.video_player.duration() > 0:
                self.slider.setEnabled(True)

    # ===================================================================
    # NOUVEAU SYSTÈME DE SEEKING — ULTRA PRÉCIS, COMME VLC
    # ===================================================================
    def _slider_pressed(self):
        self._seeking = True

    def _slider_released(self):
        self._seeking = False
        # On applique la position finale une seule fois à la fin du drag
        self.video_player.setPosition(self.slider.value())

    def _slider_value_changed(self, value):
        # Pendant le drag, on met à jour en temps réel (fluide)
        if self._seeking:
            self.video_player.setPosition(value)

    def _seek(self, delta_ms):
        target = self.video_player.position() + delta_ms
        target = max(0, min(target, self.video_player.duration()))
        self.video_player.setPosition(target)
        # Le slider suivra automatiquement via _on_position_changed

    # ===================================================================
    # CLIC N'IMPORTE OÙ SUR LA BARRE → SAUT INSTANTANÉ ET PARFAIT
    # ===================================================================
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.slider.isEnabled():
            # On convertit le clic global en coordonnées locales du slider
            pos = self.slider.mapFromGlobal(event.globalPosition().toPoint())

            # On récupère le rectangle EXACT du groove (méthode officielle Qt)
            opt = QtWidgets.QStyleOptionSlider()
            self.slider.initStyleOption(opt)
            groove = self.slider.style().subControlRect(
                QtWidgets.QStyle.ComplexControl.CC_Slider,
                opt,
                QtWidgets.QStyle.SubControl.SC_SliderGroove,
                self.slider
            )

            # Zone de clic ultra généreuse (même si tu cliques 30px au-dessus ou en dessous)
            clickable = groove.adjusted(-40, -30, 40, 50)

            if clickable.contains(pos):
                if groove.width() > 0:
                    ratio = (pos.x() - groove.left()) / groove.width()
                    ratio = max(0.0, min(1.0, ratio))
                    new_pos = int(ratio * self.slider.maximum())

                    # On force le slider + le player immédiatement
                    self.slider.setValue(new_pos)
                    self.video_player.setPosition(new_pos)

                event.accept()
                return

        super().mousePressEvent(event)

    # ===================================================================
    # AFFICHAGE
    # ===================================================================
    def _show_playing_mode(self):
        self.placeholder_label.setVisible(False)
        self.video_output.setVisible(True)

    def _show_placeholder_mode(self):
        self.placeholder_label.setVisible(True)
        self.video_output.setVisible(False)

    def mouseDoubleClickEvent(self, event):
        self.signal_double_click.emit()
        super().mouseDoubleClickEvent(event)