from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia
from pathlib import Path
import src.main.python.ui.widget.constant as constant

class MenuBarWidget(QtWidgets.QMenuBar):

    def __init__(self, parent=None, ok: bool = False):
        super().__init__(parent)
        self.ok = ok
        self.setup_ui()
        # Le style est maintenant géré entièrement dans customize_self

    def setup_ui(self):
        self.icon_font_initialize()
        self.customize_self()
        self.create_menu()
        self.apply_palette()
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

    def customize_self(self):
        self.setMinimumHeight(28)
        self.setStyleSheet(f"""
            /* =========================================== */
            /* BARRE DE MENU PRINCIPALE - THÈME VERT */
            /* =========================================== */

            QMenuBar {{
                background-color: {constant.PRINCIPAL_COLOR};
                color: #E0E0E0;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 12px;
                font-weight: 500;
                letter-spacing: 0.3px;
                padding: 4px 0px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                spacing: 12px;
            }}

            QMenuBar::item {{
                background-color: transparent;
                color: #B0B0B0;
                padding: 6px 16px;
                margin: 0px 1px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: 500;
            }}

            QMenuBar::item:selected {{
                background-color: rgba(76, 175, 80, 0.15);
                color: #FFFFFF;
                border: none;
            }}

            QMenuBar::item:pressed {{
                background-color: rgba(76, 175, 80, 0.25);
                color: #FFFFFF;
            }}

            /* =========================================== */
            /* MENUS DÉROULANTS - STYLE ÉPURÉ */
            /* =========================================== */

            QMenu {{
                background-color: {constant.PRINCIPAL_COLOR};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 4px 0px;
                margin: 2px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }}

            QMenu::separator {{
                height: 1px;
                background-color: rgba(255, 255, 255, 0.08);
                margin: 4px 12px;
            }}

            /* Items de menu - CORRECTION ESPACE ICÔNE */
            QMenu::item {{
                background-color: transparent;
                color: #D0D0D0;
                padding: 8px 24px 8px 36px; /* 36px à gauche pour laisser place à l'icône */
                border: none;
                font-size: 11px;
                font-weight: 400;
                min-height: 28px;
                margin: 0px;
            }}

            /* POSITION PRÉCISE DE L'ICÔNE - PAS D'ESPACE PARASITE */
            QMenu::icon {{
                position: absolute;
                left: 12px; /* Position fixe à 12px du bord gauche */
                width: 16px;
                height: 16px;
            }}

            /* Supprime tout espace entre l'icône et le texte */
            QMenu::item::indicator {{
                width: 0px;
                height: 0px;
            }}

            /* TEXTE aligné après l'icône */
            QMenu::item::text {{
                padding-left: 8px; /* Petit espace après l'icône */
            }}

            /* État sélectionné - accent vert */
            QMenu::item:selected {{
                background-color: rgba(76, 175, 80, 0.2);
                color: #FFFFFF;
                border-left: 3px solid {constant.ACCENT_COLOR};
                padding-left: 33px; /* 36px - 3px pour la bordure */
            }}

            QMenu::item:selected:!enabled {{
                background-color: transparent;
                color: #666666;
                border-left: 3px solid transparent;
                padding-left: 36px;
            }}

            /* État désactivé */
            QMenu::item:disabled {{
                color: #666666;
                background-color: transparent;
            }}

            /* État cochable */
            QMenu::item:checked {{
                background-color: rgba(76, 175, 80, 0.1);
                color: {constant.ACCENT_COLOR};
                font-weight: 500;
            }}

            /* Raccourcis clavier - alignés à droite */
            QMenu::item::shortcut {{
                color: #888888;
                font-size: 10px;
                font-weight: 400;
                padding-right: 4px;
                margin-left: 40px; /* Éloigne du texte principal */
            }}

            QMenu::item:selected::shortcut {{
                color: #AAAAAA;
            }}

            /* =========================================== */
            /* ANIMATIONS ET EFFETS */
            /* =========================================== */

            QMenu::item:hover {{
                background-color: rgba(255, 255, 255, 0.07);
                color: #FFFFFF;
            }}

            QMenu::item:pressed {{
                background-color: rgba(76, 175, 80, 0.25);
                color: #FFFFFF;
            }}

            /* Indicateur de sous-menu */
            QMenu::right-arrow {{
                image: url(none);
                width: 16px;
                height: 16px;
                margin-right: 8px;
            }}

            QMenu::right-arrow:selected {{
                image: url(none);
            }}
        """)
        pass

    def create_menu(self):
        self.fileMenu = QtWidgets.QMenu("Fichier")
        self.playMenu = QtWidgets.QMenu("Lecture")
        self.playlistMenu = QtWidgets.QMenu("Playlist")
        self.helpMenu = QtWidgets.QMenu("Support")
        pass

    # ------------------------------------------------------------
    # 🎨 APPLICATION DE LA PALETTE SUR TOUS LES MENUS
    # ------------------------------------------------------------
    def apply_palette(self):
        dark_bg = QtGui.QColor(constant.PRINCIPAL_COLOR)
        dark_hover = QtGui.QColor(constant.HOVER_COLOR)
        text_color = QtGui.QColor("#ffffff")
        accent_color = QtGui.QColor(constant.ACCENT_COLOR)

        def palette_for_menu(menu: QtWidgets.QMenu):
            pal = menu.palette()

            # Fond du menu
            pal.setColor(QtGui.QPalette.Window, dark_bg)
            pal.setColor(QtGui.QPalette.Base, dark_bg)

            # Texte
            pal.setColor(QtGui.QPalette.WindowText, text_color)
            pal.setColor(QtGui.QPalette.Text, text_color)
            pal.setColor(QtGui.QPalette.ButtonText, text_color)

            # Hover (zones actives) - vert accent
            pal.setColor(QtGui.QPalette.Highlight, accent_color)
            pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))

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
        bar_pal.setColor(QtGui.QPalette.Highlight, accent_color)
        bar_pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))
        self.setPalette(bar_pal)
        self.setAutoFillBackground(True)

    # ------------------------------------------------------------
    def fileMenu_customize(self):
        self.addMenu(self.fileMenu)

        self.act_open_file = self.fileMenu.addAction(
            QtGui.QIcon(constant.ICON_OPEN_FILE) if constant.ICON_OPEN_FILE else "",
            "Ajouter un fichier à la playlist"
        )
        self.act_open_file.setShortcut("Ctrl+O")

        self.act_open_folder = self.fileMenu.addAction(
            QtGui.QIcon(constant.ICON_OPEN_FOLDER) if constant.ICON_OPEN_FOLDER else "",
            "Ajouter un dossier à la playlist"
        )
        self.act_open_folder.setShortcut("Ctrl+D")

        self.act_app_exit = self.fileMenu.addAction(
            QtGui.QIcon(constant.ICON_EXIT) if constant.ICON_EXIT else "",
            "Quitter"
        )
        self.act_app_exit.setShortcut("Ctrl+Q")

        self.fileMenu.addSeparator()
        pass

    def playMenu_customize(self):
        self.addMenu(self.playMenu)

        self.act_play = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_PLAY),
            "Lire"
        )

        self.act_stop = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_STOP),
            "Stop"
        )

        self.act_skip_next = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_SKIP_NEXT),
            "Lire le suivant"
        )

        self.act_skip_previous = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_SKIP_PREVIOUS),
            "Lire le précédent"
        )

        self.act_full_screen_mode = self.playMenu.addAction(
            QtGui.QIcon(constant.ICON_FULLSCREEN),
            "Mode plein écran  "
        )
        self.act_full_screen_mode.setShortcut(QtGui.QKeySequence("F11"))
        self.playMenu.addSeparator()
        pass

    def playlistMenu_customize(self):
        self.addMenu(self.playlistMenu)

        self.act_show_playlist = self.playlistMenu.addAction(
            QtGui.QIcon(constant.ICON_PLAYLIST) if constant.ICON_PLAYLIST else "",
            "Masquer le panneau des playlists"
        )
        self.act_show_playlist.setShortcut("Ctrl+P")

        self.act_save_playlist_state = self.playlistMenu.addAction(
            QtGui.QIcon(constant.ICON_SAVE) if constant.ICON_SAVE else "",
            "Créer une nouvelle playlist"
        )
        self.act_save_playlist_state.setShortcut("Ctrl+N")

        self.act_remove_playlist_state = self.playlistMenu.addAction(
            QtGui.QIcon(constant.ICON_DELETE) if constant.ICON_DELETE else "",
            "Supprimer une playlist"
        )
        self.act_remove_playlist_state.setShortcut("Ctrl+S")
        pass

    def helpMenu_customize(self):
        self.addMenu(self.helpMenu)

        self.act_help = self.helpMenu.addAction(
            QtGui.QIcon(constant.ICON_HELP) if constant.ICON_HELP else "",
            "Aide"
        )

        self.act_about = self.helpMenu.addAction(
            QtGui.QIcon(constant.ICON_INFOS) if constant.ICON_INFOS else "",
            "À propos"
        )
        pass

    def set_tool_tip(self, ok: bool):
        if ok:
            self.fileMenu.setToolTip("Ouvrir des fichiers ou dossiers")
            self.playMenu.setToolTip("Lire des fichiers de la liste de lecture")
            self.playlistMenu.setToolTip("Voir, ajoutez ou supprimer des titres de vos liste de lecture")
            self.helpMenu.setToolTip("Obtenir de l'aide")
        pass

    def toggle_full_screen_display(self, checked):
        """
        Bascule entre mode plein écran et mode normal
        Met à jour l'icône et le texte de l'action

        Args:
            checked (bool): État de l'action (True = plein écran, False = normal)
        """
        if checked:
            self.act_full_screen_mode.setIcon(QtGui.QIcon(constant.ICON_FULLSCREEN_EXIT))
            self.act_full_screen_mode.setText("Quitter le plein écran")
        else:
            self.act_full_screen_mode.setIcon(QtGui.QIcon(constant.ICON_FULLSCREEN))
            self.act_full_screen_mode.setText("Mode plein écran")

        # Optionnel: Forcer la mise à jour du menu
        self.playMenu.repaint()

    def setup_connection(self):
        self.act_full_screen_mode.triggered.connect(self.toggle_full_screen_display)
        pass

    pass

