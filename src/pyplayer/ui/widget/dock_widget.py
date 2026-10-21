import os
from typing import List

from PySide6 import QtGui, QtCore, QtWidgets

from pyplayer.api.playlist import Playlist
from pyplayer.api.video import Video
from pyplayer.ui import theme as constant

# ============================================
# CLASSE VideoListItem PERSONNALISÉE
# ============================================

def progress_bar(progress: float) -> str:
    """Barre de progression à 10 segments : ▰▰▰▰▰▰▱▱▱▱"""
    progress = max(0.0, min(1.0, progress))
    full = round(progress * 10)
    return "▰" * full + "▱" * (10 - full)


class VideoListItem(QtWidgets.QListWidgetItem):
    """Ligne de la liste : porte les données (vidéo, numéro, état, avancement) ; le dessin est fait par
    :class:`VideoItemDelegate` — aucun widget par ligne, donc des milliers de médias restent fluides."""

    SEPARATOR_ICON = "➤"

    def __init__(self, index: int, video: Video, progress: float = 0.0, finished: bool = False, parent=None):
        super().__init__(parent)
        self.index = index
        self.video = video
        self._name = video.name
        self._is_current = False
        self._is_read = finished
        self._missing = False
        self._progress = 1.0 if finished else progress
        self._revision = 0
        self.setToolTip(str(video.path))
        self.setSizeHint(QtCore.QSize(0, VideoItemDelegate.ROW_HEIGHT))

    # --- propriétés
    @property
    def name(self) -> str:
        return self._name

    @property
    def is_current(self) -> bool:
        return self._is_current

    @is_current.setter
    def is_current(self, value: bool):
        value = bool(value)
        if self._is_current == value:
            return
        was_current, self._is_current = self._is_current, value
        if was_current and not value:
            self._is_read = True          # une vidéo quittée est marquée « lue »
        self.update_display()

    @property
    def is_read(self) -> bool:
        return self._is_read

    @is_read.setter
    def is_read(self, value: bool):
        value = bool(value)
        if self._is_read != value:
            self._is_read = value
            if value and self._is_current:
                self._is_current = False
            self.update_display()

    @property
    def missing(self) -> bool:
        return self._missing

    @missing.setter
    def missing(self, value: bool):
        if self._missing != bool(value):
            self._missing = bool(value)
            self.update_display()

    @property
    def state(self) -> str:
        if self._missing:
            return "missing"
        if self._is_current:
            return "current"
        return "read" if self._is_read else "normal"

    @property
    def progress_text(self) -> str:
        return progress_bar(self._progress)

    @property
    def main_text(self) -> str:
        return f"{self.index} {self.SEPARATOR_ICON}  {self.name}"

    # --- mises à jour
    def update_display(self):
        """Demande un redessin de la ligne (seulement si elle est dans une liste)."""
        self._revision += 1
        self.setData(QtCore.Qt.ItemDataRole.UserRole + 1, self._revision)   # déclenche dataChanged → repaint ciblé

    def set_progress(self, progress: float, finished: bool = False):
        """Avancement issu de la mémoire de reprise ; la ligne ne se redessine que si la barre change."""
        progress = 1.0 if finished else max(0.0, min(1.0, progress))
        if finished and not self._is_current:
            self._is_read = True
        changed = progress_bar(progress) != progress_bar(self._progress) or finished != (self._progress >= 1.0)
        self._progress = progress
        if changed:
            self.update_display()

    def set_selected(self, selected: bool):   # compatibilité : la sélection est dessinée par le délégué
        pass

    def set_current(self, is_current: bool):
        self.is_current = is_current

    def set_read(self, is_read: bool):
        self.is_read = is_read

    def get_video_name(self) -> str:
        return self.name

    def cleanup(self):
        """Compatibilité : plus de widgets à libérer."""

    def __str__(self) -> str:
        return f"VideoListItem[{self.index}: {self.name} ({self.state})]"

    __repr__ = __str__


