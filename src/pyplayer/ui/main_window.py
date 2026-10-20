from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6 import QtCore, QtGui, QtMultimedia, QtWidgets

from pyplayer import APP_NAME
from pyplayer.api import media, paths
from pyplayer.api.manager import PlaylistManager
from pyplayer.api.media import format_duration, format_size
from pyplayer.api.playlist import PlayMode, Playlist
from pyplayer.api.subtitles import SubtitleTrack, find_sidecar, load_subtitle_file
from pyplayer.api.video import Video
from pyplayer.ui import theme
from pyplayer.ui.dialogs import AboutDialog, MediaInfoDialog, NewPlaylistDialog
from pyplayer.ui.power import SleepInhibitor
from pyplayer.ui.widget.dock_widget import DeletePlaylistDialog, DockWidget, VideoListItem
from pyplayer.ui.widget.menu_bar import HelpDialog, MenuBarWidget
from pyplayer.ui.widget.player import PlayerWidget
from pyplayer.ui.widget.staturbar_widget import StatusBar
from pyplayer.ui.widget.tool_bar import ToolBarWidget

logger = logging.getLogger(__name__)

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")  # doit être défini avant la création du premier lecteur

SPEEDS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 4.0)
FLUSH_INTERVAL_MS = 5_000
CURSOR_HIDE_MS = 3_000
RESTART_THRESHOLD_MS = 3_000     # « précédent » après 3 s : on recommence la vidéo en cours
VOLUME_STEP = 2
WHEEL_VOLUME_STEP = 5
MediaStatus = QtMultimedia.QMediaPlayer.MediaStatus
PlaybackState = QtMultimedia.QMediaPlayer.PlaybackState
MEDIA_FILTER = ("Médias (" + " ".join(f"*{e}" for e in sorted(media.MEDIA_EXTENSIONS)) + ");;Tous les fichiers (*.*)")


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, manager: PlaylistManager | None = None):
        super().__init__()
        self.manager = manager or PlaylistManager()
        self.settings = self.manager.settings
        self.resume = self.manager.resume
        self.inhibitor = SleepInhibitor()

        self._loaded_video: Video | None = None   # média réellement chargé dans le lecteur
        self._resume_target = 0                    # position de reprise à appliquer au chargement
        self._resume_ready = False                 # tant que faux, on n'enregistre pas la position
        self._resume_seeking = False               # reprise demandée, pas encore atteinte par le lecteur
        self._error_streak = 0
        self._ab_a: int | None = None
        self._ab_b: int | None = None
        self._subtitles: SubtitleTrack | None = None
        self._rate = 1.0
        self._was_maximized = False
        self._dock_visible_before_fullscreen = True

        self.setup_ui()
        self.apply_settings()
        self.initialize_playlist_state()

    # ===================================================================
    # CONSTRUCTION DE L'INTERFACE (mise en page identique aux versions précédentes)
    # ===================================================================
    def setup_ui(self):
        self.customize_self()
        self.create_widgets()
        self.modify_widgets()
        self.setup_connections()

    def customize_self(self):
        self.setWindowIcon(theme.app_icon())
        self.setWindowTitle(APP_NAME)
        self.resize(1000, 600)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.setProperty("theme", "néon")
        self.setStyleSheet(f"background: {theme.SECONDARY_COLOR};")
        self.setAcceptDrops(True)

    def create_widgets(self):
        self.player_widget = PlayerWidget()
        self.setCentralWidget(self.player_widget)
        self.menubar_widget = MenuBarWidget(self)
        self.setMenuBar(self.menubar_widget)
        self.toolbar_widget = ToolBarWidget(self)
        self.addToolBar(QtCore.Qt.ToolBarArea.BottomToolBarArea, self.toolbar_widget)
        self.dock_widget = DockWidget()
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.setObjectName("playlist_dock")
        self.toolbar_widget.setObjectName("main_toolbar")
        self.statusbar_widget = StatusBar(self)
        self.setStatusBar(self.statusbar_widget)

        self.audio_output = self.player_widget.audio_output
        self.player = self.player_widget.video_player

        # Les actions des menus sont aussi enregistrées sur la fenêtre : leurs raccourcis restent actifs
        # quand la barre de menu est masquée (plein écran).
        for action in self.menubar_widget.all_actions():
            action.setShortcutContext(QtCore.Qt.ShortcutContext.WindowShortcut)
            self.addAction(action)

    def modify_widgets(self):
        self.toolbar_widget.setMovable(False)
        # Les boutons ne prennent pas le focus clavier : Espace, flèches et molette vont toujours à la fenêtre.
        for button in self.toolbar_widget.player_controls.btn_list:
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        for widget in (self.toolbar_widget.btn_playlist, self.toolbar_widget.volume_widget.btn,
                       self.toolbar_widget.volume_widget.slider, self.player_widget.slider):
            widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.menubar_widget.act_stop.setEnabled(False)
        self.toolbar_widget.player_controls.btn_stop.setEnabled(False)
        self.player_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)

        self._flush_timer = QtCore.QTimer(self)
        self._flush_timer.setInterval(FLUSH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self.manager.flush)
        self._flush_timer.start()

        self._resume_timer = QtCore.QTimer(self)    # filet de sécurité si le lecteur n'atteint jamais la position
        self._resume_timer.setSingleShot(True)
        self._resume_timer.setInterval(3000)
        self._resume_timer.timeout.connect(self._finish_resume_seek)

        self._cursor_timer = QtCore.QTimer(self)
        self._cursor_timer.setSingleShot(True)
        self._cursor_timer.setInterval(CURSOR_HIDE_MS)
        self._cursor_timer.timeout.connect(self._hide_fullscreen_controls)

    def setup_connections(self):
        m = self.menubar_widget
        d = self.dock_widget
        t = self.toolbar_widget
        pc = t.player_controls
        p = self.player

        # Menu Fichier
        m.act_app_exit.triggered.connect(self.close)
        m.act_open_now.triggered.connect(self.open_file_now)
        m.act_open_file.triggered.connect(self.add_video_to_playlist)
        m.act_open_folder.triggered.connect(self.choose_folder)
        m.act_open_url.triggered.connect(self.open_url_dialog)
        m.recentMenu.aboutToShow.connect(self.fill_recent_menu)
        m.act_import_playlist.triggered.connect(self.import_playlist_file)
        m.act_export_playlist.triggered.connect(self.export_playlist_file)

        # Menu Lecture
        m.act_play.triggered.connect(self.play_or_pause)
        m.act_stop.triggered.connect(self.stop_playing)
        m.act_skip_next.triggered.connect(self.next_video)
        m.act_skip_previous.triggered.connect(self.previous_video)
        m.speed_group.triggered.connect(lambda action: self.set_speed(action.data()))
        m.act_speed_up.triggered.connect(lambda: self.step_speed(+1))
        m.act_speed_down.triggered.connect(lambda: self.step_speed(-1))
        m.act_speed_reset.triggered.connect(lambda: self.set_speed(1.0))
        m.act_mute.triggered.connect(self.toggle_mute)
        m.act_ab_loop.triggered.connect(self.cycle_ab_loop)
        m.act_goto_time.triggered.connect(self.goto_time_dialog)
        m.audioTrackMenu.aboutToShow.connect(self.fill_audio_menu)
        m.act_next_audio.triggered.connect(self.next_audio_track)
        m.subtitleMenu.aboutToShow.connect(self.fill_subtitle_menu)
        m.act_next_subtitle.triggered.connect(self.next_subtitle)
        m.act_subtitle_earlier.triggered.connect(lambda: self.shift_subtitles(-100))
        m.act_subtitle_later.triggered.connect(lambda: self.shift_subtitles(+100))
        m.audioDeviceMenu.aboutToShow.connect(self.fill_audio_device_menu)
        m.aspect_group.triggered.connect(lambda action: self.set_aspect_mode(action.data()))
        m.act_screenshot.triggered.connect(self.take_screenshot)
        m.act_full_screen_mode.triggered.connect(self.toggle_fullscreen)
        m.act_always_on_top.toggled.connect(self.set_always_on_top)

        # Menu Playlist
        m.act_show_playlist.triggered.connect(self.playlist_show_or_hide)
        m.act_save_playlist_state.triggered.connect(self.create_new_playlist)
        m.act_rename_playlist.triggered.connect(self.rename_playlist)
        m.act_remove_playlist_state.triggered.connect(self.delete_playlist)
        m.act_refresh_source.triggered.connect(self.refresh_from_source)
        for key, action in m.sort_actions.items():
            action.triggered.connect(lambda _checked=False, k=key: self.sort_playlist(k))
        m.act_remove_missing.triggered.connect(self.remove_missing_files)

        # Menu Support
        m.act_media_info.triggered.connect(self.show_media_info)
        m.act_reveal_file.triggered.connect(self.reveal_current_file)
        m.act_help.triggered.connect(self.show_help_dialog)
        m.act_open_logs.triggered.connect(self.open_log_folder)
        m.act_about.triggered.connect(self.about_pyplayer)

        # Raccourcis spécifiques à la fenêtre
        self.shortcut_escape = QtGui.QShortcut(QtGui.QKeySequence("Escape"), self)
        self.shortcut_escape.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        self.shortcut_escape.activated.connect(self.exit_fullscreen)
        for key, slot in (("Alt+Up", lambda: self.move_selected(-1)), ("Alt+Down", lambda: self.move_selected(+1)),
                          ("Delete", self.remove_video_from_playlist)):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), d.lstw)
            shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(slot)
        for key, slot in (("Media Play", self.play_or_pause), ("Media Next", self.next_video),
                          ("Media Previous", self.previous_video), ("Media Stop", self.stop_playing),
                          ("Volume Mute", self.toggle_mute)):
            QtGui.QShortcut(QtGui.QKeySequence(key), self, slot)

        # Panneau de playlist
        d.btn_add_to_playlist.clicked.connect(self.add_video_to_playlist)
        d.btn_remove_to_playlist.clicked.connect(self.remove_video_from_playlist)
        d.btn_save_playlist.clicked.connect(self.create_new_playlist)
        d.btn_remove_save.clicked.connect(self.delete_playlist)
        d.lstw_archive.itemSelectionChanged.connect(self.set_manually_active_playlist)
        d.lstw.itemDoubleClicked.connect(self.double_click)
        d.lstw.rows_move_requested.connect(self.on_rows_move_requested)
        d.lstw.context_menu_requested.connect(self.show_playlist_context_menu)
        d.lstw.files_dropped.connect(lambda items: self.open_paths(items, enqueue=True))
        d.visibilityChanged.connect(self._sync_playlist_toggle_text)

        # Barre d'outils
        t.btn_playlist.clicked.connect(self.playlist_show_or_hide)
        pc.play_mode_changed.connect(self.playlist_play_mode_update)
        pc.btn_play_pause.clicked.connect(self.play_or_pause)
        pc.btn_stop.clicked.connect(self.stop_playing)
        pc.btn_skipnext.clicked.connect(self.next_video)
        pc.btn_skipprevious.clicked.connect(self.previous_video)
        t.volume_widget.btn.clicked.connect(self.toggle_mute)
        t.volume_widget.slider.valueChanged.connect(self.update_volume_change)

        # Lecteur
        pw = self.player_widget
        pw.clicked.connect(self.play_or_pause)
        pw.signal_double_click.connect(self.toggle_fullscreen)
        pw.wheel_volume.connect(lambda direction: self.change_volume(direction * WHEEL_VOLUME_STEP))
        pw.mouse_moved.connect(self._on_mouse_activity)
        pw.context_menu_requested.connect(self.show_player_context_menu)
        p.mediaStatusChanged.connect(self.on_media_status_changed)
        p.playbackStateChanged.connect(self.on_playback_state_changed)
        p.positionChanged.connect(self.on_position_changed)
        p.errorOccurred.connect(self.on_player_error)
        p.playbackRateChanged.connect(lambda _r: self._update_status_info())

    ##################### END UI ######################

    # ===================================================================
    # ÉTAT / PERSISTANCE
    # ===================================================================
    @property
    def active_playlist(self) -> Playlist:
        return self.manager.active

    @property
    def current_video(self) -> Video | None:
        """Vidéo sélectionnée dans la playlist active (lecture seule, sans effet de bord)."""
        return self.active_playlist.current

    def apply_settings(self):
        s = self.settings
        geometry = s.get("window_geometry")
        if geometry:
            self.restoreGeometry(QtCore.QByteArray.fromBase64(geometry.encode("ascii")))
        state = s.get("window_state")
        if state:
            self.restoreState(QtCore.QByteArray.fromBase64(state.encode("ascii")))
        self.dock_widget.setVisible(bool(s.get("playlist_panel_visible")))
        self._sync_playlist_toggle_text()

        self.set_aspect_mode(s.get("aspect_mode"), save=False)
        self.menubar_widget.act_always_on_top.setChecked(bool(s.get("always_on_top")))

        volume = self.manager.volume
        self.audio_output.setVolume(volume)          # valeur explicite : plus de dépendance au signal du slider
        self.toolbar_widget.volume_widget.set_volume(round(volume * 100))
        self._apply_muted(bool(s.get("muted")))
        self._restore_audio_device()

    def save_window_state(self):
        if self.isFullScreen():
            return
        self.settings.set("window_geometry", bytes(self.saveGeometry().toBase64()).decode("ascii"))
        self.settings.set("window_state", bytes(self.saveState().toBase64()).decode("ascii"))
        self.settings.set("playlist_panel_visible", self.dock_widget.isVisible())

    def closeEvent(self, event):
        self._record_position()
        self.save_window_state()
        self.manager.flush()
        self.inhibitor.set_active(False)
        self.unload_media()
        super().closeEvent(event)

    def flash(self, message: str, timeout_ms: int = 4000):
        """Message temporaire dans la barre d'état."""
        self.statusBar().showMessage(message, timeout_ms)

    # ===================================================================
    # PLAYLISTS (panneau de droite)
    # ===================================================================
    def initialize_playlist_state(self):
        playlist = self.active_playlist
        self.dock_widget.sync_playlists(self.manager.playlists)
        self.dock_widget.set_active_playlist(playlist)
        self.refresh_playlist_view()
        self.toolbar_widget.player_controls.set_play_mode(playlist.play_mode)
        self._update_menu_state()

    def refresh_playlist_view(self):
        playlist = self.active_playlist
        self.dock_widget.populate(playlist.videos, self.resume, playlist.current)
        if self._loaded_video is not None:
            self.dock_widget.set_current_video(self._loaded_video if self._loaded_video in playlist else playlist.current)

    def set_manually_active_playlist(self):
        playlist_id = self.dock_widget.get_selected_playlist_id()
        if not playlist_id or playlist_id == self.active_playlist.id:
            return
        if self.manager.set_active(playlist_id):
            self.initialize_playlist_state()

    def playlist_show_or_hide(self):
        self.dock_widget.setVisible(not self.dock_widget.isVisible())

    def _sync_playlist_toggle_text(self, *_):
        visible = self.dock_widget.isVisible()
        text = "Masquer le panneau des playlists" if visible else "Afficher le panneau des playlists"
        self.toolbar_widget.btn_playlist.setToolTip(f"<b style='color:#f2f2f7;font-weight:bold;'>{text}</b>")
        self.menubar_widget.act_show_playlist.setText(text)

    def create_new_playlist(self):
        dialog = NewPlaylistDialog(self, self.settings.get("last_open_dir"))
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        data = dialog.result_data()
        self.settings.set("last_open_dir", str(data["path"]))
        self.create_playlist_from(data["name"], data["path"], data["description"])

    def create_playlist_from(self, name: str, folder: Path, description: str = "") -> Playlist:
        playlist = self.manager.create_playlist(name=name, source_path=folder, description=description)
        self.manager.set_active(playlist.id)
        self.initialize_playlist_state()
        self.flash(f"Playlist « {playlist.name} » créée ({len(playlist)} médias)")
        return playlist

    def rename_playlist(self):
        playlist = self.active_playlist
        name, ok = QtWidgets.QInputDialog.getText(self, "Renommer la playlist", "Nouveau nom :", text=playlist.name)
        if ok and name.strip() and self.manager.rename(playlist.id, name):
            self.dock_widget.rename_playlist_state(playlist)

    def delete_playlist(self):
        choices = [(p.id, p.name) for p in self.manager]
        dialog = DeletePlaylistDialog(choices, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted or not dialog.selected_playlists:
            return
        self.remove_playlists(dialog.selected_playlists)

    def remove_playlists(self, playlist_ids: list[str]) -> int:
        """Supprime des playlists ; une playlist reste toujours active."""
        if self.active_playlist.id in playlist_ids:
            self.stop_playing()
            self._loaded_video = None
        removed = sum(1 for playlist_id in playlist_ids if self.manager.remove_playlist(playlist_id))
        self.initialize_playlist_state()
        self.flash(f"{removed} playlist(s) supprimée(s)")
        return removed

    def playlist_play_mode_update(self, mode: PlayMode):
        self.active_playlist.set_mode(mode)

    def refresh_from_source(self):
        playlist = self.active_playlist
        if playlist.source is None:
            self.flash("Cette playlist n'est liée à aucun dossier")
            return
        added = playlist.refresh_from_source()
        self.manager.flush()
        self.refresh_playlist_view()
        self.flash(f"{len(added)} nouveau(x) média(s) ajouté(s)" if added else "Aucun nouveau média")

    def sort_playlist(self, key: str):
        playlist = self.active_playlist
        playlist.sort(key, reverse=self.menubar_widget.act_sort_reverse.isChecked())
        self.refresh_playlist_view()

    def remove_missing_files(self):
        removed = self.active_playlist.remove_missing()
        self.refresh_playlist_view()
        self.flash(f"{len(removed)} fichier(s) introuvable(s) retiré(s)")

    def import_playlist_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Importer une playlist", self.settings.get("last_open_dir"),
            "Playlists (*.m3u *.m3u8 *.pls);;Tous les fichiers (*.*)")
        if not file_path:
            return
        try:
            playlist = self.manager.import_playlist_file(file_path)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "Import impossible", str(error))
            return
        self.manager.set_active(playlist.id)
        self.initialize_playlist_state()
        self.flash(f"Playlist « {playlist.name} » importée ({len(playlist)} médias)")

    def export_playlist_file(self):
        playlist = self.active_playlist
        default = str(Path(self.settings.get("last_open_dir") or Path.home()) / f"{playlist.name}.m3u8")
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter la playlist", default,
                                                             "Playlist M3U8 (*.m3u8);;Playlist M3U (*.m3u)")
        if not file_path:
            return
        try:
            self.manager.export_playlist(playlist, file_path)
            self.flash(f"Playlist exportée : {file_path}")
        except OSError as error:
            QtWidgets.QMessageBox.warning(self, "Export impossible", str(error))

    # ===================================================================
    # OUVERTURE DE FICHIERS (menu, ligne de commande, « Ouvrir avec », glisser-déposer)
    # ===================================================================
    def choose_file(self) -> list[str]:
        start = self.settings.get("last_open_dir") or QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.StandardLocation.MoviesLocation)
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Sélectionner des fichiers vidéo ou audio", start,
                                                          MEDIA_FILTER)
        if files:
            self.settings.set("last_open_dir", str(Path(files[0]).parent))
        return files

    def choose_folder(self):
        """Ajoute un dossier (récursif) à la playlist active. Annuler ne fait rien."""
        start = self.settings.get("last_open_dir") or str(Path.home())
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier", start,
            QtWidgets.QFileDialog.Option.ShowDirsOnly | QtWidgets.QFileDialog.Option.DontResolveSymlinks)
        if not folder:
            return False
        self.settings.set("last_open_dir", folder)
        self.open_paths([folder], enqueue=True)
        return True

    def add_video_to_playlist(self):
        files = self.choose_file()
        if files:
            self.open_paths(files, enqueue=True)

    def open_file_now(self):
        files = self.choose_file()
        if files:
            self.open_paths(files, enqueue=False)

    def open_url_dialog(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "Ouvrir une adresse réseau",
                                                  "Adresse du flux (http, https, rtsp…) :")
        text = text.strip()
        if ok and text:
            self.open_url(QtCore.QUrl.fromUserInput(text))

    def open_url(self, url: QtCore.QUrl):
        """Lit un flux distant directement (non ajouté aux playlists)."""
        self._record_position()
        self._loaded_video = None
        self._resume_target, self._resume_ready = 0, False
        self.player.setSource(url)
        self.player.play()
        self.statusbar_widget.lbl_title.setText(f"     🌐  {url.toString()}")
        self.setWindowTitle(f"{url.fileName() or url.host()} — {APP_NAME}")

    def open_paths(self, raw_paths, *, enqueue: bool = False):
        """Point d'entrée unique pour tout ce qui est « ouvert ».

        ``enqueue=False`` : lecture immédiate (playlist « Lecture rapide » remplacée).
        ``enqueue=True`` : ajout à la playlist active sans lancer la lecture.
        """
        files: list[Path] = []
        imported: Playlist | None = None
        for raw in raw_paths:
            path = Path(raw)
            if path.is_dir():
                files.extend(media.scan_folder(path))
            elif media.is_playlist_file(path):
                try:
                    imported = self.manager.import_playlist_file(path)
                except (OSError, ValueError) as error:
                    self.flash(f"Playlist illisible : {error}")
            elif path.is_file() and media.is_media(path):
                files.append(path)
            else:
                self.flash(f"Ignoré : {path.name}")

        if imported is not None and not files:
            self.manager.set_active(imported.id)
            self.initialize_playlist_state()
            if not enqueue and imported.ensure_current():
                self.play_video(imported.current)
            return
        if not files:
            return

        if enqueue:
            playlist = self.active_playlist
            added = playlist.add_many(files)
            self.manager.flush()
            if len(added) > 25:
                self.refresh_playlist_view()          # une seule reconstruction pour un gros lot
            else:
                for video in added:
                    self.dock_widget.add_video_to_playlist(video, self.resume)
            self.flash(f"{len(added)} média(s) ajouté(s)" + (f" ({len(files) - len(added)} déjà présent(s))"
                                                          if len(added) < len(files) else ""))
            return

        # Lecture immédiate
        playlist = self.manager.quick_playlist()
        playlist.clear()
        first = files[0]
        if len(files) == 1 and self.settings.get("open_siblings"):
            files = media.sibling_media(first) or files
        playlist.add_many(files)
        target = playlist.find(first) or (playlist[0] if len(playlist) else None)
        self.manager.set_active(playlist.id)
        if target is None:
            return
        playlist.set_current(target, remember=False)
        self.initialize_playlist_state()
        self.play_video(target)
        self.activateWindow()
        self.raise_()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        dropped = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if dropped:
            self.open_paths(dropped, enqueue=False)
            event.acceptProposedAction()

    def fill_recent_menu(self):
        menu = self.menubar_widget.recentMenu
        menu.clear()
        recent = [p for p in self.settings.get("recent_files") if Path(p).exists()]
        for path in recent:
            action = menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda _c=False, p=path: self.open_paths([p], enqueue=False))
        if not recent:
            menu.addAction("(aucun)").setEnabled(False)
        else:
            menu.addSeparator()
            menu.addAction("Effacer la liste").triggered.connect(self.settings.clear_recent)

    # ===================================================================
    # SUPPRESSION / RÉORDONNANCEMENT DANS LA LISTE
    # ===================================================================
    def remove_video_from_playlist(self):
        """Retire les médias sélectionnés de la playlist (les fichiers ne sont jamais supprimés du disque)."""
        videos = self.dock_widget.get_selected_videos()
        if not videos:
            QtWidgets.QMessageBox.information(
                self, "Sélection requise", "Sélectionnez d'abord une ou plusieurs vidéos.",
                QtWidgets.QMessageBox.StandardButton.Ok)
            return

        names = [v.name for v in videos]
        if len(names) == 1:
            message, title = f"Retirer la vidéo suivante de la playlist ?\n\n• {names[0]}", "Confirmer la suppression"
        else:
            shown = "\n".join(f"• {n}" for n in names[:5])
            more = f"\n... et {len(names) - 5} autres" if len(names) > 5 else ""
            message, title = (f"Retirer les {len(names)} vidéos suivantes de la playlist ?\n\n{shown}{more}",
                              "Confirmer la suppression multiple")

        if not self.confirm(title, message, "Les fichiers restent sur le disque."):
            return
        self.remove_videos(videos)

    def confirm(self, title: str, message: str, informative: str = "") -> bool:
        """Question Oui/Non (« Non » par défaut). Isolée pour pouvoir être remplacée dans les tests."""
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        if informative:
            box.setInformativeText(informative)
        box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        yes_button = box.addButton("Oui", QtWidgets.QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton("Non", QtWidgets.QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button)
        box.exec()
        return box.clickedButton() is yes_button

    def remove_videos(self, videos: list[Video]) -> int:
        """Retire des médias de la playlist active (arrête la lecture si l'un d'eux est en cours)."""
        if self._loaded_video is not None and any(v is self._loaded_video for v in videos):
            self.stop_playing()
            self._loaded_video = None
        removed = self.active_playlist.remove_many(videos)
        self.manager.flush()
        for video in videos:
            self.dock_widget.remove_video_from_playlist(video)
        self.flash(f"{removed} média(s) retiré(s) de la playlist")
        return removed

    def move_selected(self, direction: int):
        """Alt+↑ / Alt+↓ : déplace la sélection d'un cran."""
        playlist = self.active_playlist
        selected = self.dock_widget.get_selected_videos()
        if not selected:
            return
        order = list(playlist.videos)
        indexes = sorted(playlist.index_of(v) for v in selected)
        if direction < 0 and indexes[0] == 0 or direction > 0 and indexes[-1] == len(order) - 1:
            return
        for index in (indexes if direction < 0 else reversed(indexes)):
            order[index], order[index + direction] = order[index + direction], order[index]
        playlist.reorder(order)
        self.refresh_playlist_view()
        for video in selected:
            item = self.dock_widget.find_item(video)
            if item:
                item.setSelected(True)

    def on_rows_move_requested(self, rows: list[int], target: int):
        """Glisser-déposer dans la liste : calcule le nouvel ordre et le fait appliquer par la playlist."""
        playlist = self.active_playlist
        moved = [playlist[r] for r in rows if 0 <= r < len(playlist)]
        if not moved:
            return
        before = [v for i, v in enumerate(playlist.videos) if i < target and i not in rows]
        after = [v for i, v in enumerate(playlist.videos) if i >= target and i not in rows]
        playlist.reorder(before + moved + after)
        self.refresh_playlist_view()
        for video in moved:
            item = self.dock_widget.find_item(video)
            if item:
                item.setSelected(True)

    def double_click(self, item):
        if isinstance(item, VideoListItem):
            self.active_playlist.set_current(item.video)
            self.play_video(item.video)

    # ===================================================================
    # LECTURE
    # ===================================================================
    def play_video(self, video: Video | None = None, *, silent_if_missing: bool = False):
        """Charge et lit ``video`` (par défaut la vidéo courante de la playlist active)."""
        playlist = self.active_playlist
        video = video or playlist.ensure_current()
        if video is None:
            self.flash("Aucune vidéo à lire : ajoutez des fichiers à la playlist")
            return
        if not video.exists():
            self.dock_widget.refresh_missing()
            if not silent_if_missing:
                QtWidgets.QMessageBox.critical(
                    self, "Fichier introuvable", f"Le fichier n'existe pas :\n{video.path}",
                    QtWidgets.QMessageBox.StandardButton.Ok)
            else:
                self.flash(f"Fichier introuvable : {video.name}")
            return

        self._record_position()                       # mémorise l'endroit où l'on quitte le média précédent
        self._loaded_video = video
        if playlist.current is not video:
            playlist.set_current(video, remember=False)
        self._resume_target = self.resume.position(video.path) if self.settings.get("resume_playback") else 0
        self._resume_ready = False
        self._resume_seeking = False
        self._resume_timer.stop()
        self._clear_ab_loop(silent=True)
        self._load_sidecar_subtitles(video)

        self.player.setSource(QtCore.QUrl.fromLocalFile(str(video.path)))
        self.player.setPlaybackRate(self._rate)
        self.player.play()

        self.settings.add_recent(video.path)
        self.dock_widget.set_current_video(video)
        self._update_titles()

    def play_or_pause(self):
        """Joue ou met en pause (relance la vidéo courante si le lecteur est arrêté)."""
        state = self.player.playbackState()
        if state == PlaybackState.PlayingState:
            self.player.pause()
        elif state == PlaybackState.PausedState:
            self.player.play()
        else:
            self.play_video()

    def unload_media(self):
        """Arrête et décharge le média. On passe par ``setSource(QUrl())`` plutôt que ``QMediaPlayer.stop()`` :
        avec le backend FFmpeg de Qt 6, ``stop()`` se bloque définitivement par intermittence (reproduit avec Qt seul :
        0 série sur 4 de 150 itérations aboutit avec ``stop()``, 4 sur 4 avec ``setSource(QUrl())``)."""
        self.player.setSource(QtCore.QUrl())

    def stop_playing(self):
        if self.player.playbackState() == PlaybackState.StoppedState and self.player.mediaStatus() == MediaStatus.NoMedia:
            return
        self._record_position()
        self._resume_ready = False        # le retour de la position à 0 ne doit pas effacer la reprise qu'on vient d'enregistrer
        self._resume_seeking = False
        self._resume_timer.stop()
        self.unload_media()
        self.player_widget.slider.setValue(0)
        self.toolbar_widget.time_label.set_times(current_time="00:00:00")
        self.player_widget.set_subtitle_text("")

    def next_video(self):
        playlist = self.active_playlist
        video = playlist.next()
        if video is None:
            self.flash("Fin de la playlist")
            return
        self.play_video(video)

    def previous_video(self):
        if self.player.position() > RESTART_THRESHOLD_MS and self.player.playbackState() != PlaybackState.StoppedState:
            self.player.setPosition(0)
            return
        video = self.active_playlist.previous()
        if video is None:
            self.player.setPosition(0)
            return
        self.play_video(video)

    def on_media_status_changed(self, status):
        if status == MediaStatus.LoadedMedia:
            self._on_media_loaded()
        elif status == MediaStatus.EndOfMedia:
            self._on_media_ended()
        elif status == MediaStatus.InvalidMedia:
            self._on_media_invalid()

    def _on_media_loaded(self):
        video = self._loaded_video
        self._error_streak = 0
        duration = self.player.duration()
        self.toolbar_widget.time_label.set_times(total_time=self.player_widget.position_to_hms(duration))
        if video is not None:
            size = self._media_resolution()
            changed = video.update_metadata(width=size.width(), height=size.height(), duration=duration)
            if changed:
                self.active_playlist.mark_dirty()
            if self._resume_target > 0 and duration > self._resume_target:
                # Tant que le lecteur n'a pas atteint la position de reprise, ses positions « avant saut »
                # ne doivent pas écraser la mémoire de reprise.
                self._resume_seeking = True
                self._resume_timer.start()
                self.player.setPosition(self._resume_target)
                self.flash(f"Reprise à {format_duration(self._resume_target)}")
                self._update_titles()
                return
        self._resume_ready = True
        self._update_titles()

    def _finish_resume_seek(self):
        self._resume_seeking = False
        self._resume_ready = self._loaded_video is not None
        self._resume_timer.stop()

    def _on_media_ended(self):
        video = self._loaded_video
        if video is not None:
            self.resume.mark_finished(video.path)
            self._update_item_progress(video, 1.0, True)
        self._resume_ready = False
        self._resume_seeking = False

        playlist = self.active_playlist
        nxt = playlist.next(auto=True) if video is not None else None
        if nxt is None:
            self.stop_playing()
            self.player_widget.show_placeholder()
            self.flash("Fin de la playlist")
        elif nxt is video:
            # Boucle sur le fichier : on rembobine sans recharger.
            self.player.setPosition(0)
            self.player.play()
            self._resume_ready = True
        else:
            self.play_video(nxt, silent_if_missing=True)

    def _on_media_invalid(self):
        video = self._loaded_video
        message = self.player.errorString() or "format non pris en charge"
        self.flash(f"Lecture impossible : {video.name if video else ''} — {message}", 6000)
        logger.warning("Média invalide %s : %s", video.path if video else "?", message)
        self._error_streak += 1
        if video is not None and self._error_streak <= len(self.active_playlist):
            QtCore.QTimer.singleShot(600, self._skip_after_error)

    def _skip_after_error(self):
        if self.player.mediaStatus() != MediaStatus.InvalidMedia:
            return
        nxt = self.active_playlist.next(auto=False)
        if nxt is not None and nxt is not self._loaded_video:
            self.play_video(nxt, silent_if_missing=True)

    def on_player_error(self, error, message):
        logger.warning("Erreur lecteur : %s (%s)", message, error)

    def on_playback_state_changed(self, state):
        playing = state == PlaybackState.PlayingState
        self.toolbar_widget.player_controls.set_playing(playing)
        act = self.menubar_widget.act_play
        act.setIcon(theme.icon("pause" if playing else "play"))
        act.setText("Pause" if playing else "Lire")
        stopped = state == PlaybackState.StoppedState
        self.toolbar_widget.player_controls.btn_stop.setEnabled(not stopped)
        self.menubar_widget.act_stop.setEnabled(not stopped)
        self.inhibitor.set_active(playing and self.player.hasVideo())
        if stopped:
            self._update_titles()

    def on_position_changed(self, position: int):
        self.toolbar_widget.time_label.set_times(current_time=self.player_widget.position_to_hms(position))
        if self._ab_b is not None and self._ab_a is not None and position >= self._ab_b:
            self.player.setPosition(self._ab_a)
            return
        if self._subtitles is not None:
            self.player_widget.set_subtitle_text(self._subtitles.text_at(position))
        if self._resume_seeking and abs(position - self._resume_target) <= 1500:
            self._finish_resume_seek()
        if self._resume_ready:
            self._record_position(position)

    def _record_position(self, position: int | None = None):
        """Enregistre où l'on en est dans le média chargé (jamais dans « la vidéo courante » de la playlist)."""
        video = self._loaded_video
        if video is None or not self._resume_ready:
            return
        position = self.player.position() if position is None else position
        duration = self.player.duration() or video.duration
        self.resume.update(video.path, position, duration)
        self._update_item_progress(video, self.resume.progress(video.path, duration), self.resume.is_finished(video.path))

    def _update_item_progress(self, video: Video, progress: float, finished: bool):
        self.dock_widget.update_video_progress(video, progress, finished)

    def _media_resolution(self) -> QtCore.QSize:
        metadata = self.player.metaData()
        try:
            size = metadata.value(QtMultimedia.QMediaMetaData.Key.Resolution)
        except RuntimeError:
            size = None
        if isinstance(size, QtCore.QSize) and size.isValid():
            return size
        sink_size = self.player_widget.video_output.videoSink().videoSize()
        return sink_size if sink_size.isValid() else QtCore.QSize(0, 0)

    def _update_titles(self):
        video = self._loaded_video
        if video is None or self.player.mediaStatus() == MediaStatus.NoMedia:
            self.statusbar_widget.lbl_title.setText("   Pas de média en cours")
            self.setWindowTitle(APP_NAME)
            return
        item = self.dock_widget.find_item(video)
        index = item.index if item else self.active_playlist.index_of(video) + 1
        resolution = video.resolution
        extra = f" ▌ Résolution : {resolution}" if resolution else ""
        self.statusbar_widget.lbl_title.setText(f"     {index} ➤  {video.name}{extra}")
        self.setWindowTitle(f"{video.name} — {APP_NAME}")
        self._update_status_info()

    # ===================================================================
    # VOLUME / SON
    # ===================================================================
    def update_volume_change(self, value: int):
        """Slider de volume → sortie audio (la sauvegarde disque est faite par le timer, pas à chaque cran)."""
        volume = value / 100
        self.audio_output.setVolume(volume)
        self.manager.volume = volume

    def change_volume(self, delta: int):
        if self.audio_output.isMuted():
            self._apply_muted(False)
        self.toolbar_widget.volume_widget.volume_step(delta)
        self.flash(f"Volume : {self.toolbar_widget.volume_widget.slider.value()} %", 1200)

    def toggle_mute(self):
        self._apply_muted(not self.audio_output.isMuted())

    def _apply_muted(self, muted: bool):
        self.audio_output.setMuted(muted)
        self.settings.set("muted", muted)
        self.toolbar_widget.volume_widget.set_muted(muted)
        self.menubar_widget.act_mute.setText("Rétablir le son" if muted else "Couper le son")

    def fill_audio_device_menu(self):
        menu = self.menubar_widget.audioDeviceMenu
        menu.clear()
        group = QtGui.QActionGroup(menu)
        current = self.audio_output.device().id()
        for device in QtMultimedia.QMediaDevices.audioOutputs():
            action = menu.addAction(device.description() + (" (par défaut)" if device.isDefault() else ""))
            action.setCheckable(True)
            action.setChecked(device.id() == current)
            group.addAction(action)
            action.triggered.connect(lambda _c=False, d=device: self.set_audio_device(d))
        if not group.actions():
            menu.addAction("(aucun périphérique détecté)").setEnabled(False)

    def set_audio_device(self, device):
        self.audio_output.setDevice(device)
        default = QtMultimedia.QMediaDevices.defaultAudioOutput()
        self.settings.set("audio_device", "" if device.id() == default.id() else bytes(device.id().toBase64()).decode())

    def _restore_audio_device(self):
        wanted = self.settings.get("audio_device")
        if not wanted:
            return
        wanted_id = QtCore.QByteArray.fromBase64(wanted.encode("ascii"))
        for device in QtMultimedia.QMediaDevices.audioOutputs():
            if device.id() == wanted_id:
                self.audio_output.setDevice(device)
                return

    # ===================================================================
    # VITESSE, BOUCLE A-B, ALLER À
    # ===================================================================
    def set_speed(self, rate: float):
        rate = float(rate)
        self._rate = rate
        self.player.setPlaybackRate(rate)
        action = self.menubar_widget.speed_actions.get(rate)
        if action:
            action.setChecked(True)
        self.flash(f"Vitesse : {rate:g}×", 1500)
        self._update_status_info()

    def step_speed(self, direction: int):
        index = min(range(len(SPEEDS)), key=lambda i: abs(SPEEDS[i] - self._rate))
        self.set_speed(SPEEDS[max(0, min(len(SPEEDS) - 1, index + direction))])

    def cycle_ab_loop(self):
        if self.player.mediaStatus() in (MediaStatus.NoMedia, MediaStatus.InvalidMedia):
            return
        if self._ab_a is None:
            self._ab_a = self.player.position()
            self.flash(f"Boucle A-B : début A à {format_duration(self._ab_a)}")
        elif self._ab_b is None:
            if self.player.position() <= self._ab_a + 500:
                self.flash("Boucle A-B : B doit être après A")
                return
            self._ab_b = self.player.position()
            self.flash(f"Boucle A-B : {format_duration(self._ab_a)} → {format_duration(self._ab_b)}")
        else:
            self._clear_ab_loop()
        self._update_status_info()

    def _clear_ab_loop(self, silent: bool = False):
        had_loop = self._ab_a is not None
        self._ab_a = self._ab_b = None
        if had_loop and not silent:
            self.flash("Boucle A-B effacée")
        self._update_status_info()

    def goto_time_dialog(self):
        if self.player.duration() <= 0:
            return
        text, ok = QtWidgets.QInputDialog.getText(
            self, "Aller à un instant", "Instant (ex. 90, 1:30 ou 1:02:03) :",
            text=format_duration(self.player.position()))
        if not ok:
            return
        try:
            parts = [float(p) for p in text.strip().split(":")]
            if not 1 <= len(parts) <= 3 or any(p < 0 for p in parts):
                raise ValueError
            seconds = 0.0
            for part in parts:
                seconds = seconds * 60 + part
        except ValueError:
            self.flash("Instant invalide")
            return
        self.player.setPosition(min(int(seconds * 1000), self.player.duration()))

    def _update_status_info(self):
        parts = []
        if abs(self._rate - 1.0) > 1e-6:
            parts.append(f"{self._rate:g}×")
        if self._ab_a is not None:
            parts.append("A-B" if self._ab_b is not None else "A…")
        if self.player.loops() == QtMultimedia.QMediaPlayer.Loops.Infinite:
            parts.append("🔁")
        self.statusbar_widget.set_info("  ".join(parts))

    # ===================================================================
    # PISTES AUDIO / SOUS-TITRES
    # ===================================================================
    @staticmethod
    def _track_label(index: int, track: QtMultimedia.QMediaMetaData) -> str:
        title = track.stringValue(QtMultimedia.QMediaMetaData.Key.Title)
        language = track.stringValue(QtMultimedia.QMediaMetaData.Key.Language)
        label = f"Piste {index + 1}"
        details = " – ".join(x for x in (title, language) if x)
        return f"{label} ({details})" if details else label

    def _set_audio_track(self, index: int) -> bool:
        """Change de piste audio. Sans périphérique de sortie, le backend FFmpeg de Qt se bloque définitivement
        sur ``setActiveAudioTrack`` : on refuse proprement plutôt que de figer l'interface."""
        if not QtMultimedia.QMediaDevices.audioOutputs():
            self.flash("Aucun périphérique audio détecté : changement de piste impossible", 5000)
            return False
        self.player.setActiveAudioTrack(index)
        return True

    def fill_audio_menu(self):
        menu = self.menubar_widget.audioTrackMenu
        for action in menu.actions()[2:]:   # on garde « suivante » et le séparateur
            menu.removeAction(action)
        tracks = self.player.audioTracks()
        group = QtGui.QActionGroup(menu)
        active = self.player.activeAudioTrack()
        for i, track in enumerate(tracks):
            action = menu.addAction(self._track_label(i, track))
            action.setCheckable(True)
            action.setChecked(i == active)
            group.addAction(action)
            action.triggered.connect(lambda _c=False, n=i: self._set_audio_track(n))
        if not tracks:
            menu.addAction("(aucune piste)").setEnabled(False)

    def next_audio_track(self):
        count = len(self.player.audioTracks())
        if count < 2:
            self.flash("Une seule piste audio")
            return
        nxt = (self.player.activeAudioTrack() + 1) % count
        if self._set_audio_track(nxt):
            self.flash(f"Audio : {self._track_label(nxt, self.player.audioTracks()[nxt])}")

    def fill_subtitle_menu(self):
        menu = self.menubar_widget.subtitleMenu
        for action in menu.actions()[4:]:   # suivant, avancer, retarder, séparateur
            menu.removeAction(action)
        group = QtGui.QActionGroup(menu)
        embedded = self.player.subtitleTracks()
        active = self.player.activeSubtitleTrack()

        off = menu.addAction("Désactivés")
        off.setCheckable(True)
        off.setChecked(active < 0 and self._subtitles is None)
        group.addAction(off)
        off.triggered.connect(lambda: self.set_subtitle_source(None, -1))

        for i, track in enumerate(embedded):
            action = menu.addAction(self._track_label(i, track))
            action.setCheckable(True)
            action.setChecked(i == active and self._subtitles is None)
            group.addAction(action)
            action.triggered.connect(lambda _c=False, n=i: self.set_subtitle_source(None, n))

        if self._subtitles is not None:
            action = menu.addAction(f"Fichier : {self._subtitles.source}")
            action.setCheckable(True)
            action.setChecked(True)
            group.addAction(action)
        menu.addSeparator()
        menu.addAction(theme.icon("open_file"), "Charger un fichier de sous-titres…").triggered.connect(
            self.load_subtitle_dialog)

    def _load_sidecar_subtitles(self, video: Video):
        self._subtitles = None
        self.player_widget.set_subtitle_text("")
        sidecar = find_sidecar(video.path)
        if sidecar:
            self._set_external_subtitles(sidecar, announce=False)

    def _set_external_subtitles(self, file_path: Path, announce: bool = True):
        try:
            cues = load_subtitle_file(file_path)
        except OSError as error:
            self.flash(f"Sous-titres illisibles : {error}")
            return
        if not cues:
            self.flash("Aucun sous-titre valide dans ce fichier")
            return
        self._subtitles = SubtitleTrack(cues, source=file_path.name)
        self.player.setActiveSubtitleTrack(-1)
        if announce:
            self.flash(f"Sous-titres chargés : {file_path.name}")

    def load_subtitle_dialog(self):
        start = str(self._loaded_video.parent) if self._loaded_video else str(Path.home())
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Charger des sous-titres", start, "Sous-titres (*.srt *.vtt);;Tous les fichiers (*.*)")
        if file_path:
            self._set_external_subtitles(Path(file_path))

    def set_subtitle_source(self, external: SubtitleTrack | None, embedded_index: int):
        self._subtitles = external
        self.player_widget.set_subtitle_text("")
        self.player.setActiveSubtitleTrack(embedded_index)

    def next_subtitle(self):
        embedded = len(self.player.subtitleTracks())
        if embedded == 0 and self._subtitles is None:
            self.flash("Aucun sous-titre disponible")
            return
        current = -2 if self._subtitles is not None else self.player.activeSubtitleTrack()
        # Cycle : désactivés → piste 1 → … → piste N → fichier externe (le cas échéant) → désactivés
        if current == -1 and embedded:
            self.set_subtitle_source(None, 0)
            self.flash("Sous-titres : piste 1")
        elif current >= 0 and current + 1 < embedded:
            self.set_subtitle_source(None, current + 1)
            self.flash(f"Sous-titres : piste {current + 2}")
        else:
            self.set_subtitle_source(None, -1)
            self.flash("Sous-titres désactivés")

    def shift_subtitles(self, delta_ms: int):
        if self._subtitles is None:
            self.flash("Le décalage ne concerne que les sous-titres chargés depuis un fichier")
            return
        self._subtitles.delay += delta_ms
        self.flash(f"Décalage des sous-titres : {self._subtitles.delay / 1000:+.1f} s")

    # ===================================================================
    # IMAGE : format, capture, plein écran, premier plan
    # ===================================================================
    def set_aspect_mode(self, mode: str, save: bool = True):
        self.player_widget.set_aspect_mode(mode)
        action = self.menubar_widget.aspect_actions.get(mode)
        if action:
            action.setChecked(True)
        if save:
            self.settings.set("aspect_mode", mode)

    def take_screenshot(self):
        sink = self.player_widget.video_output.videoSink()
        image = sink.videoFrame().toImage() if sink is not None else QtGui.QImage()
        if image.isNull():
            image = self.player_widget.video_output.grab().toImage()
        if image.isNull() or not self.player.hasVideo():
            self.flash("Aucune image à capturer")
            return
        pictures = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.PicturesLocation)
        folder = Path(pictures or Path.home()) / APP_NAME
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            folder = Path.home()
        stem = self._loaded_video.stem if self._loaded_video else "capture"
        stamp = time.strftime("%H-%M-%S", time.gmtime(self.player.position() / 1000))
        target = folder / f"{stem}_{stamp}.png"
        counter = 2
        while target.exists():
            target = folder / f"{stem}_{stamp}_{counter}.png"
            counter += 1
        if image.save(str(target)):
            self.flash(f"Capture enregistrée : {target}", 6000)
        else:
            self.flash("Impossible d'enregistrer la capture")

    def set_always_on_top(self, enabled: bool):
        self.settings.set("always_on_top", bool(enabled))
        was_visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, bool(enabled))
        if was_visible:
            self.show()
            self.setGeometry(geometry)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        if self.isFullScreen():
            return
        self._was_maximized = self.isMaximized()
        self._dock_visible_before_fullscreen = self.dock_widget.isVisible()
        self.showFullScreen()
        for widget in (self.menubar_widget, self.toolbar_widget, self.dock_widget, self.statusbar_widget):
            widget.setVisible(False)
        self.setCursor(QtCore.Qt.CursorShape.BlankCursor)
        self.menubar_widget.toggle_full_screen_display(True)

    def exit_fullscreen(self):
        if not self.isFullScreen():
            return
        self._cursor_timer.stop()
        self.showMaximized() if self._was_maximized else self.showNormal()
        self.menubar_widget.setVisible(True)
        self.toolbar_widget.setVisible(True)
        self.statusbar_widget.setVisible(True)
        self.dock_widget.setVisible(self._dock_visible_before_fullscreen)   # respecte le choix de l'utilisateur
        self.unsetCursor()
        self.menubar_widget.toggle_full_screen_display(False)

    def _on_mouse_activity(self):
        """Plein écran : un mouvement de souris réaffiche le curseur et la barre de contrôle pendant 3 s."""
        if not self.isFullScreen():
            return
        self.unsetCursor()
        self.toolbar_widget.setVisible(True)
        self._cursor_timer.start()

    def _hide_fullscreen_controls(self):
        if self.isFullScreen() and self.player.playbackState() == PlaybackState.PlayingState:
            self.toolbar_widget.setVisible(False)
            self.setCursor(QtCore.Qt.CursorShape.BlankCursor)

    # ===================================================================
    # INFOS / FICHIERS
    # ===================================================================
    def _info_rows(self, video: Video) -> list[tuple[str, str]]:
        md = self.player.metaData() if video is self._loaded_video else None
        key = QtMultimedia.QMediaMetaData.Key

        def raw(k):
            """Valeur brute ; certaines clés (codecs, format) ne sont pas convertibles par PySide → ``None``."""
            if md is None or k not in md.keys():
                return None
            try:
                return md.value(k)
            except RuntimeError:
                return None

        def text(k):
            if md is None or k not in md.keys():
                return ""
            try:
                return md.stringValue(k)
            except RuntimeError:
                return ""

        rows = [
            ("Fichier", video.name), ("Dossier", str(video.parent)), ("Taille", format_size(video.size)),
            ("Durée", format_duration(video.duration) if video.duration else ""),
            ("Résolution", video.resolution),
            ("Format", text(key.FileFormat)), ("Codec vidéo", text(key.VideoCodec)),
            ("Codec audio", text(key.AudioCodec)),
            ("Débit vidéo", f"{int(raw(key.VideoBitRate)) // 1000} kb/s" if raw(key.VideoBitRate) else ""),
            ("Débit audio", f"{int(raw(key.AudioBitRate)) // 1000} kb/s" if raw(key.AudioBitRate) else ""),
            ("Images par seconde", f"{float(raw(key.VideoFrameRate)):.2f}" if raw(key.VideoFrameRate) else ""),
            ("Titre", text(key.Title)), ("Artiste", text(key.Author)), ("Album", text(key.AlbumTitle)),
            ("Genre", text(key.Genre)), ("Langue", text(key.Language)),
        ]
        if video is self._loaded_video:
            rows.append(("Pistes", f"{len(self.player.audioTracks())} audio, {len(self.player.subtitleTracks())} sous-titres"))
        rows.append(("Reprise", format_duration(self.resume.position(video.path)) if self.resume.position(video.path) else ""))
        return rows

    def _target_video(self) -> Video | None:
        selected = self.dock_widget.get_selected_videos()
        return selected[0] if selected else (self._loaded_video or self.current_video)

    def show_media_info(self, video: Video | None = None):
        video = video if isinstance(video, Video) else self._target_video()
        if video is None:
            self.flash("Aucun média sélectionné")
            return
        MediaInfoDialog(self._info_rows(video), video.name, self).exec()

    def reveal_current_file(self, video: Video | None = None):
        video = video if isinstance(video, Video) else self._target_video()
        if video is None:
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", "/select,", str(video.path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(video.path)])
            else:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(video.parent)))
        except OSError as error:
            self.flash(f"Impossible d'ouvrir le dossier : {error}")

    def open_log_folder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(paths.data_dir())))

    # ===================================================================
    # MENUS CONTEXTUELS
    # ===================================================================
    def show_player_context_menu(self, global_pos: QtCore.QPoint):
        self.build_player_context_menu().exec(global_pos)

    def build_player_context_menu(self) -> QtWidgets.QMenu:
        m = self.menubar_widget
        menu = QtWidgets.QMenu(self)
        m._palette_for_menu(menu)
        menu.addAction(m.act_play)
        menu.addAction(m.act_stop)
        menu.addSeparator()
        menu.addAction(m.act_skip_previous)
        menu.addAction(m.act_skip_next)
        menu.addSeparator()
        for submenu in (m.speedMenu, m.audioTrackMenu, m.subtitleMenu, m.aspectMenu):
            menu.addMenu(submenu)
        menu.addSeparator()
        menu.addAction(m.act_screenshot)
        menu.addAction(m.act_full_screen_mode)
        menu.addAction(m.act_media_info)
        return menu

    def show_playlist_context_menu(self, global_pos: QtCore.QPoint):
        self.build_playlist_context_menu().exec(global_pos)

    def build_playlist_context_menu(self) -> QtWidgets.QMenu:
        selected = self.dock_widget.get_selected_videos()
        menu = QtWidgets.QMenu(self)
        self.menubar_widget._palette_for_menu(menu)
        if selected:
            first = selected[0]
            menu.addAction(theme.icon("play"), "Lire").triggered.connect(lambda: self.double_click(self.dock_widget.find_item(first)))
            menu.addAction(theme.icon("arrow_upward"), "Monter  (Alt+↑)").triggered.connect(lambda: self.move_selected(-1))
            menu.addAction(theme.icon("arrow_downward"), "Descendre  (Alt+↓)").triggered.connect(lambda: self.move_selected(+1))
            menu.addSeparator()
            menu.addAction(theme.icon("remove"), "Retirer de la playlist  (Suppr)").triggered.connect(self.remove_video_from_playlist)
            menu.addAction(theme.icon("open_folder"), "Afficher dans le dossier").triggered.connect(lambda: self.reveal_current_file(first))
            menu.addAction(theme.icon("content_copy"), "Copier le chemin").triggered.connect(
                lambda: QtWidgets.QApplication.clipboard().setText("\n".join(str(v.path) for v in selected)))
            menu.addAction(theme.icon("metadata"), "Informations").triggered.connect(lambda: self.show_media_info(first))
            menu.addSeparator()
        menu.addAction(self.menubar_widget.act_open_file)
        menu.addAction(self.menubar_widget.act_open_folder)
        menu.addAction(self.menubar_widget.act_refresh_source)
        menu.addMenu(self.menubar_widget.sortMenu)
        return menu

    # ===================================================================
    # CLAVIER (flèches : actives tant que la liste ou un champ de saisie n'a pas le focus)
    # ===================================================================
    def keyPressEvent(self, event: QtGui.QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()
        step = 60_000 if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier else 10_000
        plain = not (modifiers & (QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.AltModifier))
        if plain and key == QtCore.Qt.Key.Key_Left:
            self.player_widget.seek_relative(-step)
        elif plain and key == QtCore.Qt.Key.Key_Right:
            self.player_widget.seek_relative(step)
        elif plain and key == QtCore.Qt.Key.Key_Up:
            self.change_volume(VOLUME_STEP)
        elif plain and key == QtCore.Qt.Key.Key_Down:
            self.change_volume(-VOLUME_STEP)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    # ===================================================================
    # DIVERS
    # ===================================================================
    def _update_menu_state(self):
        self.menubar_widget.act_refresh_source.setEnabled(self.active_playlist.source is not None)

    def about_pyplayer(self):
        AboutDialog(self).exec()

    def show_help_dialog(self):
        dialog = HelpDialog(self)
        dialog.setWindowOpacity(0)
        dialog.show()
        fade_animation = QtCore.QPropertyAnimation(dialog, b"windowOpacity", dialog)
        fade_animation.setDuration(300)
        fade_animation.setStartValue(0)
        fade_animation.setEndValue(1)
        fade_animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        fade_animation.start()
        dialog.move(self.geometry().center() - dialog.rect().center())
        dialog.exec()
