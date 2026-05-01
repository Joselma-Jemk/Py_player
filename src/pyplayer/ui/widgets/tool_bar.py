from PySide6 import QtCore, QtGui, QtWidgets

from src.pyplayer.ui.theme import (
    ACCENT_COLOR,
    HOVER_COLOR,
    OK_ONE_COLOR,
    PRESSED_COLOR,
    PRINCIPAL_COLOR,
    PRINCIPAL_TEXT_COLOR,
    SECONDARY_COLOR,
    THIRD_COLOR,
)
from src.pyplayer.infrastructure.filesystem import find_path
from src.pyplayer.domain.playlist import PlayMode


class VolumeWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(300)
        self.setMinimumHeight(52)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.lbl = QtWidgets.QLabel()
        self.btn = QtWidgets.QPushButton("\ue050")
        self.setup_ui()

    def setup_ui(self):
        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()
        self.setup_connections()

    def create_widgets(self):
        self.slider.setRange(0, 100)
        self.slider.setValue(20)
        self.slider.setFixedWidth(150)

        self.lbl.setText("20")
        self.lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl.setFixedWidth(25)

        self.btn.setFixedSize(40, 40)
        self.btn.setCheckable(True)
        self.mute_state = False

    def modify_widgets(self):
        self.setStyleSheet(
            """
            QWidget {
                background: transparent;
            }
            """
        )
        self.lbl.setStyleSheet(
            """
            QLabel {
                background-color: transparent;
                color: #f5f7fa;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
                margin: 0;
                border: none;
            }
        """
        )

        self.slider.setStyleSheet(
            """
            QSlider::groove:horizontal {
                background-color: rgba(77, 84, 92, 0.55);
                border: none;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::sub-page:horizontal {
                background-color: #4CAF50;
                border: none;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background-color: #f5f7fa;
                border: 2px solid #62d66b;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 8px;
            }

            QSlider::add-page:horizontal {
                background-color: rgba(77, 84, 92, 0.35);
                border: none;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal:hover {
                background-color: white;
                border: 2px solid #8CF095;
            }

            QSlider::groove:horizontal:disabled {
                background-color: rgba(70, 70, 70, 0.6);
            }

            QSlider::sub-page:horizontal:disabled {
                background-color: rgba(76, 175, 80, 0.2);
                border: 1px solid rgba(76, 175, 80, 0.1);
            }

            QSlider::handle:horizontal:disabled {
                background-color: rgba(180, 180, 180, 0.7);
                border: 2px solid rgba(140, 140, 140, 0.5);
            }
            """
        )

        self.btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(54, 58, 63, 0.9);
                border: 1px solid rgba(92, 98, 105, 0.75);
                border-radius: 10px;
                padding: 4px 0px;
                color: #4CAF50;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.18);
                border: 1px solid rgba(118, 232, 128, 0.85);
                color: #dfffe0;
            }
            QPushButton:pressed {
                background-color: rgba(52, 143, 60, 0.9);
                border: 1px solid #2d7c35;
                color: white;
            }
            QPushButton:checked {
                color: #FF5252;
                background-color: rgba(255, 82, 82, 0.15);
                border: 1px solid rgba(255, 82, 82, 0.3);
            }
        """
        )

        self.btn.setToolTip("Mode mute désactivé")

    def create_layouts(self):
        self.lyt = QtWidgets.QHBoxLayout(self)
        self.lyt.setContentsMargins(12, 6, 12, 6)
        self.lyt.setSpacing(12)
        self.lyt.addWidget(self.btn)
        self.lyt.addWidget(self.slider)
        self.lyt.addWidget(self.lbl)

    def setup_connections(self):
        self.btn.clicked.connect(self.mute_on_off)
        self.slider.valueChanged.connect(self.volume_update)

    def volume_update(self):
        value = self.slider.value()
        self.lbl.setText(str(value))

        if value == 0:
            self.lbl.setStyleSheet(
                """
                QLabel {
                    background-color: transparent;
                    color: #888;
                    font-size: 13px;
                    font-weight: bold;
                }
            """
            )
        elif value < 60:
            self.lbl.setStyleSheet(
                """
                QLabel {
                    background-color: transparent;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                }
            """
            )
        elif value < 85:
            self.lbl.setStyleSheet(
                """
                QLabel {
                    background-color: transparent;
                    color: #FFC107;
                    font-size: 13px;
                    font-weight: bold;
                }
            """
            )
        else:
            self.lbl.setStyleSheet(
                """
                QLabel {
                    background-color: transparent;
                    color: #F44336;
                    font-size: 13px;
                    font-weight: bold;
                }
            """
            )

        self.update_button_icon()

    def update_button_icon(self):
        if self.mute_state:
            self.btn.setText("\ue04f")
        else:
            value = self.slider.value()
            if value == 0:
                self.btn.setText("\ue04f")
            elif value < 33:
                self.btn.setText("\ue04e")
            elif value < 66:
                self.btn.setText("\ue04d")
            else:
                self.btn.setText("\ue050")

    def volume_up_and_down(self, direction):
        value = self.slider.value()
        if direction == "+":
            new_value = min(value + 2, 100)
        else:
            new_value = max(value - 2, 0)
        self.slider.setValue(new_value)

    def mute_on_off(self):
        self.mute_state = not self.mute_state

        if self.mute_state:
            self.slider.setEnabled(False)
            self.btn.setChecked(True)
            self.btn.setToolTip("Mode mute activé")
        else:
            self.slider.setEnabled(True)
            self.btn.setChecked(False)
            self.btn.setToolTip("Mode mute désactivé")

        self.update_button_icon()


class PlayerControlsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_font = None
        self._play_mode = PlayMode.NORMAL
        self.last_pressed_button = None
        self.setup_ui()

    def setup_ui(self):
        self.icon_font_initialize()
        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()
        self.setup_connections()

    def icon_font_initialize(self, size=14):
        from src.pyplayer.ui.theme.fonts import get_icon_font
        self.icon_font = get_icon_font(size)

    def create_widgets(self):
        self.btn_play_pause = QtWidgets.QPushButton("\ue037")
        self.btn_stop = QtWidgets.QPushButton("\ue047")
        self.btn_skipnext = QtWidgets.QPushButton("\ue044")
        self.btn_skipprevious = QtWidgets.QPushButton("\ue045")
        self.btn_play_mode = QtWidgets.QPushButton()
        self.btn_list = [
            self.btn_play_pause,
            self.btn_skipprevious,
            self.btn_stop,
            self.btn_skipnext,
            self.btn_play_mode,
        ]

    def modify_widgets(self):
        base_style = """
            QPushButton {
                background-color: rgba(49, 53, 58, 0.94);
                border: 1px solid rgba(84, 92, 99, 0.85);
                border-radius: 11px;
                color: #f3f5f7;
                font-size: 16px;
                padding: 0px;
                margin: 0px;
                qproperty-alignment: Qt.AlignCenter;
                min-width: 40px;
                min-height: 40px;
            }

            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.24);
                border: 1px solid rgba(118, 232, 128, 0.95);
                color: white;
            }

            QPushButton:pressed {
                background-color: rgba(62, 154, 70, 0.95);
                border: 1px solid #2c7a33;
                color: white;
            }

            QPushButton:disabled {
                color: #666666;
                background-color: rgba(50, 50, 55, 0.5);
                border: 1px solid rgba(80, 80, 85, 0.3);
            }
        """

        active_style = """
            QPushButton {
                background-color: rgba(76, 175, 80, 0.16);
                border: 1px solid rgba(118, 232, 128, 0.95);
                color: #f4fff4;
                border-radius: 11px;
                font-size: 16px;
                padding: 0px;
                margin: 0px;
                qproperty-alignment: Qt.AlignCenter;
                min-width: 40px;
                min-height: 40px;
            }

            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.32);
                border: 1px solid #8CF095;
                color: white;
            }

            QPushButton:pressed {
                background-color: rgba(62, 154, 70, 0.95);
                border: 1px solid #2E7D32;
                color: white;
            }
        """

        for btn in self.btn_list:
            btn.setFont(self.icon_font)
            btn.setFixedSize(40, 40)
            btn.setStyleSheet(base_style)
            btn.base_style = base_style
            btn.active_style = active_style

        self.last_pressed_button = self.btn_play_pause
        self.btn_play_pause.setStyleSheet(active_style)

        self.btn_play_pause.setToolTip(
            "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
            "<b style='color:#4CAF50; font-size: 12px;'>Lire</b>"
            "</div>"
        )
        self.btn_stop.setToolTip(
            "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
            "<b style='color:#4CAF50; font-size: 12px;'>Stop</b>"
            "</div>"
        )
        self.btn_skipnext.setToolTip(
            "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
            "<b style='color:#4CAF50; font-size: 12px;'>Lire le suivant</b>"
            "</div>"
        )
        self.btn_skipprevious.setToolTip(
            "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
            "<b style='color:#4CAF50; font-size: 12px;'>Lire le précédent</b>"
            "</div>"
        )
        self.play_mode_tooltip()
        self.btn_play_mode_init()

    def setup_connections(self):
        self.btn_play_pause.clicked.connect(lambda: self.set_active_button(self.btn_play_pause))
        self.btn_stop.clicked.connect(lambda: self.set_active_button(self.btn_stop))
        self.btn_skipnext.clicked.connect(lambda: self.set_active_button(self.btn_skipnext))
        self.btn_skipprevious.clicked.connect(lambda: self.set_active_button(self.btn_skipprevious))
        self.btn_play_mode.clicked.connect(lambda: self.set_active_button(self.btn_play_mode))
        self.btn_play_pause.clicked.connect(self.btn_play_pause_tooltip)

    def set_active_button(self, button):
        if self.last_pressed_button:
            self.last_pressed_button.setStyleSheet(self.last_pressed_button.base_style)

        button.setStyleSheet(button.active_style)
        self.last_pressed_button = button
        self.animate_button_press(button)

    def animate_button_press(self, button):
        original_size = button.size()
        animation = QtCore.QPropertyAnimation(button, b"geometry")
        animation.setDuration(150)
        animation.setStartValue(button.geometry())

        small_rect = QtCore.QRect(
            button.x() + 1,
            button.y() + 1,
            original_size.width() - 2,
            original_size.height() - 2,
        )
        animation.setKeyValueAt(0.5, small_rect)
        animation.setEndValue(button.geometry())
        animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        animation.start()

    def create_layouts(self):
        self.lyt = QtWidgets.QHBoxLayout(self)
        self.lyt.setContentsMargins(10, 8, 10, 8)
        self.lyt.setSpacing(10)
        for btn in self.btn_list:
            self.lyt.addWidget(btn)

    @property
    def play_mode(self):
        return self._play_mode

    @play_mode.setter
    def play_mode(self, value):
        self._play_mode = value

    def btn_play_pause_tooltip(self):
        if self.btn_play_pause.text() == "\ue037":
            self.btn_play_pause.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Pause</b>"
                "</div>"
            )
        else:
            self.btn_play_pause.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Lire</b>"
                "</div>"
            )
        self.set_active_button(self.btn_play_pause)

    def btn_play_mode_init(self):
        if self.play_mode == PlayMode.NORMAL:
            self.btn_play_mode.setText("\ue14b")
        elif self.play_mode == PlayMode.LOOP_ONE:
            self.btn_play_mode.setText("\ue041")
        elif self.play_mode == PlayMode.LOOP_ALL:
            self.btn_play_mode.setText("\ue040")
        else:
            self.btn_play_mode.setText("\ue043")
        self.play_mode_tooltip()

    def player_mode_update(self):
        if self.play_mode == PlayMode.NORMAL:
            self.btn_play_mode.setText("\ue041")
        elif self.play_mode == PlayMode.LOOP_ONE:
            self.btn_play_mode.setText("\ue040")
        elif self.play_mode == PlayMode.LOOP_ALL:
            self.btn_play_mode.setText("\ue043")
        else:
            self.btn_play_mode.setText("\ue14b")
        self.play_mode_tooltip()

    def play_mode_tooltip(self):
        if self.btn_play_mode.text() == "\ue040":
            self.btn_play_mode.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Boucler sur toute la playlist</b>"
                "</div>"
            )
            self.play_mode = PlayMode.LOOP_ALL
        elif self.btn_play_mode.text() == "\ue041":
            self.btn_play_mode.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Boucler sur la vidéo actuelle</b>"
                "</div>"
            )
            self.play_mode = PlayMode.LOOP_ONE
        elif self.btn_play_mode.text() == "\ue14b":
            self.btn_play_mode.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Lire la playlist une seule fois</b>"
                "</div>"
            )
            self.play_mode = PlayMode.NORMAL
        else:
            self.btn_play_mode.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Lecture aléatoire en boucle</b>"
                "</div>"
            )
            self.play_mode = PlayMode.SHUFFLE


class TimeLabelWidget(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_time = "00:00:00"
        self.total_time = "00:00:00"
        self.update_display()
        self.setFixedHeight(44)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            """
            QLabel {
                background-color: rgba(27, 30, 34, 0.88);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 12px;
                padding: 0 14px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """
        )

    def update_display(self):
        self.setText(
            f"<span style='color:#eaeaea;font-weight:bold;font-size:13px;'>{self.current_time}</span>"
            f"<span style='color:#4CAF50;font-weight:bold;font-size:15px;'> | </span>"
            f"<span style='color:#7f7f7f;font-weight:bold;font-size:13px;'>{self.total_time}</span>"
        )

    def set_times(self, current_time=None, total_time=None):
        if current_time:
            self.current_time = current_time
        if total_time:
            self.total_time = total_time
        self.update_display()


class PlaylistButtonWidget(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__("\ue0ee", parent)
        self.setFixedSize(46, 46)
        buttons_style = """
            QPushButton {
                background-color: rgba(35, 39, 43, 0.94);
                border: 1px solid rgba(118, 232, 128, 0.75);
                border-radius: 12px;
                color: #4CAF50;
                font-size: 18px;
                padding: 10px;
            }

            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.24);
                color: white;
            }

            QPushButton:pressed {
                background-color: #2E7D32;
                border-color: #2E7D32;
                color: white;
            }
        """
        self.setStyleSheet(buttons_style)
        self.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Masquer le panneau des playlists</b>")


class ToolBarWidget(QtWidgets.QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setup_ui()

    def setup_ui(self):
        self.create_widgets()
        self.setup_connections()
        self.add_widgets_to_toolbar()

    def create_widgets(self):
        self.player_controls = PlayerControlsWidget()
        self.time_label = TimeLabelWidget()
        self.volume_widget = VolumeWidget()
        self.btn_playlist = PlaylistButtonWidget()

        self.left_container = QtWidgets.QWidget()
        self.right_container = QtWidgets.QWidget()

        self.left_layout = QtWidgets.QHBoxLayout(self.left_container)
        self.right_layout = QtWidgets.QHBoxLayout(self.right_container)

        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(14)
        self.right_layout.setSpacing(14)

        self.setStyleSheet(
            """
            QToolBar {
                background-color: rgba(24, 26, 29, 0.98);
                border-top: 1px solid rgba(255,255,255,0.05);
                spacing: 0px;
                padding: 6px 10px;
            }
            """
        )
        self.left_container.setStyleSheet(
            """
            QWidget {
                background-color: transparent;
            }
            """
        )
        self.right_container.setStyleSheet(
            """
            QWidget {
                background-color: transparent;
            }
            """
        )

        if self.player_controls.icon_font:
            self.btn_playlist.setFont(self.player_controls.icon_font)

    def setup_connections(self):
        self.volume_widget.slider.valueChanged.connect(self.volume_widget.volume_update)

        QtGui.QShortcut(QtCore.Qt.Key.Key_VolumeMute, self.volume_widget, self.volume_widget.mute_on_off)

        QtGui.QShortcut(
            QtCore.Qt.Key.Key_Up,
            self.volume_widget,
            lambda: self.volume_widget.volume_up_and_down("+"),
        )
        QtGui.QShortcut(
            QtCore.Qt.Key.Key_Down,
            self.volume_widget,
            lambda: self.volume_widget.volume_up_and_down("-"),
        )

        QtGui.QShortcut(
            QtCore.Qt.Key.Key_Space,
            self.volume_widget,
            self.player_controls.btn_play_pause.clicked.emit,
        )
        QtGui.QShortcut(
            QtCore.Qt.Key.Key_VolumeMute,
            self.volume_widget,
            self.volume_widget.btn.clicked.emit,
        )

        self.player_controls.btn_play_mode.clicked.connect(self.player_controls.player_mode_update)

    def add_widgets_to_toolbar(self):
        self.left_layout.addWidget(self.player_controls)
        self.left_layout.addWidget(self.time_label)
        self.left_layout.addStretch()

        self.right_layout.addStretch()
        self.right_layout.addWidget(self.volume_widget)
        self.right_layout.addWidget(self.btn_playlist)

        self.addWidget(self.left_container)

        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.addWidget(self.right_container)

    def volume_update(self):
        if self.volume_widget.slider.value():
            self.volume_widget.volume_update()


__all__ = [
    "PlayerControlsWidget",
    "PlaylistButtonWidget",
    "TimeLabelWidget",
    "ToolBarWidget",
    "VolumeWidget",
]