class VideoItemDelegate(QtWidgets.QStyledItemDelegate):
    """Dessine une ligne : « n ➤ nom » à gauche, barre de progression à droite, couleurs selon l'état."""

    ROW_HEIGHT = 46   # 44 px de ligne + 1 px de marge haut/bas (comme l'ancien rendu)
    # état -> (couleur du texte, graisse, couleur de la progression, taille de la progression en px, graisse)
    STYLES = {
        "normal": ("#e0e0e0", 400, "#4CAF50", 12, 500),
        "current": ("#ffffff", 600, "#4CAF50", 16, 600),
        "read": ("#a5d6a7", 400, "#81C784", 14, 500),
        "missing": ("#8e8e93", 400, "#8e8e93", 12, 400),
    }
    FAMILY = "Segoe UI"

    def sizeHint(self, option, index):
        return QtCore.QSize(option.rect.width(), self.ROW_HEIGHT)

    @staticmethod
    def _font(pixel_size: int, weight: int) -> QtGui.QFont:
        font = QtGui.QFont(VideoItemDelegate.FAMILY)
        font.setStyleHint(QtGui.QFont.StyleHint.SansSerif)
        font.setPixelSize(pixel_size)
        font.setWeight(QtGui.QFont.Weight(weight))
        return font

    def paint(self, painter, option, index):
        item = index.data(QtCore.Qt.ItemDataRole.UserRole)
        if not isinstance(item, VideoListItem):
            return super().paint(painter, option, index)

        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.features &= ~QtWidgets.QStyleOptionViewItem.ViewItemFeature.HasDisplay
        widget = option.widget
        style = widget.style() if widget else QtWidgets.QApplication.style()
        style.drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)   # fond, survol, sélection (QSS)

        text_color, text_weight, progress_color, progress_px, progress_weight = self.STYLES[item.state]
        selected = bool(option.state & QtWidgets.QStyle.StateFlag.State_Selected)
        rect = option.rect.adjusted(9 if selected else 6, 4, -4, -4)

        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        progress_font = self._font(progress_px, progress_weight)
        progress_metrics = QtGui.QFontMetrics(progress_font)
        progress_width = progress_metrics.horizontalAdvance(item.progress_text)
        progress_rect = QtCore.QRect(rect.right() - progress_width, rect.top(), progress_width, rect.height())
        painter.setFont(progress_font)
        painter.setPen(QtGui.QColor(progress_color))
        painter.drawText(progress_rect, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
                         item.progress_text)

        text_font = self._font(12, text_weight)
        text_rect = QtCore.QRect(rect.left(), rect.top(), max(0, progress_rect.left() - rect.left() - 8), rect.height())
        elided = QtGui.QFontMetrics(text_font).elidedText(item.main_text, QtCore.Qt.TextElideMode.ElideRight, text_rect.width())
        painter.setFont(text_font)
        painter.setPen(QtGui.QColor(text_color))
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, elided)
        painter.restore()


