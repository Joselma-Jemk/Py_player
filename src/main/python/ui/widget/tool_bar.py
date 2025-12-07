from PySide6 import QtCore, QtGui, QtWidgets
import src.main.python.ui.widget.constant as constant
from pathlib import Path

class VolumeWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.lbl = QtWidgets.QLabel()
        self.btn = QtWidgets.QPushButton()
        self.setup_ui()

    def setup_ui(self):
        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()
        self.setup_connections()

    def create_widgets(self):
        self.slider.setRange(0, 100)
        self.slider.setValue(20)
        self.lbl.setText("0")
        self.lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.btn.setFixedSize(40, 40)
        self.slider.setFixedWidth(150)
        self.btn.setIcon(QtGui.QIcon(constant.ICON_VOLUME_UP))
        self.btn.text = False

    def modify_widgets(self):
        self.setStyleSheet("""
            QWidget {
                background-color:#1c1c1e;
                border:none;
                }
            QLabel {
                background-color:#1c1c1e;
                border-right:#2c2c2e;
                }
        """)
        self.lbl.setStyleSheet("background-color: #2c2c2e;")
        self.btn.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Mode mute désactivé</b>")

    def create_layouts(self):
        self.lyt = QtWidgets.QHBoxLayout(self)
        self.lyt.addWidget(self.btn)
        self.lyt.addWidget(self.slider)
        self.lyt.addWidget(self.lbl)

    def setup_connections(self):
        self.btn.clicked.connect(self.mute_on_off)

    def volume_update(self):
        value = self.slider.value()
        if value < 60:
            self.lbl.setText(str(value))
            self.lbl.setStyleSheet(
                "background-color:#1c1c1e;color:white;font-size:12px;font-weight:bold;")
        elif value > 60 and value < 85:
            self.lbl.setText(str(value))
            self.lbl.setStyleSheet(
                "background-color:#1c1c1e;color:yellow;font-weight:bold;font-size:12px;")
        else:
            self.lbl.setText(str(value))
            self.lbl.setStyleSheet(
                "background-color:#1c1c1e;color:red;font-weight:bold;font-size:12px;")

    def volume_up_and_down(self, direction):
        value = self.slider.value()
        if direction == "+":
            self.slider.setValue(value + 2)
        else:
            self.slider.setValue(value - 2)

    def mute_on_off(self):
        if self.slider.isEnabled():
            self.btn.setIcon(QtGui.QIcon(constant.ICON_VOLUME_OFF))
            self.btn.text = True
            self.slider.setEnabled(False)
            self.btn.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Mode mute activé</b>")
        else:
            self.slider.setEnabled(True)
            self.btn.setIcon(QtGui.QIcon(constant.ICON_VOLUME_UP))
            self.btn.text = False
            self.btn.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Mode mute désactivé</b>")

class PlayerControlsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_font = None
        self.setup_ui()

    def setup_ui(self):
        self.icon_font_initialize()
        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()

    def icon_font_initialize(self, size=14):
        dir = constant.find_path("material-symbols-outlined.ttf")
        font_id = QtGui.QFontDatabase.addApplicationFont(str(dir))
        self.icon_font = QtGui.QFont(QtGui.QFontDatabase.applicationFontFamilies(font_id)[0])
        self.icon_font.setPointSize(size)

    def create_widgets(self):
        self.btn_play_pause = QtWidgets.QPushButton("\ue037")
        self.btn_stop = QtWidgets.QPushButton("\ue047")
        self.btn_skipnext = QtWidgets.QPushButton("\ue044")
        self.btn_skipprevious = QtWidgets.QPushButton("\ue045")
        self.btn_play_mode = QtWidgets.QPushButton("\ue043 ")
        self.btn_list = [self.btn_play_pause, self.btn_skipprevious, self.btn_stop, self.btn_skipnext,
                         self.btn_play_mode]

    def modify_widgets(self):
        for btn in self.btn_list:
            btn.setFont(self.icon_font)
            btn.setFixedSize(30, 30)

        # Remplacement: constant.PRINCIPAL_TEXT_COLOR = "#f2f2f7"
        self.btn_play_pause.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Lire</b>")
        self.btn_stop.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Stop</b>")
        self.btn_skipnext.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Lire le suivant</b>")
        self.btn_skipprevious.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Lire le précédent</b>")
        self.play_mode_tooltip()

    def create_layouts(self):
        self.lyt = QtWidgets.QHBoxLayout(self)
        for btn in self.btn_list:
            self.lyt.addWidget(btn)

    def btn_play_pause_update(self):
        if self.btn_play_pause.text() == "\ue037":
            self.btn_play_pause.setText("\ue034")
            self.btn_play_pause.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Pause</b>")
        else:
            self.btn_play_pause.setText("\ue037")
            self.btn_play_pause.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Lire</b>")

    def player_mode_update(self):
        if self.btn_play_mode.text() == "\ue043":
            self.btn_play_mode.setText("\ue040")
        elif self.btn_play_mode.text() == "\ue040":
            self.btn_play_mode.setText("\ue041")
        elif self.btn_play_mode.text() == "\ue041":
            self.btn_play_mode.setText("\ue14b")
        else:
            self.btn_play_mode.setText("\ue043")
        self.play_mode_tooltip()

    def play_mode_tooltip(self):
        # Remplacement: constant.PRINCIPAL_TEXT_COLOR = "#f2f2f7"
        if self.btn_play_mode.text() == "\ue040":
            self.btn_play_mode.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Lecture de la playlist</b>")
        elif self.btn_play_mode.text() == "\ue041":
            self.btn_play_mode.setToolTip(
                "<b style='color:#f2f2f7;font-weight:bold;'>Lecture en boucle du fichier actuelle</b>")
        elif self.btn_play_mode.text() == "\ue14b":
            self.btn_play_mode.setToolTip(
                "<b style='color:#f2f2f7;font-weight:bold;'>Lire une seul fois le fichier actuelle</b>")
        else:
            self.btn_play_mode.setToolTip(
                "<b style='color:#f2f2f7;font-weight:bold;'>Lecture aléatoire de la playlist</b>")

class TimeLabelWidget(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText(
            "<span style='color:#eaeaea;font-weight:bold'>00:00:00</span> / <span style='color:#7f7f7f;font-weight:bold'>00:00:00 </span>")
        self.setFixedWidth(200)
        self.setFixedHeight(40)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color:#1c1c1e;
                border-left: 1px solid #1c1c1e;
                border-right: 1px solid #1c1c1e;
            }
        """)

class PlaylistButtonWidget(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__("\ue0ee", parent)
        self.setFixedSize(40, 40)
        self.setStyleSheet("border-left:1px solid #3a3a3c;")
        self.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Voir la playlist</b>")

class ToolBarWidget(QtWidgets.QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setup_ui()

    def setup_ui(self):
        self.create_widgets()
        self.setup_connections()
        self.add_widgets_to_toolbar()

    def create_widgets(self):
        self.player_controls = PlayerControlsWidget()
        self.time_label = TimeLabelWidget()
        self.volume_widget = VolumeWidget()
        self.playlist_button = PlaylistButtonWidget()

        # Set icon font for playlist button
        if self.player_controls.icon_font:
            self.playlist_button.setFont(self.player_controls.icon_font)

    def setup_connections(self):
        self.volume_widget.slider.valueChanged.connect(self.volume_widget.volume_update)

        # Setup shortcuts
        QtGui.QShortcut(QtCore.Qt.Key.Key_VolumeMute, self.volume_widget, self.volume_widget.mute_on_off)

        shorcut_1 = QtGui.QShortcut(QtCore.Qt.Key.Key_Up, self.volume_widget,
                                    lambda: self.volume_widget.volume_up_and_down("+"))
        shorcut_2 = QtGui.QShortcut(QtCore.Qt.Key.Key_Down, self.volume_widget,
                                    lambda: self.volume_widget.volume_up_and_down("-"))

        QtGui.QShortcut(QtCore.Qt.Key.Key_Space, self.volume_widget,
                        self.player_controls.btn_play_pause.clicked.emit)
        QtGui.QShortcut(QtCore.Qt.Key.Key_VolumeMute, self.volume_widget,
                        self.volume_widget.btn.clicked.emit)

        # Connect player controls
        self.player_controls.btn_play_pause.clicked.connect(self.player_controls.btn_play_pause_update)
        self.player_controls.btn_play_mode.clicked.connect(self.player_controls.player_mode_update)

    def add_widgets_to_toolbar(self):
        self.addWidget(self.player_controls)
        self.addWidget(self.time_label)
        self.addWidget(self.volume_widget)
        self.addWidget(self.playlist_button)

    def volume_update(self):
        if self.volume_widget.slider.value():
            self.volume_widget.volume_update()

    pass