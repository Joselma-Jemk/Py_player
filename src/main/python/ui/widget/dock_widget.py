from PySide6 import  QtGui, QtCore, QtWidgets
from pathlib import Path
import src.main.python.ui.widget.constant as constant

class DockWidget(QtWidgets.QDockWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.customize_self()
        self.icon_font_initialize()
        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()
        self.add_widgets_to_layouts()
        self.setup_connections()
        pass

    def customize_self(self):
        self.setWindowTitle("Playlist")
        pass

    def icon_font_initialize(self, size=15):
        dir = constant.find_path("material-symbols-outlined.ttf")
        font_id = QtGui.QFontDatabase.addApplicationFont(str(dir))
        self.icon_font = QtGui.QFont(QtGui.QFontDatabase.applicationFontFamilies(font_id)[0])
        self.icon_font.setPointSize(size)
        pass

    def create_widgets(self):
        self.playlist_widget = QtWidgets.QWidget()
        self.lstw = QtWidgets.QListWidget()
        self.btn_add_to_playlist = QtWidgets.QPushButton("\ue03b")
        self.btn_remove_to_playlist = QtWidgets.QPushButton("\ueb80")
        pass

    def modify_widgets(self):
        #btn
        for btn in [self.btn_add_to_playlist,self.btn_remove_to_playlist]:
            btn.setFont(self.icon_font)
            if btn.text() == "\ue03b":
                btn.setStyleSheet("color:green")
                btn.setToolTip("<b style='color:#f2f2f2;font-weight:bold;'>Ajoutez un fichiers à la playlist </b>")
                continue
            btn.setStyleSheet("color:red")
            btn.setToolTip("<b style='color:#f2f2f2;font-weight:bold;'> Retirer de la playlist</b>")

         #listwidget
        self.lstw.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ContiguousSelection)
        pass

    def create_layouts(self):
        self.playlist_widget.main_lyt = QtWidgets.QVBoxLayout(self.playlist_widget)
        self.playlist_widget.second_lyt = QtWidgets.QHBoxLayout()
        pass

    def add_widgets_to_layouts(self):
        self.playlist_widget.main_lyt.addWidget(self.lstw)
        for btn in [self.btn_add_to_playlist,self.btn_remove_to_playlist]:
            self.playlist_widget.second_lyt.addWidget(btn)
            self.playlist_widget.main_lyt.addLayout(self.playlist_widget.second_lyt)
            self.setWidget(self.playlist_widget)
        pass

    def setup_connections(self):
        pass


    pass