class ReorderableList(QtWidgets.QListWidget):
    """Liste avec glisser-déposer pour réordonner : Qt ne déplace rien lui-même, il demande à la fenêtre
    (qui modifie la playlist puis reconstruit la liste) ; les widgets d'item restent ainsi intacts."""

    rows_move_requested = QtCore.Signal(list, int)   # lignes sources, ligne cible (avant déplacement)
    context_menu_requested = QtCore.Signal(QtCore.QPoint)
    files_dropped = QtCore.Signal(list)              # chemins déposés depuis l'explorateur

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.context_menu_requested.emit(self.viewport().mapToGlobal(pos)))
        self.setItemDelegate(VideoItemDelegate(self))
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.source() is self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.source() is self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls() and event.source() is not self:
            paths = [os.path.normpath(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        if event.source() is self:
            rows = sorted({self.row(item) for item in self.selectedItems()})
            target_item = self.itemAt(event.position().toPoint())
            target = self.row(target_item) if target_item is not None else self.count()
            if rows:
                self.rows_move_requested.emit(rows, target)
            event.ignore()  # la liste est reconstruite par la fenêtre après modification de la playlist
            return
        super().dropEvent(event)


# ============================================
# CLASSE DockWidget PRINCIPALE
# ============================================

class DockWidget(QtWidgets.QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: dict[int, VideoListItem] = {}  # id(video) -> item
        self.setup_ui()

    def setup_ui(self):
        self.customize_self()
        self.icon_font_initialize()
        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()
        self.add_widgets_to_layouts()
        self.setup_connections()

    def customize_self(self):
        self.setWindowTitle("Playlist")
        self.setMinimumWidth(250)

    def icon_font_initialize(self, size=14):
        self.icon_font = constant.load_icon_font(size)

    def create_widgets(self):
        # Widget principal
        self.main_widget = QtWidgets.QWidget()
        # TabWidget
        self.tab_widget = QtWidgets.QTabWidget()
        # Onglet 1 : Liste de lecture
        self.tab_current = QtWidgets.QWidget()
        self.lstw = ReorderableList()
        # Boutons pour l'onglet 1
        self.btn_add_to_playlist = QtWidgets.QPushButton("\ue03b")
        self.btn_remove_to_playlist = QtWidgets.QPushButton("\ueb80")
        # Onglet 2 : Archives
        self.tab_archive = QtWidgets.QWidget()
        self.lstw_archive = QtWidgets.QListWidget()
        # Boutons pour l'onglet 2
        self.btn_save_playlist = QtWidgets.QPushButton("\ueb60")
        self.btn_remove_save = QtWidgets.QPushButton("\ue872")

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

        # Style harmonisé pour les ListWidgets avec VideoListItem
        list_style = """
            QListWidget {
                background-color: rgba(30, 30, 30, 0.7);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                outline: none;
                padding: 4px;
            }

            QListWidget::item {
                height: 44px;
                padding: 0px;
                margin: 1px 0;
                border: none;
                font-family: 'Segoe UI', Arial, sans-serif;
                background-color: rgba(30, 30, 30, 0.7);
            }

            QListWidget::item:selected {
                background-color: rgba(76, 175, 80, 0.15);
                border-left: 3px solid rgba(76, 175, 80, 0.5);
                padding-left: 0px;
                border-radius: 2px;
            }

            QListWidget::item:hover:!selected {
                background-color: rgba(255, 255, 255, 0.07);
            }

            QScrollBar:vertical {
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
            }
            QPushButton:pressed {
                background-color: rgba(40, 40, 40, 0.9);
            }
        """
        # Configuration spécifique des boutons
        buttons_config = [
            (self.btn_add_to_playlist, "#4CAF50", "Ajouter un fichier à la playlist", "#4CAF50", "rgba(76, 175, 80, 0.1)"),
            (self.btn_remove_to_playlist, "#FF5252", "Retirer sélection", "#FF5252", "rgba(255, 82, 82, 0.1)"),
            (self.btn_save_playlist, "#4CAF50", "Créer une nouvelle playlist", "#4CAF50", "rgba(33, 150, 243, 0.1)"),
            (self.btn_remove_save, "#FF5252", "Supprimer une playlist", "#FF5252", "rgba(255, 82, 82, 0.1)")
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
        self.lstw.setAlternatingRowColors(False)  # Désactivé pour éviter le problème
        self.lstw_archive.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        # Noms des onglets
        self.tab_widget.addTab(self.tab_current, "Playlist Active")
        self.tab_widget.addTab(self.tab_archive, "Gestion des Playlists")

    def create_layouts(self):
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(3, 0, 3, 3)
        self.main_layout.setSpacing(0)

        self.tab_current_layout = QtWidgets.QVBoxLayout(self.tab_current)
        self.tab_current_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_current_layout.setSpacing(5)

        self.current_buttons_layout = QtWidgets.QHBoxLayout()
        self.current_buttons_layout.setSpacing(5)

        self.tab_archive_layout = QtWidgets.QVBoxLayout(self.tab_archive)
        self.tab_archive_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_archive_layout.setSpacing(5)

        self.archive_buttons_layout = QtWidgets.QHBoxLayout()
        self.archive_buttons_layout.setSpacing(5)

    def add_widgets_to_layouts(self):
        self.main_layout.addWidget(self.tab_widget)

        # Onglet 1
        self.tab_current_layout.addWidget(self.lstw, 1)
        current_buttons_vbox = QtWidgets.QVBoxLayout()
        current_buttons_vbox.addLayout(self.current_buttons_layout)
        self.tab_current_layout.addLayout(current_buttons_vbox)
        self.current_buttons_layout.addWidget(self.btn_add_to_playlist)
        self.current_buttons_layout.addWidget(self.btn_remove_to_playlist)

        # Onglet 2
        self.tab_archive_layout.addWidget(self.lstw_archive, 1)
        archive_buttons_vbox = QtWidgets.QVBoxLayout()
        archive_buttons_vbox.addLayout(self.archive_buttons_layout)
        self.tab_archive_layout.addLayout(archive_buttons_vbox)
        self.archive_buttons_layout.addWidget(self.btn_save_playlist)
        self.archive_buttons_layout.addWidget(self.btn_remove_save)

        self.setWidget(self.main_widget)

    def setup_connections(self):
        # Connecter le signal de changement de sélection
        self.lstw.itemSelectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self):
        """Met à jour les marges des items selon leur sélection."""
        selected_items = self.lstw.selectedItems()
        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem):
                is_selected = item in selected_items
                item.set_selected(is_selected)

    # ============================================
    # MÉTHODES DE GESTION DES PLAYLISTS (onglet « Gestion »)
    # ============================================

    def _archive_item(self, playlist_id: str):
        for i in range(self.lstw_archive.count()):
            item = self.lstw_archive.item(i)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) == playlist_id:
                return item
        return None

    def add_playlist_state(self, playlist: Playlist) -> bool:
        """Ajoute la playlist à l'onglet de gestion (identifiée par son ID, jamais par son nom)."""
        if self._archive_item(playlist.id) is not None:
            return False
        item = QtWidgets.QListWidgetItem(playlist.name)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, playlist.id)
        self.lstw_archive.addItem(item)
        return True

    def remove_playlist_state(self, playlist_id: str) -> bool:
        item = self._archive_item(playlist_id)
        if item is None:
            return False
        self.lstw_archive.takeItem(self.lstw_archive.row(item))
        return True

    def rename_playlist_state(self, playlist: Playlist):
        item = self._archive_item(playlist.id)
        if item is not None:
            item.setText(playlist.name)
        if self.lstw_archive.currentItem() is item:
            self.tab_widget.setTabText(self.tab_widget.indexOf(self.tab_current), playlist.name)

    def sync_playlists(self, playlists: List[Playlist]):
        """Reconstruit l'onglet de gestion à partir des playlists existantes."""
        wanted = {p.id for p in playlists}
        for i in reversed(range(self.lstw_archive.count())):
            if self.lstw_archive.item(i).data(QtCore.Qt.ItemDataRole.UserRole) not in wanted:
                self.lstw_archive.takeItem(i)
        for playlist in playlists:
            self.add_playlist_state(playlist)
            self.rename_playlist_state(playlist)

    def get_selected_playlist_id(self) -> str:
        selected_items = self.lstw_archive.selectedItems()
        if selected_items:
            return selected_items[0].data(QtCore.Qt.ItemDataRole.UserRole) or ""
        return ""

    def set_active_playlist(self, playlist: Playlist):
        item = self._archive_item(playlist.id)
        if item is None:
            return None
        self.lstw_archive.blockSignals(True)  # sélectionner l'active ne doit pas relancer un changement de playlist
        self.lstw_archive.setCurrentItem(item)
        self.lstw_archive.blockSignals(False)
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.tab_current), playlist.name)
        return playlist

    # ============================================
    # MÉTHODES POUR VideoListItem
    # ============================================

    def populate(self, videos: List[Video], resume=None, current: Video | None = None):
        """Reconstruit toute la liste d'un coup (rapide : un seul repaint)."""
        selected = {id(item.video) for item in self.lstw.selectedItems() if isinstance(item, VideoListItem)}
        self.lstw.setUpdatesEnabled(False)
        try:
            self.lstw.clear()
            self._items.clear()
            for position, video in enumerate(videos):
                self._add_item(video, resume, check_exists=position < self.EXISTS_CHECK_NOW)
            if len(videos) > self.EXISTS_CHECK_NOW:
                QtCore.QTimer.singleShot(0, lambda: self._check_missing(self.EXISTS_CHECK_NOW))
            for item in self.get_video_items():
                if id(item.video) in selected:
                    item.setSelected(True)
            if current is not None:
                self.set_current_video(current)
        finally:
            self.lstw.setUpdatesEnabled(True)

    EXISTS_CHECK_NOW = 300      # au-delà, la vérification d'existence (un stat par fichier) se fait par paquets
    EXISTS_CHECK_CHUNK = 200

    def _check_missing(self, start: int):
        """Vérifie par paquets l'existence des fichiers, sans bloquer l'interface sur de très grandes listes."""
        end = min(self.lstw.count(), start + self.EXISTS_CHECK_CHUNK)
        for row in range(start, end):
            item = self.lstw.item(row)
            if isinstance(item, VideoListItem):
                item.missing = not item.video.exists()
        if end < self.lstw.count():
            QtCore.QTimer.singleShot(0, lambda: self._check_missing(end))

    def _add_item(self, video: Video, resume=None, check_exists: bool = True) -> VideoListItem:
        progress, finished = (0.0, False)
        if resume is not None:
            progress, finished = resume.progress(video.path, video.duration), resume.is_finished(video.path)
        item = VideoListItem(self.lstw.count() + 1, video, progress, finished)
        if check_exists:
            item.missing = not video.exists()
        item.setData(QtCore.Qt.ItemDataRole.UserRole, item)
        self.lstw.addItem(item)
        self._items[id(video)] = item
        return item

    def add_video_to_playlist(self, video: Video, resume=None) -> bool:
        """Ajoute un média à la fin de la liste."""
        if video is None or id(video) in self._items:
            return False
        self._add_item(video, resume)
        return True

    def remove_video_from_playlist(self, video: Video) -> bool:
        item = self._items.pop(id(video), None)
        if item is None:
            return False
        self.lstw.takeItem(self.lstw.row(item))
        self.reindex_video_items()
        return True

    def reindex_video_items(self):
        """Réindexe tous les VideoListItem."""
        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem):
                item.index = i + 1
                item.update_display()

    def find_item(self, video: Video | None) -> "VideoListItem | None":
        return self._items.get(id(video)) if video is not None else None

    def set_current_video(self, video: Video | None) -> bool:
        """Marque la vidéo en cours de lecture ; la précédente passe en « lue » si elle a été vue."""
        found = False
        for item in self.get_video_items():
            if video is not None and item.video is video:
                item.is_current = True
                item.is_read = False
                found = True
                self.lstw.setCurrentItem(item, QtCore.QItemSelectionModel.SelectionFlag.NoUpdate)
                self.lstw.scrollToItem(item)
            elif item.is_current:
                item.is_current = False
        return found

    def update_video_progress(self, video: Video, progress: float, finished: bool = False):
        item = self.find_item(video)
        if item is not None:
            item.set_progress(progress, finished)

    def refresh_missing(self):
        for item in self.get_video_items():
            item.missing = not item.video.exists()

    def get_selected_videos(self) -> List[Video]:
        return [item.video for item in self.lstw.selectedItems() if isinstance(item, VideoListItem)]

    def clear_video_playlist(self):
        """Vide complètement la liste."""
        self.lstw.clear()
        self._items.clear()

    def get_video_items(self) -> List[VideoListItem]:
        return [item for item in (self.lstw.item(i) for i in range(self.lstw.count()))
                if isinstance(item, VideoListItem)]


