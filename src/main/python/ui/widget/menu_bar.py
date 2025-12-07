from PySide6 import QtCore, QtGui, QtWidgets
from pathlib import Path
import src.main.python.ui.widget.constant as constant


class MenuBarWidgets(QtWidgets.QMenuBar):
    def __init__(self, parent=None, ok: bool = False):
        super().__init__(parent)
        self.ok = ok
        self.setup_ui()
        self.setStyleSheet("""
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                border-left: 3px solid #00aaff;
            }
        """)

    def setup_ui(self):
        self.icon_font_initialize()
        self.create_menu()
        self.apply_palette()   # <-- Palette appliquée ici
        self.fileMenu_customize()
        self.playMenu_customize()
        self.playlistMenu_customize()
        self.helpMenu_customize()
        self.set_tool_tip(self.ok)
        self.setup_connection()

    def icon_font_initialize(self, size=15):
        font_path = constant.find_path("material-symbols-outlined.ttf", safe=True)
        if font_path and Path(font_path).exists():
            font_id = QtGui.QFontDatabase.addApplicationFont(str(font_path))
            self.icon_font = QtGui.QFont(QtGui.QFontDatabase.applicationFontFamilies(font_id)[0])
            self.icon_font.setPointSize(size)
        pass

    def create_menu(self):
        self.fileMenu = QtWidgets.QMenu("Fichier")
        self.playMenu = QtWidgets.QMenu("Lecture")
        self.playlistMenu = QtWidgets.QMenu("Playlist")
        self.helpMenu = QtWidgets.QMenu("Aide")
        pass

    # ------------------------------------------------------------
    # 🎨 APPLICATION DE LA PALETTE SUR TOUS LES MENUS
    # ------------------------------------------------------------
    def apply_palette(self):
        dark_bg = QtGui.QColor("#2c2c2e")
        dark_hover = QtGui.QColor("#3a3a3c")
        text_color = QtGui.QColor("#ffffff")

        def palette_for_menu(menu: QtWidgets.QMenu):
            pal = menu.palette()

            # Fond du menu
            pal.setColor(QtGui.QPalette.Window, dark_bg)
            pal.setColor(QtGui.QPalette.Base, dark_bg)

            # Texte
            pal.setColor(QtGui.QPalette.WindowText, text_color)
            pal.setColor(QtGui.QPalette.Text, text_color)
            pal.setColor(QtGui.QPalette.ButtonText, text_color)

            # Hover (zones actives)
            pal.setColor(QtGui.QPalette.Highlight, dark_hover)
            pal.setColor(QtGui.QPalette.HighlightedText, text_color)

            menu.setPalette(pal)
            menu.setAutoFillBackground(True)

        # Appliquer à tous les menus
        palette_for_menu(self.fileMenu)
        palette_for_menu(self.playMenu)
        palette_for_menu(self.playlistMenu)
        palette_for_menu(self.helpMenu)

        # La barre de menu elle-même
        bar_pal = self.palette()
        bar_pal.setColor(QtGui.QPalette.Window, dark_bg)
        bar_pal.setColor(QtGui.QPalette.Button, dark_bg)
        bar_pal.setColor(QtGui.QPalette.ButtonText, text_color)
        bar_pal.setColor(QtGui.QPalette.WindowText, text_color)
        self.setPalette(bar_pal)
        self.setAutoFillBackground(True)

    # ------------------------------------------------------------

    def fileMenu_customize(self):
        self.addMenu(self.fileMenu)

        self.act_open_file = self.fileMenu.addAction(
            QtGui.QIcon(constant.ICON_OPEN_FILE) if constant.ICON_OPEN_FILE else "",
            "Ouvrir un fichier  "
        )
        self.act_open_file.setShortcut("Ctrl+I")

        self.act_open_folder = self.fileMenu.addAction(
            QtGui.QIcon(constant.ICON_OPEN_FOLDER) if constant.ICON_OPEN_FOLDER else "",
            "Ouvrir un dossier  "
        )
        self.act_open_folder.setShortcut("Ctrl+D")

        self.act_app_exit = self.fileMenu.addAction(
            QtGui.QIcon(constant.ICON_EXIT) if constant.ICON_EXIT else "",
            "Quitter  "
        )
        self.act_app_exit.setShortcut("Ctrl+Q")
        self.addSeparator()
        pass

    def playMenu_customize(self):
        self.addMenu(self.playMenu)

        self.act_play = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_PLAY) if constant.ICON_PLAY else "",
            "Lire"
        )

        self.act_stop = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_STOP) if constant.ICON_STOP else "",
            "Stop"
        )

        self.act_skip_next = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_SKIP_NEXT) if constant.ICON_SKIP_NEXT else "",
            "Lire le suivant"
        )

        self.act_skip_previous = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_SKIP_PREVIOUS) if constant.ICON_SKIP_PREVIOUS else "",
            "Lire le précédent"
        )

        self.act_mute_mode = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_VOLUME_UP) if constant.ICON_VOLUME_UP else "",
            "Mute désactivé"
        )
        self.act_mute_mode.setCheckable(True)

        self.act_full_screen_mode = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_FULLSCREEN) if constant.ICON_FULLSCREEN else "",
            "Mode plein écran"
        )
        self.act_full_screen_mode.setCheckable(True)
        self.addSeparator()
        pass

    def playlistMenu_customize(self):
        self.addMenu(self.playlistMenu)

        self.act_show_playlist = self.playlistMenu.addAction(
            QtGui.QIcon(constant.ICON_PLAYLIST) if constant.ICON_PLAYLIST else "",
            "Voir la playlist  "
        )
        self.act_show_playlist.setShortcut("Ctrl+P")

        self.act_add_to_playlist = self.playlistMenu.addAction(
            QtGui.QIcon(constant.ICON_PLAYLIST_ADD) if constant.ICON_PLAYLIST_ADD else "",
            "Ajouter un fichier à la playlist  "
        )

        self.act_remove_to_playlist = self.playlistMenu.addAction(
            QtGui.QIcon(constant.ICON_PLAYLIST_REMOVE) if constant.ICON_PLAYLIST_REMOVE else "",
            "Supprimer de la playlist  "
        )
        pass

    def helpMenu_customize(self):
        self.addMenu(self.helpMenu)

        self.act_about = self.helpMenu.addAction(
            QtGui.QIcon(constant.ICON_INFOS) if constant.ICON_INFOS else "",
            "À propos  "
        )
        pass

    def set_tool_tip(self, ok: bool):
        if ok:
            self.fileMenu.setToolTip("Ouvrir des fichiers ou dossiers")
            self.playMenu.setToolTip("Lire des fichiers de la liste de lecture")
            self.playlistMenu.setToolTip("Voir, ajoutez ou supprimer des titres de vos liste de lecture")
            self.helpMenu.setToolTip("Obtenir de l'aide")
        pass

    def setup_connection(self):
        self.act_play.triggered.connect(self.play_pause_update)
        self.act_mute_mode.triggered.connect(self.mute_icon_update)
        pass

    def play_pause_update(self):
        if self.act_play.text() == "Lire":
            if constant.ICON_PAUSE:
                self.act_play.setIcon(QtGui.QIcon(constant.ICON_PAUSE))
            self.act_play.setToolTip("Pause")
            self.act_play.setText("Pause")
        else:
            if constant.ICON_PLAY:
                self.act_play.setIcon(QtGui.QIcon(constant.ICON_PLAY))
            self.act_play.setToolTip("Lire")
            self.act_play.setText("Lire")
        pass

    def mute_icon_update(self):
        if self.act_mute_mode.text() == "Mute désactivé":
            if constant.ICON_VOLUME_OFF:
                self.act_mute_mode.setIcon(QtGui.QIcon(constant.ICON_VOLUME_OFF))
            self.act_mute_mode.setToolTip("Mute activé")
            self.act_mute_mode.setText("Mute activé")
        else:
            if constant.ICON_VOLUME_UP:
                self.act_mute_mode.setIcon(QtGui.QIcon(constant.ICON_VOLUME_UP))
            self.act_mute_mode.setToolTip("Mute désactivé")
            self.act_mute_mode.setText("Mute désactivé")
        pass
