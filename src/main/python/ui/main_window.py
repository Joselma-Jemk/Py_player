from pathlib import Path
import os
from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia
import src.main.python.ui.widget.constant as constant
from src.main.python.api.playlist import Playlist
from src.main.python.api.pyplayer_manager import PlaylistManager
from src.main.python.api.video import Video
from src.main.python.ui.widget.dock_widget import DockWidget, DeletePlaylistDialog
from src.main.python.ui.widget.menu_bar import MenuBarWidget
from src.main.python.ui.widget.player import PlayerWidget
from src.main.python.ui.widget.staturbar_widget import StatusBar
from src.main.python.ui.widget.tool_bar import ToolBarWidget

# Forcé ffmpeg
os.environ["QT_MEDIA_BACKEND"]="ffmpeg"

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.position_timer = QtCore.QTimer()
        self.manager = PlaylistManager()
        self.icon_font = None
        self.setup_ui()
        self.first_source_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.MoviesLocation)

    def setup_ui(self):
        self.customize_self()
        self.create_widgets()
        self.modify_widgets()
        self.setup_connections()
        self.initialize_playlist_state()
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
        self.menubar_widget.act_open_file.triggered.connect(self.dock_widget.btn_add_to_playlist.clicked.emit)
        self.menubar_widget.act_open_folder.triggered.connect(self.choose_folder)
        self.menubar_widget.act_show_playlist.triggered.connect(self.toolbar_widget.btn_playlist.clicked.emit)
        self.menubar_widget.act_about.triggered.connect(self.about_pyplayer)
        self.menubar_widget.act_play.triggered.connect(self.toolbar_widget.player_controls.btn_play_pause.clicked.emit)
        self.menubar_widget.act_save_playlist_state.triggered.connect(self.dock_widget.btn_save_playlist.clicked.emit)
        self.menubar_widget.act_remove_playlist_state.triggered.connect(self.dock_widget.btn_remove_save.clicked.emit)

        #DockWidget
        self.dock_widget.btn_add_to_playlist.clicked.connect(self.add_video_to_playlist)
        self.dock_widget.btn_remove_to_playlist.clicked.connect(self.remove_video_from_playlist)
        self.dock_widget.btn_save_playlist.clicked.connect(self.create_new_playlist)
        self.dock_widget.btn_remove_save.clicked.connect(self.delete_playlist)
        self.dock_widget.lstw_archive.itemSelectionChanged.connect(self.set_manually_active_playlist)

        #Toolbar
        self.toolbar_widget.btn_playlist.clicked.connect(self.playlist_show_or_hide)
            # player_control
        self.toolbar_widget.player_controls.btn_play_mode.clicked.connect(self.playlist_play_mode_update)
        self.toolbar_widget.player_controls.btn_play_pause.clicked.connect(self.play_or_pause)
        self.toolbar_widget.player_controls.btn_play_pause.clicked.connect(self.btn_play_pause_update)
        self.toolbar_widget.player_controls.btn_stop.clicked.connect(self.stop_playing)
        self.toolbar_widget.player_controls.btn_skipnext.clicked.connect(self.next_video)
        self.toolbar_widget.player_controls.btn_skipprevious.clicked.connect(self.previous_video)


        #Player
        self.player_widget.signal_double_click.connect(self.play_or_pause)
        self.player_widget.signal_double_click.connect(self.btn_play_pause_update)
        self.player_widget.video_player.mediaStatusChanged.connect(self.btn_play_pause_update)
        self.player_widget.video_player.mediaStatusChanged.connect(self.playlist_play_mode_update)
        self.player_widget.video_player.mediaStatusChanged.connect(self.current_video_update_metadata)
        self.player_widget.video_player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.player_widget.video_player.positionChanged.connect(self.save_video_on_position_changed)
        pass

    ##################### END UI ######################

    @property
    def active_playlist(self) -> Playlist:
        return self.manager.active_playlist

    @property
    def current_video(self) -> Video | None:
        playlist = self.active_playlist
        # on vérifie si la playlist est active
        if playlist.ensure_active() or playlist.current_video != -1:
            return playlist.current_video
        playlist.auto_save()
        return None

    # ============================================
    # MÉTHODES DE GESTION DES PLAYLISTS
    # ============================================

    def choose_file(self):
        """Ouvre une boîte de dialogue pour sélectionner un fichier vidéo"""
        # Déterminer le dossier de départ
        if hasattr(self, 'active_playlist') and self.active_playlist and self.active_playlist.path:
            start_dir = str(self.active_playlist.path)
        else:
            start_dir = QtCore.QStandardPaths.writableLocation(
                QtCore.QStandardPaths.StandardLocation.MoviesLocation
            )

        # Ouvrir la boîte de dialogue
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier vidéo",
            start_dir,
            "Vidéos (*.mp4 *.avi *.mkv *.mov *.webm *.wmv *.flv *.mpeg *.mpg *.m4v);;Tous les fichiers (*.*)"
        )

        return file_path

    def choose_folder(self):
        """Ouvre une boîte de dialogue pour sélectionner un dossier"""
        # Déterminer le dossier de départ
        if hasattr(self, 'active_playlist') and self.active_playlist and self.active_playlist.path:
            start_dir = str(self.active_playlist.path)
        else:
            start_dir = QtCore.QStandardPaths.writableLocation(
                QtCore.QStandardPaths.StandardLocation.HomeLocation
            )

        # Ouvrir la boîte de dialogue
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Sélectionner un dossier",
            start_dir,
            QtWidgets.QFileDialog.Option.ShowDirsOnly or QtWidgets.QFileDialog.Option.DontResolveSymlinks
        )

        video_list = self.active_playlist.add_video_from_dir_path(Path(dir_path))
        for video in video_list:
            self.dock_widget.add_video_to_playlist(video)
        return True

    def playlist_show_or_hide(self):
        if self.dock_widget.isVisible():
            self.dock_widget.setVisible(False)
            self.toolbar_widget.btn_playlist.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Afficher le panneau des playlists</b>")
            self.menubar_widget.act_show_playlist.setText("Afficher le panneau des playlists")
            return
        self.dock_widget.setVisible(True)
        self.toolbar_widget.btn_playlist.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Masquer le panneau des playlists</b>")
        self.menubar_widget.act_show_playlist.setText("Masquer le panneau des playlists")

    def get_playlist_create_info(self):
        """Retourne nom, chemin et description de playlist via un dialogue personnalisé"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Créer une nouvelle playlist")
        dialog.setModal(True)
        dialog.setMinimumWidth(450)

        # Style global
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {constant.PRINCIPAL_COLOR};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QLabel {{
                color: {constant.PRINCIPAL_TEXT_COLOR};
                background-color: transparent;
            }}
            QLineEdit, QTextEdit {{
                background-color: {constant.SECONDARY_COLOR};
                color: {constant.PRINCIPAL_TEXT_COLOR};
                border: 1px solid {constant.THIRD_COLOR};
                border-radius: 4px;
                padding: 6px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {constant.ACCENT_COLOR};
            }}
            QPushButton {{
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
            }}
        """)

        # Création des widgets
        lbl_folder = QtWidgets.QLabel("Dossier de destination :")

        folder_layout = QtWidgets.QHBoxLayout()
        edit_folder = QtWidgets.QLineEdit()
        edit_folder.setPlaceholderText("Sélectionnez un dossier contenant des vidéos...")

        btn_browse = QtWidgets.QPushButton("📂 Parcourir...")
        btn_browse.setFixedWidth(120)
        btn_browse.setStyleSheet(f"""
            QPushButton {{
                background-color: {constant.THIRD_COLOR};
                color: {constant.PRINCIPAL_TEXT_COLOR};
            }}
            QPushButton:hover {{
                background-color: {constant.HOVER_COLOR};
            }}
        """)

        folder_layout.addWidget(edit_folder)
        folder_layout.addWidget(btn_browse)

        lbl_name = QtWidgets.QLabel("Nom de la playlist :")
        edit_name = QtWidgets.QLineEdit()
        edit_name.setPlaceholderText("Ex: Mes Favoris, Chill Vibes...")

        lbl_desc = QtWidgets.QLabel("Description :")
        edit_desc = QtWidgets.QTextEdit()
        edit_desc.setMaximumHeight(100)
        edit_desc.setPlaceholderText("Description optionnelle de la playlist...")

        # Label d'erreur pour le dossier
        error_label = QtWidgets.QLabel("")
        error_label.setStyleSheet(f"""
            QLabel {{
                color: {constant.ACCENT_COLOR};
                font-size: 12px;
                background-color: transparent;
            }}
        """)
        error_label.setVisible(False)

        # Label d'erreur pour le nom
        name_error_label = QtWidgets.QLabel("")
        name_error_label.setStyleSheet(f"""
            QLabel {{
                color: {constant.ACCENT_COLOR};
                font-size: 12px;
                background-color: transparent;
            }}
        """)
        name_error_label.setVisible(False)

        # Création des boutons principaux
        btn_save = QtWidgets.QPushButton("Créer la playlist")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {constant.THIRD_COLOR};
                color: {constant.OK_ONE_COLOR};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {constant.OK_ONE_COLOR};
                color: {constant.PRINCIPAL_TEXT_COLOR};
            }}
            QPushButton:disabled {{
                background-color: {constant.THIRD_COLOR};
                color: #8e8e93;
            }}
        """)

        btn_cancel = QtWidgets.QPushButton("Annuler")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {constant.THIRD_COLOR};
                color: {constant.PRINCIPAL_TEXT_COLOR};
            }}
            QPushButton:hover {{
                background-color: {constant.HOVER_COLOR};
            }}
        """)

        # Connexion des boutons
        btn_save.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)

        # Fonction pour parcourir les dossiers
        def browse_folder():
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                dialog,
                "Sélectionner un dossier contenant des vidéos",
                str(Path.home())
            )
            if folder:
                folder_path = Path(folder)
                edit_folder.setText(str(folder_path))

                # Si le champ nom est vide, on le remplit avec le nom du dossier
                if not edit_name.text().strip():
                    folder_name = folder_path.name
                    if folder_name and folder_name != "/":  # Éviter les noms vides ou racine
                        edit_name.setText(folder_name)
                    else:
                        edit_name.setText("nouvelle_playlist")

        btn_browse.clicked.connect(browse_folder)

        # Fonction pour extraire le nom du dossier
        def update_name_from_folder():
            folder_path = edit_folder.text().strip()
            if folder_path and not edit_name.text().strip():
                try:
                    folder_name = Path(folder_path).name
                    if folder_name and folder_name != "/":
                        edit_name.setText(folder_name)
                    else:
                        edit_name.setText("nouvelle_playlist")
                except:
                    edit_name.setText("nouvelle_playlist")

        edit_folder.textChanged.connect(update_name_from_folder)

        # Vérifier si le dossier existe, est accessible et contient des vidéos
        def validate_folder():
            folder_path = edit_folder.text().strip()
            if not folder_path:
                error_label.setVisible(False)
                return False

            try:
                path = Path(folder_path)

                # Vérifier si le chemin existe
                if not path.exists():
                    error_label.setText("❌ Ce dossier n'existe pas")
                    error_label.setVisible(True)
                    return False

                # Vérifier si c'est un dossier (et non un fichier)
                if not path.is_dir():
                    error_label.setText("❌ Le chemin spécifié n'est pas un dossier")
                    error_label.setVisible(True)
                    return False

                # Vérifier les permissions d'écriture
                try:
                    # Tester si on peut créer un fichier temporaire
                    test_file = path / ".write_test"
                    test_file.touch()
                    test_file.unlink()  # Supprimer le fichier test
                except (PermissionError, OSError):
                    error_label.setText("❌ Pas de permission d'écriture dans ce dossier")
                    error_label.setVisible(True)
                    return False

                # VÉRIFIER SI LE DOSSIER CONTIENT DES FICHIERS VIDÉO
                try:
                    # Utiliser les extensions vidéo de constant
                    video_extensions = constant.VIDEO_EXTENSIONS

                    # Compter le nombre de fichiers vidéo dans le dossier
                    video_files = []
                    for ext in video_extensions:
                        video_files.extend(list(path.rglob(f"*{ext}")))
                        video_files.extend(list(path.rglob(f"*{ext.upper()}")))

                    # Filtrer pour ne garder que les fichiers (pas les dossiers)
                    video_files = [f for f in video_files if f.is_file()]

                    if not video_files:
                        error_label.setText("❌ Ce dossier ne contient pas de fichiers vidéo")
                        error_label.setVisible(True)
                        return False

                    # Afficher le nombre de vidéos trouvées
                    num_videos = len(video_files)
                    if num_videos == 1:
                        video_info = f"✓ 1 fichier vidéo trouvé"
                    else:
                        video_info = f"✓ {num_videos} fichiers vidéo trouvés"

                    error_label.setText(video_info)
                    error_label.setStyleSheet(f"""
                        QLabel {{
                            color: #4CAF50;  /* Vert pour succès */
                            font-size: 12px;
                            background-color: transparent;
                        }}
                    """)
                    error_label.setVisible(True)

                    # Optionnel : Stocker le nombre de vidéos pour une utilisation ultérieure
                    if not hasattr(dialog, '_video_count'):
                        dialog._video_count = num_videos
                    else:
                        dialog._video_count = num_videos

                    return True

                except Exception as e:
                    error_label.setText(f"❌ Erreur lors de la recherche de vidéos: {str(e)[:50]}")
                    error_label.setVisible(True)
                    return False

            except Exception as e:
                error_label.setText(f"❌ Erreur: {str(e)[:50]}")
                error_label.setVisible(True)
                return False

        # Valider le nom de la playlist
        def validate_name():
            name = edit_name.text().strip()
            if not name:
                name_error_label.setVisible(False)
                return False

            # Vérifier la longueur
            if len(name) < 2:
                name_error_label.setText("❌ Le nom doit avoir au moins 2 caractères")
                name_error_label.setVisible(True)
                return False

            if len(name) > 100:
                name_error_label.setText("❌ Le nom ne doit pas dépasser 100 caractères")
                name_error_label.setVisible(True)
                return False

            # Vérifier les caractères interdits (pour les noms de fichiers)
            invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
            for char in invalid_chars:
                if char in name:
                    name_error_label.setText(f"❌ Caractère interdit: '{char}'")
                    name_error_label.setVisible(True)
                    return False

            # Vérifier si le fichier existe déjà dans le dossier
            folder_path = edit_folder.text().strip()
            if folder_path and validate_folder():
                try:
                    # Supposons que votre fichier playlist a une extension .json
                    playlist_file = Path(folder_path) / f"{name}.json"
                    if playlist_file.exists():
                        name_error_label.setText("⚠️ Une playlist avec ce nom existe déjà")
                        name_error_label.setVisible(True)
                        return True  # On permet mais on prévient
                except:
                    pass

            # Tout est OK
            name_error_label.setVisible(False)
            return True

        # Validation globale
        def validate_input():
            has_name = bool(edit_name.text().strip())
            has_folder = bool(edit_folder.text().strip())

            folder_valid = validate_folder() if has_folder else False
            name_valid = validate_name() if has_name else False

            # Réinitialiser le style du label d'erreur du dossier
            if error_label.text().startswith("✓"):
                error_label.setStyleSheet(f"""
                    QLabel {{
                        color: #4CAF50;
                        font-size: 12px;
                        background-color: transparent;
                    }}
                """)
            elif error_label.text():
                error_label.setStyleSheet(f"""
                    QLabel {{
                        color: {constant.ACCENT_COLOR};
                        font-size: 12px;
                        background-color: transparent;
                    }}
                """)

            btn_save.setEnabled(has_name and has_folder and folder_valid and name_valid)

        # Connecter les signaux de validation
        edit_name.textChanged.connect(validate_input)
        edit_folder.textChanged.connect(validate_input)
        edit_folder.editingFinished.connect(validate_input)

        # Validation à chaque modification
        edit_name.textChanged.connect(validate_name)
        edit_folder.textChanged.connect(lambda: (validate_folder(), validate_name()))

        # Layout des boutons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(btn_save)

        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(dialog)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Ajout des widgets
        main_layout.addWidget(lbl_folder)
        main_layout.addLayout(folder_layout)
        main_layout.addWidget(error_label)
        main_layout.addSpacing(10)

        main_layout.addWidget(lbl_name)
        main_layout.addWidget(edit_name)
        main_layout.addWidget(name_error_label)
        main_layout.addSpacing(10)

        main_layout.addWidget(lbl_desc)
        main_layout.addWidget(edit_desc)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        # Initialiser la validation
        validate_input()

        # Exécution du dialogue
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            name = edit_name.text().strip()
            folder_path = edit_folder.text().strip()

            # Validation finale
            if name and folder_path:
                try:
                    path = Path(folder_path)
                    if path.exists() and path.is_dir():
                        # Récupérer le nombre de vidéos trouvées
                        video_count = getattr(dialog, '_video_count', 0)

                        return {
                            'name': name,
                            'p_path': str(path),
                            'description': edit_desc.toPlainText().strip(),
                            'video_count': video_count  # Optionnel: nombre de vidéos trouvées
                        }
                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Erreur de validation",
                        f"Impossible de créer la playlist : {str(e)}"
                    )

            QtWidgets.QMessageBox.warning(
                self,
                "Données invalides",
                "Veuillez vérifier les informations saisies."
            )

        return None

    def set_manually_active_playlist(self):
        self.manager.set_active_playlist_by_name(self.dock_widget.get_selected_playlist_name())
        self.initialize_playlist_state()
        pass

    def create_new_playlist(self):
        infos = self.get_playlist_create_info()
        if infos:
            name = infos.get('name')
            p_path = Path(infos.get('p_path'))
            playlist = self.manager.create_playlist(source_path=p_path, name=name)
            self.manager.set_active_playlist(playlist.id)
            self.initialize_playlist_state()
        pass

    def delete_playlist(self):
        selected = self.confirm_delete_playlist_multiple(self.manager.playlist_names.values())
        if selected:
            for playlist_name in selected :
                playlist = self.manager.find_playlist(search_term=playlist_name)
                self.manager.remove_playlist(playlist.id)
                self.dock_widget.remove_playlist_state(playlist)
        self.initialize_playlist_state()
        pass

    def ui_and_api_update(self):
        pass

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

    # Fonction d'interface pour confirmer la suppression
    def confirm_delete_playlist_multiple(self, playlist_names):
        """
        Affiche un widget pour sélectionner et confirmer la suppression de playlists.
        Retourne la liste des playlists sélectionnées, ou une liste vide si annulé.
        """
        dialog = DeletePlaylistDialog(playlist_names, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return dialog.selected_playlists
        return []

    def initialize_playlist_state(self):
        for name,item in self.manager.all_playlist.items() :
            self.dock_widget.add_playlist_state(item)
            self.dock_widget.set_active_playlist(self.manager.active_playlist)
            self.initialize_playlist()
            self.btn_play_mode_initialize()
        pass

    def initialize_playlist(self):
        self.dock_widget.lstw.clear()
        for video in self.active_playlist.all_video:
            self.dock_widget.add_video_to_playlist(video)
            pass
        pass

    # ============================================
    # MÉTHODES DE GESTION DES VIDEOS
    # ============================================
    def add_video_to_playlist(self):
        v_path = self.choose_file()
        if v_path:
            video = self.active_playlist.add_video(Path(v_path))
            self.dock_widget.add_video_to_playlist(video)
        pass

    def remove_video_from_playlist(self):
        """Supprime les vidéos sélectionnées"""
        # Récupérer les noms sélectionnés
        items = self.dock_widget.get_selected_video_names()

        if not items:
            QtWidgets.QMessageBox.information(
                self,
                "Sélection requise",
                "Sélectionnez d'abord une ou plusieurs vidéos.",
                QtWidgets.QMessageBox.StandardButton.Ok
            )
            return

        # Extraire les noms réels des vidéos
        video_names = []
        for item in items:
            video_name = self.dock_widget.extract_video_name_from_listitem(item)
            video_names.append(video_name)

        # Créer le message avec les noms des vidéos
        if len(video_names) == 1:
            # Message pour une seule vidéo
            message = f"Supprimer la vidéo suivante ?\n\n• {video_names[0]}"
            title = "Confirmer la suppression"
        elif len(video_names) <= 5:
            # Afficher tous les noms si 5 ou moins
            videos_list = "\n".join([f"• {name}" for name in video_names])
            message = f"Supprimer les vidéos suivantes ?\n\n{videos_list}"
            title = "Confirmer la suppression multiple"
        else:
            # Afficher les 5 premiers + nombre total si plus de 5
            videos_list = "\n".join([f"• {name}" for name in video_names[:5]])
            message = f"Supprimer les {len(video_names)} vidéos suivantes ?\n\n{videos_list}\n... et {len(video_names) - 5} autres"
            title = "Confirmer la suppression multiple"

        # Boîte de dialogue de confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            title,
            message,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )

        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return  # Annuler la suppression

        # Supprimer chaque vidéo
        for item in items:
            # Extraire le nom réel de la vidéo
            video_name = self.dock_widget.extract_video_name_from_listitem(item)
            # Chercher la vidéo
            found_videos = self.active_playlist.find_videos_by_name(video_name, case_sensitive=True)

            if found_videos:
                video = found_videos[0]
                # Supprimer de la playlist
                self.active_playlist.remove_video(video)
                # Supprimer de l'interface
                self.dock_widget.remove_video_from_playlist(item)

        # Message de confirmation finale (optionnel)
        if len(items) > 1:
            QtWidgets.QMessageBox.information(
                self,
                "Suppression terminée",
                f"{len(items)} vidéos ont été supprimées de la playlist.",
                QtWidgets.QMessageBox.StandardButton.Ok
            )

    def current_video_update_metadata(self,status):
        if not status == QtMultimedia.QMediaPlayer.MediaStatus.LoadedMedia:
            return
        player = self.player_widget.video_player
        self.current_video.update_metadata(duration = player.duration())
        print(self.current_video)
        pass

    def on_playback_state_changed(self, state):
        if state == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
            # Attendre quelques frames pour que la vidéo soit décodée
            QtCore.QTimer.singleShot(100, self._update_video_resolution)

    def _update_video_resolution(self):
        """Récupère la résolution après que la vidéo ait commencé à jouer."""
        # Maintenant width()/height() devraient être corrects
        width = self.player_widget.video_output.width()
        height = self.player_widget.video_output.height()
        self.current_video.update_metadata(
            width=width,
            height=height
        )
        print(self.current_video)
        pass

    def save_video_on_position_changed(self, position):
        """Appelé par positionChanged du player."""
        player_widget = self.player_widget
        if not position == self.current_video.duration:
            self.position_timer.setSingleShot(True)
            if not self.position_timer.isActive():
                self.position_timer.start(2500)
                self.active_playlist.update_current_video_state(
                    position=position,
                    playing= player_widget.video_player.isPlaying(),
                    volume= player_widget.audio_output.volume(),
                    muted= player_widget.audio_output.isMuted()
                )
            return
        self.active_playlist.update_current_video_state(
            position=position,
            playing=player_widget.video_player.isPlaying(),
            volume=player_widget.audio_output.volume(),
            muted=player_widget.audio_output.isMuted()
        )
        return

    # ============================================
    # MÉTHODES DE GESTION DES LECTURES
    # ============================================

    def playlist_play_mode_update(self):
        self.active_playlist.set_play_mode(self.toolbar_widget.player_controls.play_mode)

    def btn_play_mode_initialize(self):
        self.toolbar_widget.player_controls.play_mode = self.active_playlist.play_mode
        self.toolbar_widget.player_controls.btn_play_mode_init()
        pass

    def play_or_pause(self):
        """Joue ou met en pause la vidéo en fonction de l'état du lecteur"""
        player = self.player_widget.video_player
        print(self.toolbar_widget.player_controls.play_mode == self.active_playlist.play_mode)
        print(self.toolbar_widget.player_controls.play_mode)

        # Si déjà en lecture, mettre en pause
        if player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
            player.pause()
            return

        # Si en pause, mettre en lecture
        elif player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.PausedState:
            player.play()
            return

        # Vérifier si une vidéo est sélectionnée

        #Sinon charger une vidéo et jouée.
        if not self.current_video:
            QtWidgets.QMessageBox.warning(
                self,
                "Aucune vidéo sélectionnée",
                "Veuillez d'abord sélectionner une vidéo dans la playlist.",
                QtWidgets.QMessageBox.StandardButton.Ok
            )
            return

        # Vérifier si le fichier existe
        if not self.current_video.file_path.exists():
            QtWidgets.QMessageBox.critical(
                self,
                "Fichier introuvable",
                f"Le fichier n'existe pas :\n{self.current_video.file_path}",
                QtWidgets.QMessageBox.StandardButton.Ok
            )
            return

        # Enfin, charger et jouer
        self.play_video()
        pass

    def stop_playing(self):
        player = self.player_widget.video_player
        player.stop()
        pass

    def next_video(self):
        self.active_playlist.get_next_video()
        self.play_video()

    def previous_video(self):
        self.active_playlist.get_previous_video()
        self.play_video()

    def play_video(self):
        player = self.player_widget.video_player
        video_url = QtCore.QUrl.fromLocalFile(str(self.current_video.file_path))
        player.setSource(video_url)
        if 1000 < self.current_video.state.position < self.current_video.state.duration:
            self.player_widget.video_player.setPosition(self.current_video.state.position)
        player.play()

    def btn_play_pause_update(self, status=None):
        """
        Met à jour l'état du bouton play/pause en fonction du statut du média
        et de l'état de lecture du player.

        Args:
            status: Statut du média ou état de lecture
        """
        # Déterminer si on a reçu un status ou un player_state
        player_state = None

        if status is None:
            # Récupérer l'état actuel du média
            media_status = self.player_widget.video_player.mediaStatus()
            player_state = self.player_widget.video_player.playbackState()

            # Si le média est terminé, forcer l'état "Stopped"
            if media_status == QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia:
                player_state = QtMultimedia.QMediaPlayer.PlaybackState.StoppedState

        elif isinstance(status, QtMultimedia.QMediaPlayer.MediaStatus):
            # On a reçu un statut de média
            media_status = status
            player_state = self.player_widget.video_player.playbackState()

            # Si le média est terminé, forcer l'état "Stopped"
            if media_status == QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia:
                player_state = QtMultimedia.QMediaPlayer.PlaybackState.StoppedState

        elif isinstance(status, QtMultimedia.QMediaPlayer.PlaybackState):
            # On a directement reçu un état de lecture
            player_state = status

        # Si aucun média n'est chargé, ne rien faire
        if (self.player_widget.video_player.mediaStatus() ==
                QtMultimedia.QMediaPlayer.MediaStatus.NoMedia):
            return

        # Mettre à jour les boutons avec l'état déterminé
        if hasattr(self, 'toolbar_widget') and hasattr(self.toolbar_widget.player_controls,
                                                       'btn_play_pause_update'):
            self.toolbar_widget.player_controls.btn_play_pause_update(player_state)

        if hasattr(self, 'menubar_widget') and hasattr(self.menubar_widget, 'play_pause_update'):
            self.menubar_widget.play_pause_update(player_state)

    pass