# ============================================
# CLASSE DeletePlaylistDialog (inchangée)
# ============================================

class DeletePlaylistDialog(QtWidgets.QDialog):
    """Choix des playlists à supprimer. ``playlists`` : liste de ``(id, nom)`` ; ``selected_playlists`` : IDs choisis."""

    def __init__(self, playlists, parent=None):
        super().__init__(parent)
        self.playlists = list(playlists)
        self.selected_playlists = []
        self.confirm_dialog = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Supprimer des playlists")
        self.setModal(True)
        self.setFixedSize(500, 400)

        # Style global
        self.setStyleSheet(
            f"""QDialog {{background-color: {constant.PRINCIPAL_COLOR};font-family: 'Segoe UI', Arial, sans-serif;}}QLabel {{color: {constant.PRINCIPAL_TEXT_COLOR};background-color: transparent;}}QCheckBox {{font-size: 14px;color: {constant.PRINCIPAL_TEXT_COLOR};padding: 8px 4px;margin: 2px;background-color: transparent;}}QCheckBox:hover {{background-color: {constant.HOVER_COLOR};border-radius: 4px;color: {constant.PRINCIPAL_TEXT_COLOR};}}QCheckBox::indicator {{width: 18px;height: 18px;border: 2px solid {constant.THIRD_COLOR};border-radius: 9px;background-color: {constant.SECONDARY_COLOR};}}QCheckBox::indicator:checked {{background-color: {constant.ACCENT_COLOR};border: 4px solid {constant.SECONDARY_COLOR};}}QCheckBox::indicator:checked:hover {{background-color: #ff5a52;}}QScrollArea {{border: 1px solid {constant.THIRD_COLOR};background-color: {constant.SECONDARY_COLOR};border-radius: 8px;}}QScrollBar:vertical {{background-color: {constant.SECONDARY_COLOR};width: 12px;border-radius: 6px;}}QScrollBar::handle:vertical {{background-color: {constant.THIRD_COLOR};border-radius: 6px;min-height: 20px;}}QScrollBar::handle:vertical:hover {{background-color: {constant.HOVER_COLOR};}}QWidget#scroll_content {{background-color: {constant.SECONDARY_COLOR};}}""")

        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # En-tête avec icône
        header_layout = QtWidgets.QHBoxLayout()
        icon_label = QtWidgets.QLabel("⚠️")
        icon_label.setStyleSheet(
            f"""QLabel {{font-size: 32px;color: {constant.ACCENT_COLOR};background-color: transparent;}}""")
        icon_label.setFixedSize(40, 40)

        header_text = QtWidgets.QLabel("Sélectionnez les playlists à supprimer")
        header_text.setStyleSheet(
            f"""QLabel {{font-size: 18px;font-weight: bold;color: {constant.PRINCIPAL_TEXT_COLOR};background-color: transparent;}}""")
        header_layout.addWidget(icon_label)
        header_layout.addWidget(header_text)
        header_layout.addStretch()

        # Zone de défilement pour les playlists
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Conteneur pour les boutons radio
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_widget.setObjectName("scroll_content")
        self.radio_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.radio_layout.setSpacing(8)
        self.radio_layout.setContentsMargins(16, 16, 16, 16)

        # Créer les boutons radio
        self.radio_buttons = []
        for playlist_id, playlist_name in self.playlists:
            radio = QtWidgets.QCheckBox(playlist_name)
            radio.setProperty("playlist_id", playlist_id)
            self.radio_layout.addWidget(radio)
            self.radio_buttons.append(radio)

        self.radio_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)

        # Boutons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(12)

        # Bouton "Annuler"
        self.btn_cancel = QtWidgets.QPushButton("Annuler")
        self.btn_cancel.setStyleSheet(
            f"""QPushButton {{background-color: {constant.THIRD_COLOR};color: {constant.PRINCIPAL_TEXT_COLOR};padding: 10px 24px;border-radius: 6px;border: none;font-weight: 600;}}QPushButton:hover {{background-color: {constant.HOVER_COLOR};}}QPushButton:pressed {{background-color: {constant.PRESSED_COLOR};}}""")
        self.btn_cancel.clicked.connect(self.reject)

        # Bouton "Supprimer"
        self.btn_delete = QtWidgets.QPushButton("Supprimer")
        self.btn_delete.setStyleSheet(
            f"""QPushButton {{background-color: {constant.ACCENT_COLOR};color: {constant.PRINCIPAL_TEXT_COLOR};padding: 10px 24px;border-radius: 6px;border: none;font-weight: 600;}}QPushButton:hover {{background-color: #ff5a52;}}QPushButton:pressed {{background-color: #d70015;}}QPushButton:disabled {{background-color: {constant.THIRD_COLOR};color: #8e8e93;}}""")
        self.btn_delete.clicked.connect(self.show_confirm_dialog)
        self.btn_delete.setEnabled(False)

        # Activer/désactiver le bouton Supprimer en fonction de la sélection
        for radio in self.radio_buttons:
            radio.toggled.connect(self.update_delete_button)

        button_layout.addStretch()
        button_layout.addWidget(self.btn_cancel)
        button_layout.addWidget(self.btn_delete)

        # Assembler le layout
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.scroll_area)
        main_layout.addLayout(button_layout)

        self.update_delete_button()

    def update_delete_button(self):
        """Active le bouton Supprimer si au moins un élément est sélectionné"""
        has_selection = any(radio.isChecked() for radio in self.radio_buttons)
        self.btn_delete.setEnabled(has_selection)

    def get_selected_playlists(self):
        """IDs des playlists sélectionnées"""
        return [radio.property("playlist_id") for radio in self.radio_buttons if radio.isChecked()]

    def get_selected_names(self):
        return [radio.text() for radio in self.radio_buttons if radio.isChecked()]

    def show_confirm_dialog(self):
        """Affiche la boîte de dialogue de confirmation"""
        selected = self.get_selected_names()
        if not selected:
            return

        # Créer la boîte de dialogue de confirmation
        self.confirm_dialog = QtWidgets.QDialog(self)
        self.confirm_dialog.setWindowTitle("Confirmer la suppression")
        self.confirm_dialog.setModal(True)
        self.confirm_dialog.setFixedSize(500, 350)

        # Style de la boîte de confirmation
        self.confirm_dialog.setStyleSheet(
            f"""QDialog {{background-color: {constant.PRINCIPAL_COLOR};font-family: 'Segoe UI', Arial, sans-serif;}}QLabel {{color: {constant.PRINCIPAL_TEXT_COLOR};background-color: transparent;}}QTextEdit {{background-color: {constant.SECONDARY_COLOR};color: {constant.PRINCIPAL_TEXT_COLOR};border: 1px solid {constant.THIRD_COLOR};border-radius: 6px;padding: 10px;font-size: 14px;}}""")

        # Layout principal
        confirm_layout = QtWidgets.QVBoxLayout(self.confirm_dialog)
        confirm_layout.setSpacing(16)
        confirm_layout.setContentsMargins(20, 20, 20, 20)

        # En-tête avec icône
        header_layout = QtWidgets.QHBoxLayout()
        confirm_icon = QtWidgets.QLabel("⚠️")
        confirm_icon.setStyleSheet(
            f"""QLabel {{font-size: 32px;color: {constant.ACCENT_COLOR};background-color: transparent;}}""")
        confirm_icon.setFixedSize(40, 40)

        confirm_title = QtWidgets.QLabel("Confirmer la suppression")
        confirm_title.setStyleSheet(
            f"""QLabel {{font-size: 18px;font-weight: bold;color: {constant.PRINCIPAL_TEXT_COLOR};background-color: transparent;}}""")
        header_layout.addWidget(confirm_icon)
        header_layout.addWidget(confirm_title)
        header_layout.addStretch()

        # Zone de message
        message_widget = QtWidgets.QWidget()
        message_widget.setStyleSheet("background-color: transparent;")
        message_layout = QtWidgets.QVBoxLayout(message_widget)
        message_layout.setSpacing(12)
        message_layout.setContentsMargins(0, 0, 0, 0)

        # Message principal
        if len(selected) == 1:
            main_message = QtWidgets.QLabel(f"Supprimer la playlist '{selected[0]}' ?")
        else:
            main_message = QtWidgets.QLabel(f"Supprimer {len(selected)} playlists ?")
        main_message.setStyleSheet(
            f"""QLabel {{font-size: 16px;font-weight: 500;color: {constant.PRINCIPAL_TEXT_COLOR};background-color: transparent;}}""")

        # Avertissement
        warning_label = QtWidgets.QLabel("Cette action est irréversible.")
        warning_label.setStyleSheet(
            f"""QLabel {{font-size: 14px;color: {constant.ACCENT_COLOR};font-weight: 500;background-color: transparent;}}""")

        # Liste des playlists sélectionnées
        list_widget = QtWidgets.QTextEdit()
        list_widget.setReadOnly(True)
        playlist_text = ""
        for i, playlist in enumerate(selected, 1):
            playlist_text += f"{i}. {playlist}\n"
        list_widget.setText(playlist_text.strip())

        line_count = len(selected)
        list_height = min(30 + line_count * 24, 150)
        list_widget.setFixedHeight(list_height)

        message_layout.addWidget(main_message)
        message_layout.addWidget(warning_label)
        message_layout.addWidget(list_widget)

        # Boutons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(12)

        # Bouton "Revoir la sélection"
        btn_back = QtWidgets.QPushButton("Revoir la sélection")
        btn_back.setStyleSheet(
            f"""QPushButton {{background-color: transparent;color: {constant.PRINCIPAL_TEXT_COLOR};padding: 10px 20px;border: 1px solid {constant.THIRD_COLOR};border-radius: 6px;font-weight: 500;}}QPushButton:hover {{background-color: {constant.HOVER_COLOR};border-color: {constant.HOVER_COLOR};}}QPushButton:pressed {{background-color: {constant.PRESSED_COLOR};}}""")
        btn_back.clicked.connect(self.back_to_selection)

        # Bouton "Annuler"
        btn_confirm_cancel = QtWidgets.QPushButton("Annuler")
        btn_confirm_cancel.setStyleSheet(
            f"""QPushButton {{background-color: {constant.THIRD_COLOR};color: {constant.PRINCIPAL_TEXT_COLOR};padding: 10px 24px;border-radius: 6px;border: none;font-weight: 600;}}QPushButton:hover {{background-color: {constant.HOVER_COLOR};}}QPushButton:pressed {{background-color: {constant.PRESSED_COLOR};}}""")
        btn_confirm_cancel.clicked.connect(self.cancel_confirm)

        # Bouton "Supprimer"
        btn_confirm_delete = QtWidgets.QPushButton("Supprimer")
        btn_confirm_delete.setStyleSheet(
            f"""QPushButton {{background-color: {constant.ACCENT_COLOR};color: {constant.PRINCIPAL_TEXT_COLOR};padding: 10px 24px;border-radius: 6px;border: none;font-weight: 600;}}QPushButton:hover {{background-color: #ff5a52;}}QPushButton:pressed {{background-color: #d70015;}}""")
        btn_confirm_delete.clicked.connect(self.final_delete)

        button_layout.addWidget(btn_back)
        button_layout.addStretch()
        button_layout.addWidget(btn_confirm_cancel)
        button_layout.addWidget(btn_confirm_delete)

        # Assembler le layout
        confirm_layout.addLayout(header_layout)
        confirm_layout.addWidget(message_widget)
        confirm_layout.addStretch()
        confirm_layout.addLayout(button_layout)

        # Connecter le signal finished pour gérer la fermeture
        self.confirm_dialog.finished.connect(self.on_confirm_dialog_closed)

        # Afficher la fenêtre de confirmation
        self.confirm_dialog.show()

    def on_confirm_dialog_closed(self, result):
        """Gère la fermeture de la fenêtre de confirmation"""
        if result == QtWidgets.QDialog.DialogCode.Rejected:
            if not hasattr(self, '_back_to_selection_flag') or not self._back_to_selection_flag:
                self.reject()
            else:
                self._back_to_selection_flag = False
        elif result == QtWidgets.QDialog.DialogCode.Accepted:
            self.accept()

    def back_to_selection(self):
        """Retour à la fenêtre de sélection"""
        if self.confirm_dialog:
            self._back_to_selection_flag = True
            self.confirm_dialog.reject()

    def cancel_confirm(self):
        """Annuler la confirmation et fermer la principale"""
        if self.confirm_dialog:
            self.confirm_dialog.reject()

    def final_delete(self):
        """Finalise la suppression"""
        self.selected_playlists = self.get_selected_playlists()
        if self.confirm_dialog:
            self.confirm_dialog.accept()