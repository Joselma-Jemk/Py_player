from PySide6 import QtGui, QtCore, QtWidgets
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
        #self.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setMinimumWidth(250)
        pass

    def icon_font_initialize(self, size=14):
        dir = constant.find_path("material-symbols-outlined.ttf")
        font_id = QtGui.QFontDatabase.addApplicationFont(str(dir))
        self.icon_font = QtGui.QFont(QtGui.QFontDatabase.applicationFontFamilies(font_id)[0])
        self.icon_font.setPointSize(size)
        pass

    def create_widgets(self):
        # Widget principal
        self.main_widget = QtWidgets.QWidget()

        # TabWidget
        self.tab_widget = QtWidgets.QTabWidget()

        # Onglet 1 : Liste de lecture
        self.tab_current = QtWidgets.QWidget()
        self.lstw = QtWidgets.QListWidget()

        # Boutons pour l'onglet 1
        self.btn_add_to_playlist = QtWidgets.QPushButton("\ue03b")
        self.btn_remove_to_playlist = QtWidgets.QPushButton("\ueb80")

        # Onglet 2 : Archives
        self.tab_archive = QtWidgets.QWidget()
        self.lstw_archive = QtWidgets.QListWidget()

        # Boutons pour l'onglet 2
        self.btn_save_playlist = QtWidgets.QPushButton("\ueb60")
        self.btn_upload_playlist = QtWidgets.QPushButton("\uf09b")
        pass

    def modify_widgets(self):
        # Style général du tabWidget
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            QTabBar::tab {
                background-color: rgba(40, 40, 40, 0.8);
                color: #b0b0b0;
                padding: 8px 16px;
                margin-right: 1px;
                border: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }
            QTabBar::tab:selected {
                background-color: rgba(50, 50, 50, 0.95);
                color: #ffffff;
                border-bottom: 2px solid #4CAF50;
            }
            QTabBar::tab:hover {
                background-color: rgba(60, 60, 60, 0.9);
                color: #ffffff;
            }
            QTabBar {
                background-color: transparent;
                border: none;
            }
        """)

        # Style des ListWidgets - Professionnel et épuré
        list_style = """
            QListWidget {
                background-color: rgba(30, 30, 30, 0.7);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                outline: none;
                padding: 2px;
            }
            QListWidget::item {
                padding: 10px 12px;
                margin: 1px 0;
                border-radius: 3px;
                border: none;
                background-color: transparent;
                border-left: 3px solid transparent;
            }
            QListWidget::item:nth-child(even) {
                background-color: rgba(255, 255, 255, 0.03);
            }
            QListWidget::item:nth-child(odd) {
                background-color: rgba(255, 255, 255, 0.01);
            }
            QListWidget::item:selected {
                background-color: rgba(76, 175, 80, 0.15);
                color: #ffffff;
                border-left: 3px solid #4CAF50;
                font-weight: 500;
            }
            QListWidget::item:hover:!selected {
                background-color: rgba(255, 255, 255, 0.07);
                border-left: 3px solid rgba(255, 255, 255, 0.2);
            }
            QScrollBar:vertical {
                background-color: rgba(40, 40, 40, 0.5);
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(100, 100, 100, 0.7);
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(120, 120, 120, 0.9);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        self.lstw.setStyleSheet(list_style)
        self.lstw_archive.setStyleSheet(list_style)

        # Style de base pour les boutons
        button_base_style = """
            QPushButton {
                background-color: rgba(50, 50, 50, 0.8);
                border: 1px solid rgba(70, 70, 70, 0.8);
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 18px;
                font-weight: 500;
                letter-spacing: 0.3px;
                margin: 2px 0;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 0.9);
                border: 1px solid rgba(90, 90, 90, 0.9);
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                background-color: rgba(40, 40, 40, 0.9);
                transform: translateY(0px);
            }
        """

        # Configuration spécifique des boutons
        buttons_config = [
            (self.btn_add_to_playlist, "#4CAF50", "Ajouter un fichier", "#4CAF50", "rgba(76, 175, 80, 0.1)"),
            (self.btn_remove_to_playlist, "#FF5252", "Retirer sélection", "#FF5252", "rgba(255, 82, 82, 0.1)"),
            (self.btn_save_playlist, "#2196F3", "Sauvegarder playlist", "#2196F3", "rgba(33, 150, 243, 0.1)"),
            (self.btn_upload_playlist, "#9C27B0", "Importer playlist", "#9C27B0", "rgba(156, 39, 176, 0.1)")
        ]

        for btn, color, tooltip, hover_color, hover_bg in buttons_config:
            btn.setFont(self.icon_font)
            btn.setStyleSheet(f"""
                {button_base_style}
                QPushButton {{
                    color: {color};
                }}
                QPushButton:hover {{
                    color: {hover_color};
                    border-color: {color};
                    background-color: {hover_bg};
                }}
            """)
            btn.setToolTip(
                f"<div style='background-color: rgba(40,40,40,0.95); padding: 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.1);'><b style='color:#ffffff; font-size: 12px;'>{tooltip}</b></div>")

        # Configuration des listes
        self.lstw.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lstw_archive.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

        # Noms des onglets
        self.tab_widget.addTab(self.tab_current, "Playlist Active")
        self.tab_widget.addTab(self.tab_archive, "Archives")
        pass

    def create_layouts(self):
        # Layout principal
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(3, 0, 3, 3)
        self.main_layout.setSpacing(0)

        # Layout pour l'onglet 1 (liste + boutons)
        self.tab_current_layout = QtWidgets.QVBoxLayout(self.tab_current)
        self.tab_current_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_current_layout.setSpacing(5)

        # Layout horizontal pour les boutons de l'onglet 1
        self.current_buttons_layout = QtWidgets.QHBoxLayout()
        self.current_buttons_layout.setSpacing(5)

        # Layout pour l'onglet 2 (liste + boutons)
        self.tab_archive_layout = QtWidgets.QVBoxLayout(self.tab_archive)
        self.tab_archive_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_archive_layout.setSpacing(5)

        # Layout horizontal pour les boutons de l'onglet 2
        self.archive_buttons_layout = QtWidgets.QHBoxLayout()
        self.archive_buttons_layout.setSpacing(5)
        pass

    def add_widgets_to_layouts(self):
        # Ajouter le tabWidget
        self.main_layout.addWidget(self.tab_widget)

        # Configuration de l'onglet 1
        self.tab_current_layout.addWidget(self.lstw, 1)  # La liste prend tout l'espace disponible

        # Créer un layout vertical pour centrer les boutons
        current_buttons_vbox = QtWidgets.QVBoxLayout()

        # Ajouter les boutons horizontalement au centre
        current_buttons_vbox.addLayout(self.current_buttons_layout)

        # Ajouter ce layout vertical à l'onglet
        self.tab_current_layout.addLayout(current_buttons_vbox)

        # Ajouter les boutons au layout horizontal
        self.current_buttons_layout.addWidget(self.btn_add_to_playlist)
        self.current_buttons_layout.addWidget(self.btn_remove_to_playlist)

        # Configuration de l'onglet 2
        self.tab_archive_layout.addWidget(self.lstw_archive, 1)  # La liste prend tout l'espace disponible

        # Créer un layout vertical pour centrer les boutons
        archive_buttons_vbox = QtWidgets.QVBoxLayout()

        # Ajouter les boutons horizontalement au centre
        archive_buttons_vbox.addLayout(self.archive_buttons_layout)

        # Ajouter ce layout vertical à l'onglet
        self.tab_archive_layout.addLayout(archive_buttons_vbox)

        # Ajouter les boutons au layout horizontal
        self.archive_buttons_layout.addWidget(self.btn_save_playlist)
        self.archive_buttons_layout.addWidget(self.btn_upload_playlist)

        # Définir le widget principal du dock
        self.setWidget(self.main_widget)
        pass

    def setup_connections(self):
        # Vous pouvez ajouter vos connections ici
        pass