class HelpDialog(QtWidgets.QDialog):
    """Boîte de dialogue d'aide interactive et moderne"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aide - PyPlayer")
        self.setModal(True)
        # TAILLE RÉDUITE
        self.setFixedSize(750, 500)  # Taille fixe réduite
        self.setup_ui()
        self.setup_styles()
        self.setup_connections()

    def setup_ui(self):
        """Configure l'interface de l'aide"""
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header avec titre et bouton fermer
        self.create_header(main_layout)

        # TabWidget pour les différentes sections
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setDocumentMode(True)
        main_layout.addWidget(self.tab_widget, 1)

        # Créer les onglets
        self.create_welcome_tab()
        self.create_shortcuts_tab()
        self.create_features_tab()
        self.create_tips_tab()

        # Footer avec version et crédits
        self.create_footer(main_layout)

    def create_header(self, parent_layout):
        """Crée l'en-tête avec titre et bouton fermer"""
        header_widget = QtWidgets.QWidget()
        header_widget.setObjectName("help_header")
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 10, 15, 10)  # Marges réduites

        # Titre avec icône
        title_layout = QtWidgets.QHBoxLayout()
        title_layout.setSpacing(10)

        # Icône réduite
        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(32, 32)  # Taille réduite
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                border-radius: 16px;
                font-size: 18px;
                font-weight: bold;
                color: white;
                qproperty-alignment: AlignCenter;
            }
        """)
        icon_label.setText("🎬")

        # Texte du titre réduit
        title_text = QtWidgets.QLabel("Aide PyPlayer")
        title_text.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #FFFFFF;
                background-color: transparent;
            }
        """)

        title_layout.addWidget(icon_label)
        title_layout.addWidget(title_text)
        title_layout.addStretch()

        # Bouton fermer
        self.close_button = QtWidgets.QPushButton("Fermer")
        self.close_button.setFixedSize(70, 30)  # Taille réduite
        self.close_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.close_button.setObjectName("close_button")

        header_layout.addLayout(title_layout)
        header_layout.addWidget(self.close_button)

        parent_layout.addWidget(header_widget)

    def create_welcome_tab(self):
        """Onglet d'accueil/bienvenue"""
        tab = QtWidgets.QWidget()
        tab.setObjectName("welcome_tab")
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)  # Marges réduites
        layout.setSpacing(15)

        # Animation/Vidéo de présentation réduite
        video_widget = QtWidgets.QWidget()
        video_widget.setMinimumHeight(120)  # Hauteur réduite
        video_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2196F3, stop:1 #4CAF50);
                border-radius: 8px;
            }
        """)

        # Conteneur pour l'animation
        video_container = QtWidgets.QVBoxLayout(video_widget)
        video_container.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        play_icon = QtWidgets.QLabel("▶️")
        play_icon.setStyleSheet("""
            QLabel {
                font-size: 36px;
                background-color: transparent;
            }
        """)
        play_text = QtWidgets.QLabel("Votre lecteur vidéo intelligent")
        play_text.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: white;
                background-color: transparent;
            }
        """)

        video_container.addWidget(play_icon)
        video_container.addWidget(play_text)

        # Texte de bienvenue avec police réduite
        welcome_text = QtWidgets.QLabel()
        welcome_text.setTextFormat(QtCore.Qt.TextFormat.RichText)
        welcome_text.setText("""
            <div style='text-align: center;'>
                <h3 style='color: #4CAF50; margin-bottom: 8px;'>Bienvenue dans PyPlayer !</h3>
                <p style='font-size: 12px; color: #CCCCCC; line-height: 1.5;'>
                PyPlayer est votre compagnon idéal pour regarder des vidéos.<br>
                Simple, rapide et efficace.
                </p>
            </div>
        """)
        welcome_text.setWordWrap(True)
        welcome_text.setStyleSheet("background-color: transparent;")

        # Boutons d'action rapide plus petits
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)

        quick_buttons = [
            ("🎥 Raccourcis", self.show_shortcuts_tab),
            ("✨ Fonctionnalités", self.show_features_tab),
            ("💡 Conseils", self.show_tips_tab)
        ]

        button_layout.addStretch()

        for text, callback in quick_buttons:
            btn = QtWidgets.QPushButton(text)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("quick_button")
            btn.setFixedHeight(35)  # Hauteur fixe
            btn.clicked.connect(callback)
            button_layout.addWidget(btn)

        button_layout.addStretch()

        layout.addWidget(video_widget)
        layout.addWidget(welcome_text)
        layout.addLayout(button_layout)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Accueil")

    def create_shortcuts_tab(self):
        """Onglet des raccourcis clavier"""
        tab = QtWidgets.QWidget()
        tab.setObjectName("shortcuts_tab")
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)  # Marges réduites
        layout.setSpacing(8)

        # Introduction réduite
        intro_label = QtWidgets.QLabel("🎮 <b>Raccourcis clavier</b>")
        intro_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        intro_label.setStyleSheet("""
            font-size: 14px; 
            color: #FFFFFF; 
            margin-bottom: 10px;
            background-color: transparent;
        """)
        layout.addWidget(intro_label)

        # Scroll area pour les raccourcis
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                background-color: rgba(40, 40, 40, 0.5);
            }
            QScrollBar:vertical {
                width: 8px;
                background-color: rgba(30, 30, 30, 0.8);
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #4CAF50;
                border-radius: 4px;
                min-height: 20px;
            }
        """)

        shortcuts_widget = QtWidgets.QWidget()
        shortcuts_layout = QtWidgets.QVBoxLayout(shortcuts_widget)
        shortcuts_layout.setContentsMargins(10, 10, 10, 10)
        shortcuts_layout.setSpacing(6)

        # Catégories de raccourcis (texte réduit)
        categories = [
            {
                "title": "🎬 Lecture",
                "color": "#2196F3",
                "shortcuts": [
                    ("Espace", "⏯️ Lire/Pause", "Contrôle rapide"),
                    ("F11", "🖥️ Plein écran", "Immersion"),
                    ("Échap", "↩️ Sortir", "Quitter plein écran"),
                    ("Double-clic", "🎯 Lancer", "Sur une vidéo")
                ]
            },
            {
                "title": "📁 Fichiers",
                "color": "#4CAF50",
                "shortcuts": [
                    ("Ctrl+O", "📂 Ouvrir", "Ajouter vidéo"),
                    ("Ctrl+D", "📁 Dossier", "Créer playlist"),
                    ("Ctrl+P", "📋 Playlist", "Afficher/Masquer")
                ]
            },
            {
                "title": "🔊 Volume",
                "color": "#FF9800",
                "shortcuts": [
                    ("Flèche ↑", "🔊 +2%", "Augmenter"),
                    ("Flèche ↓", "🔉 -2%", "Diminuer"),
                    ("Muet", "🔇 Muet", "Silence")
                ]
            },
            {
                "title": "🎮 Navigation",
                "color": "#9C27B0",
                "shortcuts": [
                    ("Ctrl+→", "⏭️ Suivant", "Vidéo suivante"),
                    ("Ctrl+←", "⏮️ Précédent", "Vidéo précédente"),
                    ("Ctrl+Q", "🚪 Quitter", "Fermer app")
                ]
            }
        ]

        for category in categories:
            # En-tête de catégorie réduit
            cat_header = QtWidgets.QWidget()
            cat_header.setStyleSheet(f"""
                QWidget {{
                    background-color: {category['color']}20;
                    border-left: 3px solid {category['color']};
                    border-radius: 3px;
                }}
            """)
            cat_layout = QtWidgets.QHBoxLayout(cat_header)
            cat_layout.setContentsMargins(10, 6, 10, 6)

            cat_label = QtWidgets.QLabel(category["title"])
            cat_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    font-weight: bold;
                    color: #FFFFFF;
                    background-color: transparent;
                }
            """)
            cat_layout.addWidget(cat_label)
            cat_layout.addStretch()

            shortcuts_layout.addWidget(cat_header)

            # Items de raccourcis plus compacts
            for shortcut, action, description in category["shortcuts"]:
                shortcut_item = self.create_shortcut_item(shortcut, action, description)
                shortcuts_layout.addWidget(shortcut_item)

            # Espacement réduit entre catégories
            shortcuts_layout.addSpacing(8)

        shortcuts_layout.addStretch()
        scroll_area.setWidget(shortcuts_widget)
        layout.addWidget(scroll_area, 1)

        self.tab_widget.addTab(tab, "Raccourcis")

    def create_shortcut_item(self, shortcut, action, description):
        """Crée un widget pour afficher un raccourci"""
        item = QtWidgets.QWidget()
        item.setObjectName("shortcut_item")
        item.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        item.setFixedHeight(40)  # Hauteur fixe

        layout = QtWidgets.QHBoxLayout(item)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Raccourci clavier plus petit
        shortcut_label = QtWidgets.QLabel(shortcut)
        shortcut_label.setStyleSheet("""
            QLabel {
                background-color: rgba(76, 175, 80, 0.2);
                color: #4CAF50;
                padding: 4px 8px;
                border-radius: 10px;
                font-family: 'Consolas', 'Monospace';
                font-weight: bold;
                font-size: 10px;
                min-width: 60px;
                max-width: 60px;
                text-align: center;
                border: 1px solid rgba(76, 175, 80, 0.3);
            }
        """)

        # Action avec icône réduite
        action_label = QtWidgets.QLabel(action)
        action_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: 500;
                color: #E0E0E0;
                min-width: 100px;
                max-width: 100px;
                background-color: transparent;
            }
        """)

        # Description plus courte
        desc_label = QtWidgets.QLabel(description)
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #AAAAAA;
                background-color: transparent;
            }
        """)
        desc_label.setWordWrap(True)
        desc_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        desc_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred
        )

        layout.addWidget(shortcut_label)
        layout.addWidget(action_label)
        layout.addWidget(desc_label, 1)

        # Animation au survol
        item.enterEvent = lambda e: self.animate_shortcut_item(item, True)
        item.leaveEvent = lambda e: self.animate_shortcut_item(item, False)

        return item

    def animate_shortcut_item(self, item, hover):
        """Animation de survol pour les items de raccourci"""
        if hover:
            item.setStyleSheet("""
                QWidget#shortcut_item {
                    background-color: rgba(255, 255, 255, 0.05);
                    border-radius: 4px;
                }
                QWidget#shortcut_item QLabel {
                    background-color: transparent;
                }
            """)
        else:
            item.setStyleSheet("""
                QWidget#shortcut_item { 
                    background-color: transparent; 
                }
                QWidget#shortcut_item QLabel {
                    background-color: transparent;
                }
            """)

    def create_features_tab(self):
        """Onglet des fonctionnalités avec SCROLL AREA"""
        tab = QtWidgets.QWidget()
        tab.setObjectName("features_tab")
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Titre
        title = QtWidgets.QLabel("✨ Fonctionnalités")
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #4CAF50;
                background-color: transparent;
            }
        """)
        layout.addWidget(title)

        # SCROLL AREA pour les fonctionnalités
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background-color: rgba(30, 30, 30, 0.8);
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #4CAF50;
                border-radius: 4px;
                min-height: 20px;
            }
        """)

        # Widget conteneur pour le scroll
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(15)

        features = [
            {
                "icon": "🎯",
                "title": "Lecture intelligente",
                "description": "Reprend automatiquement là où vous vous étiez arrêté",
                "color": "#2196F3"
            },
            {
                "icon": "📁",
                "title": "Organisation facile",
                "description": "Créez des playlists depuis vos dossiers de vidéos",
                "color": "#4CAF50"
            },
            {
                "icon": "💾",
                "title": "Sauvegarde automatique",
                "description": "Tout est sauvegardé automatiquement",
                "color": "#FF9800"
            },
            {
                "icon": "🎨",
                "title": "Interface épurée",
                "description": "Mode sombre confortable pour les yeux",
                "color": "#9C27B0"
            },
            {
                "icon": "🔄",
                "title": "4 modes de lecture",
                "description": "Normal, Boucle 1, Boucle Tous, Aléatoire",
                "color": "#00BCD4"
            },
            {
                "icon": "🎲",
                "title": "Lecture aléatoire",
                "description": "Mélange les vidéos pour varier les plaisirs",
                "color": "#E91E63"
            }
        ]

        for feature in features:
            feature_widget = self.create_feature_card(
                feature["icon"],
                feature["title"],
                feature["description"],
                feature["color"]
            )
            scroll_layout.addWidget(feature_widget)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area, 1)

        self.tab_widget.addTab(tab, "Fonctionnalités")

    def create_feature_card(self, icon, title, description, color):
        """Crée une carte de fonctionnalité avec texte correctement géré"""
        card = QtWidgets.QWidget()
        card.setObjectName("feature_card")
        card.setMinimumHeight(100)  # Hauteur minimale réduite
        card.setMaximumHeight(120)  # Hauteur maximale réduite

        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Conteneur pour icône et titre (sur la même ligne)
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(10)

        # Icône réduite
        icon_label = QtWidgets.QLabel(icon)
        icon_label.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                background-color: {color}20;
                border-radius: 20px;
                padding: 6px;
                qproperty-alignment: AlignCenter;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
            }}
        """)

        # Titre avec wrap
        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {color};
                background-color: transparent;
            }}
        """)
        title_label.setWordWrap(True)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label, 1)

        # Description avec gestion correcte du texte
        desc_label = QtWidgets.QLabel(description)
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #CCCCCC;
                background-color: transparent;
                padding: 2px 0px;
            }
        """)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        # Configuration pour éviter la coupure de mots
        desc_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        desc_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding
        )
        # Forcer le minimum height pour afficher tout le texte
        desc_label.setMinimumHeight(35)

        layout.addLayout(header_layout)
        layout.addWidget(desc_label)

        # Animation au clic
        def animate_click():
            card.setStyleSheet(f"""
                QWidget#feature_card {{
                    background-color: {color}15;
                    border: 2px solid {color}40;
                    border-radius: 8px;
                }}
                QWidget#feature_card QLabel {{
                    background-color: transparent;
                }}
            """)
            QtCore.QTimer.singleShot(300, lambda: card.setStyleSheet("""
                QWidget#feature_card { 
                    background-color: rgba(50, 50, 50, 0.5); 
                    border: 1px solid #3A3A3A; 
                    border-radius: 8px; 
                }
                QWidget#feature_card QLabel {
                    background-color: transparent;
                }
            """))

        card.mousePressEvent = lambda e: animate_click()
        card.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        return card

    def create_tips_tab(self):
        """Onglet des conseils d'utilisation avec SCROLL AREA"""
        tab = QtWidgets.QWidget()
        tab.setObjectName("tips_tab")
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Titre
        title = QtWidgets.QLabel("💡 Conseils")
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #FF9800;
                background-color: transparent;
            }
        """)
        layout.addWidget(title)

        # SCROLL AREA pour les conseils
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background-color: rgba(30, 30, 30, 0.8);
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #FF9800;
                border-radius: 4px;
                min-height: 20px;
            }
        """)

        # Widget conteneur pour le scroll
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(8)

        tips = [
            "🎯 <b>Double-cliquez</b> sur la vidéo pour lire/mettre en pause",
            "🖱️ <b>Plein écran</b> : bougez la souris pour afficher les contrôles",
            "🎲 <b>Utilisez F11</b> pour immersion complète",
            "📁 <b>Playlists</b> par type de contenu (films, séries, tutoriels)",
            "🔊 <b>Volume</b> : flèches Haut/Bas pour ajustements précis",
            "💾 <b>Sauvegarde</b> automatique - ne vous inquiétez pas !",
            "🔄 <b>Changez de mode</b> selon votre humeur",
            "🎬 <b>Formats</b> : MP4, AVI, MKV, MOV, WEBM, WMV, FLV, MPEG, MPG, M4V"
        ]

        for tip in tips:
            tip_widget = QtWidgets.QWidget()
            tip_widget.setMinimumHeight(40)
            tip_layout = QtWidgets.QHBoxLayout(tip_widget)
            tip_layout.setContentsMargins(10, 5, 10, 5)

            # Point décoratif
            dot = QtWidgets.QLabel("•")
            dot.setStyleSheet("""
                QLabel {
                    font-size: 20px;
                    color: #FF9800;
                    min-width: 15px;
                    background-color: transparent;
                }
            """)

            # Texte du conseil
            tip_label = QtWidgets.QLabel(tip)
            tip_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
            tip_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #E0E0E0;
                    background-color: transparent;
                }
            """)
            tip_label.setWordWrap(True)
            tip_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            tip_label.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Preferred
            )

            tip_layout.addWidget(dot)
            tip_layout.addWidget(tip_label, 1)

            scroll_layout.addWidget(tip_widget)

        # Note importante
        note = QtWidgets.QLabel()
        note.setTextFormat(QtCore.Qt.TextFormat.RichText)
        note.setText("""
            <div style='background-color: rgba(76, 175, 80, 0.1); padding: 12px; border-radius: 6px; border-left: 3px solid #4CAF50;'>
                <b style='color: #4CAF50; font-size: 12px;'>💾 Sauvegarde automatique</b><br>
                <span style='font-size: 11px; color: #CCCCCC;'>
                • ✅ Position des vidéos<br>
                • ✅ Volume et muet<br>
                • ✅ Ordre des playlists<br>
                • ✅ Mode de lecture<br><br>
                <i>Tout sera exactement comme vous l'avez laissé !</i>
                </span>
            </div>
        """)
        note.setStyleSheet("background-color: transparent;")
        note.setWordWrap(True)
        scroll_layout.addWidget(note)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area, 1)

        self.tab_widget.addTab(tab, "Conseils")

    def create_footer(self, parent_layout):
        """Crée le pied de page réduit"""
        footer_widget = QtWidgets.QWidget()
        footer_widget.setObjectName("help_footer")
        footer_widget.setFixedHeight(35)  # Hauteur fixe réduite
        footer_layout = QtWidgets.QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(15, 5, 15, 5)

        # Version réduite
        version_label = QtWidgets.QLabel("PyPlayer v0.0.1")
        version_label.setStyleSheet("""
            font-size: 10px; 
            color: #666666;
            background-color: transparent;
        """)

        # Crédits réduits
        credits_label = QtWidgets.QLabel("Développé par Josias KOUTCHANOU")
        credits_label.setStyleSheet("""
            font-size: 10px; 
            color: #666666;
            background-color: transparent;
        """)

        # Logo réduit
        logo_label = QtWidgets.QLabel("🎬")
        logo_label.setStyleSheet("""
            font-size: 14px;
            background-color: transparent;
        """)

        footer_layout.addWidget(version_label)
        footer_layout.addStretch()
        footer_layout.addWidget(credits_label)
        footer_layout.addStretch()
        footer_layout.addWidget(logo_label)

        parent_layout.addWidget(footer_widget)

    def setup_styles(self):
        """Configure les styles globaux réduits"""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {constant.PRINCIPAL_COLOR};
                border: 1px solid {constant.THIRD_COLOR};
                border-radius: 10px;
            }}

            QTabWidget::pane {{
                border: none;
                background-color: {constant.SECONDARY_COLOR};
            }}

            QTabBar::tab {{
                background-color: transparent;
                color: #AAAAAA;
                padding: 8px 16px;
                margin-right: 2px;
                font-size: 11px;
                font-weight: 500;
                border: none;
            }}

            QTabBar::tab:selected {{
                color: #FFFFFF;
                border-bottom: 2px solid #4CAF50;
            }}

            QTabBar::tab:hover {{
                color: #FFFFFF;
                background-color: rgba(255, 255, 255, 0.05);
            }}

            QPushButton#close_button {{
                background-color: rgba(76, 175, 80, 0.1);
                color: #4CAF50;
                border: 1px solid rgba(76, 175, 80, 0.3);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 500;
                padding: 5px 12px;
            }}

            QPushButton#close_button:hover {{
                background-color: rgba(76, 175, 80, 0.2);
                border-color: rgba(76, 175, 80, 0.5);
            }}

            QPushButton#close_button:pressed {{
                background-color: rgba(76, 175, 80, 0.3);
            }}

            QPushButton#quick_button {{
                background-color: rgba(76, 175, 80, 0.1);
                color: #4CAF50;
                padding: 8px 12px;
                border: 1px solid rgba(76, 175, 80, 0.3);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 500;
            }}

            QPushButton#quick_button:hover {{
                background-color: rgba(76, 175, 80, 0.2);
                border-color: rgba(76, 175, 80, 0.5);
            }}

            QWidget#help_header {{
                background-color: {constant.SECONDARY_COLOR};
                border-bottom: 1px solid {constant.THIRD_COLOR};
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}

            QWidget#help_footer {{
                background-color: {constant.SECONDARY_COLOR};
                border-top: 1px solid {constant.THIRD_COLOR};
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }}

            QWidget#feature_card {{
                background-color: rgba(50, 50, 50, 0.5);
                border: 1px solid #3A3A3A;
                border-radius: 8px;
            }}

            QWidget#feature_card:hover {{
                border-color: rgba(255, 255, 255, 0.2);
                background-color: rgba(60, 60, 60, 0.7);
            }}

            /* Assure que TOUS les QLabel ont un fond transparent */
            QLabel {{
                background-color: transparent;
            }}
        """)

    def setup_connections(self):
        """Configure les connexions des signaux"""
        self.close_button.clicked.connect(self.accept)

    def show_shortcuts_tab(self):
        """Affiche l'onglet des raccourcis"""
        self.tab_widget.setCurrentIndex(1)

    def show_features_tab(self):
        """Affiche l'onglet des fonctionnalités"""
        self.tab_widget.setCurrentIndex(2)

    def show_tips_tab(self):
        """Affiche l'onglet des conseils"""
        self.tab_widget.setCurrentIndex(3)