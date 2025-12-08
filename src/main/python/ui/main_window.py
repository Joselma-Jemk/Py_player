from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
import src.main.python.ui.widget.constant as constant
from src.main.python.ui.widget.dock_widget import DockWidget
from src.main.python.ui.widget.menu_bar import MenuBarWidget
from src.main.python.ui.widget.player import PlayerWidget
from src.main.python.ui.widget.staturbar_widget import StatusBar
from src.main.python.ui.widget.tool_bar import ToolBarWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.icon_font = None
        self.setup_ui()
        self.first_source_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.MoviesLocation)

    def setup_ui(self):
        self.customize_self()
        self.create_widgets()
        self.modify_widgets()
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
        self.menubar_widget = MenuBarWidget(self)
        self.setMenuBar(self.menubar_widget)
        self.toolbar_widget = ToolBarWidget(self)
        self.addToolBar(QtGui.Qt.ToolBarArea.BottomToolBarArea, self.toolbar_widget)
        self.dock_widget = DockWidget()
        self.addDockWidget(QtGui.Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widget)
        self.statusbar_widget = StatusBar(self)
        self.setStatusBar(self.statusbar_widget)

        pass

    def modify_widgets(self):
        self.toolbar_widget.setMovable(False)
        pass

    def setup_connections(self):
        # MenuBar
        self.menubar_widget.act_app_exit.triggered.connect(self.close)
        self.menubar_widget.act_open_file.triggered.connect(self.choose_file)
        self.menubar_widget.act_open_folder.triggered.connect(self.choose_dir)
        self.menubar_widget.act_show_playlist.triggered.connect(self.playlist_show_or_hide)
        self.menubar_widget.act_about.triggered.connect(self.about_pyplayer)
        self.menubar_widget.act_play.triggered.connect(self.toolbar_widget.player_controls.btn_play_pause.clicked.emit)
        self.menubar_widget.act_save_playlist_state.triggered.connect(self.dock_widget.btn_save_playlist.clicked.emit)
        self.menubar_widget.act_remove_playlist_state.triggered.connect(self.dock_widget.btn_remove_save.clicked.emit)

        #DockWidget
        self.dock_widget.btn_add_to_playlist.clicked.connect(self.choose_file)
        self.dock_widget.btn_save_playlist.clicked.connect(self.get_save_info)
        self.dock_widget.btn_remove_save.clicked.connect(self.confirm_delete_playlist)

        #Toolbar
        self.toolbar_widget.btn_playlist.clicked.connect(self.playlist_show_or_hide)

        pass

    from pathlib import Path

    def choose_file(self):
        """Ouvre une boîte de dialogue pour sélectionner un fichier vidéo"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier vidéo",
            self.first_source_dir,
            "Vidéos (*.mp4 *.avi *.mkv *.wmv *.flv *.mpeg *.mpg *.mov *.webm);;Tous les fichiers (*.*)"
        )

        if file_path:
            print(file_path)
            return file_path
        return ""

    def choose_dir(self):
        """Ouvre une boîte de dialogue pour sélectionner un dossier"""
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Sélectionner un dossier",
            self.first_source_dir
        )

        if dir_path:
            print(dir_path)
            return Path(dir_path)
        return Path("")

    def playlist_show_or_hide(self):
        if self.dock_widget.isVisible():
            self.dock_widget.setVisible(False)
            self.toolbar_widget.btn_playlist.setToolTip("Voir la playlist")
            return
        self.dock_widget.setVisible(True)
        self.toolbar_widget.btn_playlist.setToolTip("Masquer la playlist")

    def get_save_info(self):
        """Retourne nom et description de sauvegarde via un dialogue personnalisé"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Sauvegarder")
        dialog.setModal(True)
        dialog.setMinimumWidth(400)  # Largeur minimale pour un bon affichage

        # Création des widgets
        lbl_name = QtWidgets.QLabel("Nom :")
        edit_name = QtWidgets.QLineEdit()
        edit_name.setPlaceholderText("Nom de la sauvegarde")

        lbl_desc = QtWidgets.QLabel("Description :")
        edit_desc = QtWidgets.QTextEdit()
        edit_desc.setMaximumHeight(100)
        edit_desc.setPlaceholderText("Description optionnelle")

        # Création des boutons
        btn_save = QtWidgets.QPushButton("Save")
        btn_cancel = QtWidgets.QPushButton("Cancel")

        # Connexion des boutons
        btn_save.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)

        # Validation : désactiver "Save" si nom vide
        def validate_input():
            btn_save.setEnabled(bool(edit_name.text().strip()))

        edit_name.textChanged.connect(validate_input)

        # Création du layout pour les boutons (horizontal)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)  # Espace extensible à gauche
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_cancel)

        # Création du layout principal
        main_layout = QtWidgets.QVBoxLayout(dialog)

        # Ajout des champs de saisie
        main_layout.addWidget(lbl_name)
        main_layout.addWidget(edit_name)
        main_layout.addWidget(lbl_desc)
        main_layout.addWidget(edit_desc)

        # Ajout d'un espace extensible pour pousser les boutons vers le bas
        main_layout.addStretch(1)

        # Ajout du layout des boutons
        main_layout.addLayout(button_layout)

        # Initialiser la validation
        validate_input()

        # Exécution du dialogue
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            name = edit_name.text().strip()
            if name:
                return {
                    'name': name,
                    'description': edit_desc.toPlainText().strip()
                }

        return None

    def about_pyplayer(self):
        """Version avec icône affichée simplement"""

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("À propos de PyPlayer")
        dialog.setModal(True)
        dialog.setFixedSize(500, 450)

        # Style
        dialog.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #f0f0f0; }
            QLabel { color: #f0f0f0; }
        """)

        main_layout = QtWidgets.QVBoxLayout(dialog)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header avec icône
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(20)

        # Création du label pour l'icône - TAILLE NORMALE
        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(64, 64)  # Taille normale

        try:
            # Essayer de charger l'icône depuis constant
            if hasattr(constant, 'py_player_icone'):
                icon_path = constant.py_player_icone(4)
                if icon_path and Path(icon_path).exists():
                    pixmap = QtGui.QPixmap(icon_path)
                    if not pixmap.isNull():
                        # REDIMENSIONNER EN GARDANT LES PROPORTIONS
                        pixmap = pixmap.scaled(
                            64, 64,
                            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation
                        )

                        icon_label.setPixmap(pixmap)

                        # Pas de style circulaire, juste une bordure simple si besoin
                        icon_label.setStyleSheet("""
                            QLabel {
                                border: 1px solid #3a3a3a;
                                background-color: transparent;
                            }
                        """)
                    else:
                        raise ValueError("Pixmap invalide")
                else:
                    raise FileNotFoundError("Chemin d'icône invalide")
            else:
                raise AttributeError("Fonction py_player_icone non trouvée")

        except Exception as e:
            print(f"Erreur chargement icône: {e}")
            # Fallback avec emoji simple
            icon_label.setStyleSheet("""
                QLabel {
                    background-color: #0a74da;
                    font-size: 24px;
                    font-weight: bold;
                    color: white;
                }
            """)
            icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            icon_label.setText("🎬")

        # Titre et version
        text_widget = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QtWidgets.QLabel("PyPlayer")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #0a74da;
                padding-top: 5px;
            }
        """)

        version_label = QtWidgets.QLabel("Version 0.0.1")
        version_label.setStyleSheet("font-size: 14px; color: #a0a0a0;")

        text_layout.addWidget(title_label)
        text_layout.addWidget(version_label)
        text_layout.addStretch()

        # Alignement
        header_layout.addWidget(icon_label)
        header_layout.addWidget(text_widget)
        header_layout.addStretch()

        # Centrer verticalement
        header_layout.setAlignment(icon_label, QtCore.Qt.AlignmentFlag.AlignVCenter)
        header_layout.setAlignment(text_widget, QtCore.Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(header_layout)

        # Séparateur
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3a3a3a;")
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)

        # Zone de texte pour les informations
        info_text = QtWidgets.QTextEdit()
        info_text.setReadOnly(True)
        info_text.setText(f"""
        <div style='margin: 10px;'>
            <p style='font-size: 11pt; color: #d0d0d0;'>
            <b>Développé par :</b> Josias KOUTCHANOU<br><br>

            <b>Description :</b><br>
            Lecteur vidéo minimaliste et rapide pour vos fichiers multimédias locaux.<br><br>

            <b>Formats supportés :</b><br>
            <span style='color: #0a74da; font-family: monospace;'>
            MP4 • AVI • MKV • MOV • WEBM • WMV • FLV • MPEG • MPG
            </span><br><br>

            <b>Technologies :</b><br>
            • Python<br>
            • Qt for Python (PySide6)<br>
            • FFmpeg<br>
            • Icônes Material Icons<br><br>

            <b>Licence :</b><br>
            © 2025 Joselma. Tous droits réservés.
            </p>
        </div>
        """)

        main_layout.addWidget(info_text)

        # Bouton de fermeture
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        close_button = QtWidgets.QPushButton("Fermer")
        close_button.setFixedWidth(100)
        close_button.clicked.connect(dialog.accept)

        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

        # Afficher la boîte de dialogue
        dialog.exec()

    def confirm_delete_playlist(self, playlist_name=""):
        """Demande confirmation avec icône d'avertissement"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Confirmer la suppression")
        dialog.setModal(True)
        dialog.setFixedSize(400, 180)

        # Layout horizontal pour icône + texte
        content_layout = QtWidgets.QHBoxLayout()

        # Icône d'avertissement (emoji ou caractère Unicode)
        icon_label = QtWidgets.QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 36px;")
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedWidth(60)

        # Message
        message_widget = QtWidgets.QWidget()
        message_layout = QtWidgets.QVBoxLayout(message_widget)

        title_label = QtWidgets.QLabel("Supprimer la playlist")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        message_text = "Cette action est irréversible. Voulez-vous continuer ?"
        if playlist_name:
            message_text = f"Supprimer la playlist '{playlist_name}' ?\nCette action est irréversible."

        message_label = QtWidgets.QLabel(message_text)
        message_label.setWordWrap(True)

        message_layout.addWidget(title_label)
        message_layout.addWidget(message_label)
        message_layout.addStretch()

        content_layout.addWidget(icon_label)
        content_layout.addWidget(message_widget)

        # Boutons
        btn_yes = QtWidgets.QPushButton("Supprimer")
        btn_no = QtWidgets.QPushButton("Annuler")

        # Style pour le bouton Supprimer (rouge pour danger)
        btn_yes.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c62828;
            }
        """)

        # Style 1 : Bouton gris élégant
        btn_no.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
                border: 1px solid #616161;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #616161;
                border-color: #424242;
            }
            QPushButton:pressed {
                background-color: #424242;
            }
        """)

        btn_yes.clicked.connect(dialog.accept)
        btn_no.clicked.connect(dialog.reject)

        # Layout des boutons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(btn_no)
        button_layout.addWidget(btn_yes)

        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(dialog)
        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Retourner True si Oui/Supprimer, False si Non/Annuler
        return dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted

    pass
