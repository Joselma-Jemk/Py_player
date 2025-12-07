from PySide6 import QtCore, QtGui, QtWidgets
import src.main.python.ui.widget.constant as constant
from src.main.python.ui.widget.menu_bar import MenuBarWidgets
from src.main.python.ui.widget.player import PlayerWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.icon_font = None
        self.setup_ui()

    def setup_ui(self):
        self.customize_self()
        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()
        self.add_widgets_to_layouts()
        self.setup_connections()
        pass

    def icon_font_initialize(self, size=15):
        dir = constant.find_path("material-symbols-outlined.ttf")
        font_id = QtGui.QFontDatabase.addApplicationFont(str(dir))
        self.icon_font = QtGui.QFont(QtGui.QFontDatabase.applicationFontFamilies(font_id)[0])
        self.icon_font.setPointSize(size)
        pass

    def customize_self(self):
        self.setWindowIcon(QtGui.QIcon(constant.icon_directory))
        self.setWindowTitle("PyPlayer")
        self.resize(1000, 600)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.setProperty("theme", "néon")
        self.setStyleSheet(f"background: {constant.SECONDARY_COLOR};")


        pass

    def create_widgets(self):
        self.player_widget = PlayerWidget()
        self.setCentralWidget(self.player_widget)
        self.menubar_widget = MenuBarWidgets(self)
        self.setMenuBar(self.menubar_widget)

        pass

    def modify_widgets(self):
        pass

    def create_layouts(self):
        pass

    def add_widgets_to_layouts(self):
        pass

    def setup_connections(self):
        pass

    pass
