from typing import List

from PySide6 import QtCore, QtGui, QtWidgets

from src.pyplayer.domain.media import Video
from src.pyplayer.domain.playlist import Playlist
from src.pyplayer.ui.theme import (
    ACCENT_COLOR,
    HOVER_COLOR,
    PRESSED_COLOR,
    PRINCIPAL_COLOR,
    PRINCIPAL_TEXT_COLOR,
    SECONDARY_COLOR,
    THIRD_COLOR,
)
from src.pyplayer.infrastructure.filesystem import find_path


class VideoListItem(QtWidgets.QListWidgetItem):
    """Item personnalisé pour afficher une vidéo avec progression séparée."""

    SEPARATOR_ICON = "➤"

    def __init__(self, index: int, video: Video, parent=None):
        super().__init__(parent)

        self.index = index
        self.video = video
        self._name = video.name if hasattr(video, "name") else ""
        self._is_current = False
        self._is_read = False

        self.container = QtWidgets.QWidget()
        self.container.setProperty("class", "video-item-container")

        self.text_label = QtWidgets.QLabel()
        self.text_label.setProperty("class", "video-item-text")

        self.progress_label = QtWidgets.QLabel()
        self.progress_label.setProperty("class", "video-item-progress")
        self.progress_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )

        self.layout = QtWidgets.QHBoxLayout(self.container)

        self.normal_margins = QtCore.QMargins(6, 4, 4, 4)
        self.selected_margins = QtCore.QMargins(9, 4, 4, 4)

        self.layout.setContentsMargins(self.normal_margins)

        self.layout.addWidget(self.text_label, 1)
        self.layout.addWidget(self.progress_label, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        self.update_display()

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = str(value)
        self.update_display()

    @property
    def is_current(self) -> bool:
        return self._is_current

    @is_current.setter
    def is_current(self, value: bool):
        old_value = self._is_current
        new_value = bool(value)

        if old_value == new_value:
            return

        self._is_current = new_value

        if old_value and not new_value:
            self.is_read = True

        self.apply_style()

    @property
    def is_read(self) -> bool:
        return self._is_read

    @is_read.setter
    def is_read(self, value: bool):
        if self._is_read != value:
            self._is_read = bool(value)
            if value and self._is_current:
                self._is_current = False
            self.apply_style()

    @property
    def state(self) -> str:
        if self._is_current:
            return "current"
        if self._is_read:
            return "read"
        return "normal"

    def update_display(self):
        main_text = f"{self.index} {self.SEPARATOR_ICON}  {self.name}"
        self.text_label.setText(main_text)

        progress_text = f"{self.video.progress}"
        self.progress_label.setText(progress_text)

        self.apply_style()

    def apply_style(self):
        self.text_label.setProperty("state", self.state)
        self.progress_label.setProperty("state", self.state)

        self.text_label.style().unpolish(self.text_label)
        self.text_label.style().polish(self.text_label)
        self.progress_label.style().unpolish(self.progress_label)
        self.progress_label.style().polish(self.progress_label)

    def set_selected(self, selected: bool):
        if selected:
            self.layout.setContentsMargins(self.selected_margins)
        else:
            self.layout.setContentsMargins(self.normal_margins)

    def set_current(self, is_current: bool):
        self.is_current = is_current

    def set_read(self, is_read: bool):
        self.is_read = is_read

    def get_video_name(self) -> str:
        return self.name

    def set_widget_to_list(self, list_widget: QtWidgets.QListWidget):
        list_widget.setItemWidget(self, self.container)

    def cleanup(self):
        try:
            if hasattr(self, "container"):
                if hasattr(self, "layout"):
                    while self.layout.count():
                        child = self.layout.takeAt(0)
                        if child and child.widget():
                            child.widget().setParent(None)
                    self.layout.deleteLater()

                self.container.deleteLater()

            self.text_label = None
            self.progress_label = None
            self.container = None
            self.layout = None

        except Exception as error:
            print(f"Erreur lors du nettoyage: {error}")

    def __str__(self) -> str:
        return f"VideoListItem[{self.index}: {self.name} ({self.state})]"

    def __repr__(self) -> str:
        return f"VideoListItem(index={self.index}, name='{self.name}', state='{self.state}')"


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

    def customize_self(self):
        self.setWindowTitle("Playlist")
        self.setMinimumWidth(250)

    def icon_font_initialize(self, size=14):
        font_path = find_path("material-symbols-outlined.ttf")
        font_id = QtGui.QFontDatabase.addApplicationFont(str(font_path))
        self.icon_font = QtGui.QFont(QtGui.QFontDatabase.applicationFontFamilies(font_id)[0])
        self.icon_font.setPointSize(size)

    def create_widgets(self):
        self.main_widget = QtWidgets.QWidget()
        self.tab_widget = QtWidgets.QTabWidget()

        self.tab_current = QtWidgets.QWidget()
        self.lstw = QtWidgets.QListWidget()
        self.btn_add_to_playlist = QtWidgets.QPushButton("\ue03b")
        self.btn_remove_to_playlist = QtWidgets.QPushButton("\ueb80")

        self.tab_archive = QtWidgets.QWidget()
        self.lstw_archive = QtWidgets.QListWidget()
        self.btn_save_playlist = QtWidgets.QPushButton("\ueb60")
        self.btn_remove_save = QtWidgets.QPushButton("\ue872")

    def modify_widgets(self):
        self.tab_widget.setStyleSheet(
            """
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
        """
        )

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

            QListWidget::item .video-item-container {
                background-color: inherit;
            }

            QListWidget::item:selected .video-item-container {
                background-color: rgba(76, 175, 80, 0.15);
            }

            QListWidget::item:hover:!selected .video-item-container {
                background-color: rgba(255, 255, 255, 0.07);
            }

            .video-item-text {
                background-color: transparent;
            }

            .video-item-progress {
                background-color: transparent;
            }

            .video-item-text[state="normal"] {
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }

            .video-item-progress[state="normal"] {
                color: #4CAF50;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 500;
            }

            .video-item-text[state="current"] {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 600;
                color: #ffffff;
                font-size: 12px;
            }

            .video-item-progress[state="current"] {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 600;
                color: #4CAF50;
                font-size: 16px;
            }

            .video-item-text[state="read"] {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: normal;
                color: #a5d6a7;
                font-size: 12px;
            }

            .video-item-progress[state="read"] {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 500;
                color: #81C784;
                font-size: 14px;
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
        buttons_config = [
            (
                self.btn_add_to_playlist,
                "#4CAF50",
                "Ajouter un fichier",
                "#4CAF50",
                "rgba(76, 175, 80, 0.1)",
            ),
            (
                self.btn_remove_to_playlist,
                "#FF5252",
                "Retirer sélection",
                "#FF5252",
                "rgba(255, 82, 82, 0.1)",
            ),
            (
                self.btn_save_playlist,
                "#4CAF50",
                "Créer une nouvelle playlist",
                "#4CAF50",
                "rgba(33, 150, 243, 0.1)",
            ),
            (
                self.btn_remove_save,
                "#FF5252",
                "Supprimer une playlist",
                "#FF5252",
                "rgba(255, 82, 82, 0.1)",
            ),
        ]
        for btn, color, tooltip, hover_color, hover_bg in buttons_config:
            btn.setFont(self.icon_font)
            btn.setStyleSheet(
                f"""
                {button_base_style}
                QPushButton {{
                    color: {color};
                }}
                QPushButton:hover {{
                    color: {hover_color};
                    border-color: {color};
                    background-color: {hover_bg};
                }}
            """
            )
            btn.setToolTip(
                "<div style='background-color: rgba(40,40,40,0.95); padding: 8px; "
                "border-radius: 4px; border: 1px solid rgba(255,255,255,0.1);'>"
                f"<b style='color:#ffffff; font-size: 12px;'>{tooltip}</b></div>"
            )

        self.lstw.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lstw.setAlternatingRowColors(False)
        self.lstw_archive.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

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

        self.tab_current_layout.addWidget(self.lstw, 1)
        current_buttons_vbox = QtWidgets.QVBoxLayout()
        current_buttons_vbox.addLayout(self.current_buttons_layout)
        self.tab_current_layout.addLayout(current_buttons_vbox)
        self.current_buttons_layout.addWidget(self.btn_add_to_playlist)
        self.current_buttons_layout.addWidget(self.btn_remove_to_playlist)

        self.tab_archive_layout.addWidget(self.lstw_archive, 1)
        archive_buttons_vbox = QtWidgets.QVBoxLayout()
        archive_buttons_vbox.addLayout(self.archive_buttons_layout)
        self.tab_archive_layout.addLayout(archive_buttons_vbox)
        self.archive_buttons_layout.addWidget(self.btn_save_playlist)
        self.archive_buttons_layout.addWidget(self.btn_remove_save)

        self.setWidget(self.main_widget)

    def setup_connections(self):
        self.lstw.itemSelectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self):
        selected_items = self.lstw.selectedItems()
        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem):
                item.set_selected(item in selected_items)

    def add_playlist_state(self, item: Playlist):
        if not self.lstw_archive.findItems(item.name, QtCore.Qt.MatchFlag.MatchEndsWith):
            self.lstw_archive.addItem(item.name)
            return True
        return False

    def remove_playlist_state(self, item: Playlist):
        items = self.lstw_archive.findItems(item.name, QtCore.Qt.MatchFlag.MatchExactly)
        if items:
            row = self.lstw_archive.row(items[0])
            self.lstw_archive.takeItem(row)
            return True
        return False

    def get_selected_playlist_name(self) -> str:
        selected_items = self.lstw_archive.selectedItems()
        if selected_items:
            return selected_items[0].text()
        return ""

    def set_active_playlist(self, playlist: Playlist):
        items = self.lstw_archive.findItems(playlist.name, QtCore.Qt.MatchFlag.MatchExactly)
        if items:
            self.lstw_archive.setCurrentItem(items[0])
            index = self.tab_widget.indexOf(self.tab_current)
            self.tab_widget.setTabText(index, playlist.name)
            return playlist

    def add_video_to_playlist(self, video: Video) -> bool:
        if not video or not hasattr(video, "name"):
            return False

        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem) and item.name == video.name:
                return False

        index = self.lstw.count() + 1
        item = VideoListItem(index, video)
        self.lstw.addItem(item)
        self.lstw.setItemWidget(item, item.container)

        return True

    def remove_video_from_playlist(self, video_name: str) -> bool:
        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem) and item.name == video_name:
                item.cleanup()
                self.lstw.takeItem(i)
                self.reindex_video_items()
                return True
        return False

    def reindex_video_items(self):
        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem):
                item.index = i + 1
                item.update_display()

    def set_current_video(self, video_name: str) -> bool:
        found_current = False

        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem):
                if item.name == video_name:
                    item.is_current = True
                    item.is_read = False
                    found_current = True
                    self.lstw.clearSelection()
                    self.lstw.setCurrentItem(item)
                elif item.is_current:
                    item.is_current = False

        return found_current

    def update_video_progress(self, video_name: str):
        item = self.find_video_item_by_name(video_name)
        if item:
            item.update_display()

    def get_selected_video_names(self) -> List[str]:
        selected_items = self.lstw.selectedItems()
        return [item.name for item in selected_items if isinstance(item, VideoListItem)]

    def clear_video_playlist(self):
        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem):
                item.cleanup()

        self.lstw.clear()

    def find_video_item_by_name(self, video_name: str) -> VideoListItem | None:
        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem) and item.name == video_name:
                return item
        return None

    def get_video_items(self) -> List[VideoListItem]:
        items = []
        for i in range(self.lstw.count()):
            item = self.lstw.item(i)
            if isinstance(item, VideoListItem):
                items.append(item)
        return items


class DeletePlaylistDialog(QtWidgets.QDialog):
    def __init__(self, playlists, parent=None):
        super().__init__(parent)
        self.playlists = playlists
        self.selected_playlists = []
        self.confirm_dialog = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Supprimer des playlists")
        self.setModal(True)
        self.setFixedSize(500, 400)

        self.setStyleSheet(
            f"""QDialog {{background-color: {PRINCIPAL_COLOR};font-family: 'Segoe UI', Arial, sans-serif;}}QLabel {{color: {PRINCIPAL_TEXT_COLOR};background-color: transparent;}}QCheckBox {{font-size: 14px;color: {PRINCIPAL_TEXT_COLOR};padding: 8px 4px;margin: 2px;background-color: transparent;}}QCheckBox:hover {{background-color: {HOVER_COLOR};border-radius: 4px;color: {PRINCIPAL_TEXT_COLOR};}}QCheckBox::indicator {{width: 18px;height: 18px;border: 2px solid {THIRD_COLOR};border-radius: 9px;background-color: {SECONDARY_COLOR};}}QCheckBox::indicator:checked {{background-color: {ACCENT_COLOR};border: 4px solid {SECONDARY_COLOR};}}QCheckBox::indicator:checked:hover {{background-color: #ff5a52;}}QScrollArea {{border: 1px solid {THIRD_COLOR};background-color: {SECONDARY_COLOR};border-radius: 8px;}}QScrollBar:vertical {{background-color: {SECONDARY_COLOR};width: 12px;border-radius: 6px;}}QScrollBar::handle:vertical {{background-color: {THIRD_COLOR};border-radius: 6px;min-height: 20px;}}QScrollBar::handle:vertical:hover {{background-color: {HOVER_COLOR};}}QWidget#scroll_content {{background-color: {SECONDARY_COLOR};}}"""
        )

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QtWidgets.QHBoxLayout()
        icon_label = QtWidgets.QLabel("⚠️")
        icon_label.setStyleSheet(
            f"""QLabel {{font-size: 32px;color: {ACCENT_COLOR};background-color: transparent;}}"""
        )
        icon_label.setFixedSize(40, 40)

        header_text = QtWidgets.QLabel("Sélectionnez les playlists à supprimer")
        header_text.setStyleSheet(
            f"""QLabel {{font-size: 18px;font-weight: bold;color: {PRINCIPAL_TEXT_COLOR};background-color: transparent;}}"""
        )
        header_layout.addWidget(icon_label)
        header_layout.addWidget(header_text)
        header_layout.addStretch()

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_widget.setObjectName("scroll_content")
        self.radio_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.radio_layout.setSpacing(8)
        self.radio_layout.setContentsMargins(16, 16, 16, 16)

        self.radio_buttons = []
        for playlist in self.playlists:
            radio = QtWidgets.QCheckBox(playlist)
            self.radio_layout.addWidget(radio)
            self.radio_buttons.append(radio)

        self.radio_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(12)

        self.btn_cancel = QtWidgets.QPushButton("Annuler")
        self.btn_cancel.setStyleSheet(
            f"""QPushButton {{background-color: {THIRD_COLOR};color: {PRINCIPAL_TEXT_COLOR};padding: 10px 24px;border-radius: 6px;border: none;font-weight: 600;}}QPushButton:hover {{background-color: {HOVER_COLOR};}}QPushButton:pressed {{background-color: {PRESSED_COLOR};}}"""
        )
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_delete = QtWidgets.QPushButton("Supprimer")
        self.btn_delete.setStyleSheet(
            f"""QPushButton {{background-color: {ACCENT_COLOR};color: {PRINCIPAL_TEXT_COLOR};padding: 10px 24px;border-radius: 6px;border: none;font-weight: 600;}}QPushButton:hover {{background-color: #ff5a52;}}QPushButton:pressed {{background-color: #d70015;}}QPushButton:disabled {{background-color: {THIRD_COLOR};color: #8e8e93;}}"""
        )
        self.btn_delete.clicked.connect(self.show_confirm_dialog)
        self.btn_delete.setEnabled(False)

        for radio in self.radio_buttons:
            radio.toggled.connect(self.update_delete_button)

        button_layout.addStretch()
        button_layout.addWidget(self.btn_cancel)
        button_layout.addWidget(self.btn_delete)

        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.scroll_area)
        main_layout.addLayout(button_layout)

        self.update_delete_button()

    def update_delete_button(self):
        has_selection = any(radio.isChecked() for radio in self.radio_buttons)
        self.btn_delete.setEnabled(has_selection)

    def get_selected_playlists(self):
        return [radio.text() for radio in self.radio_buttons if radio.isChecked()]

    def show_confirm_dialog(self):
        selected = self.get_selected_playlists()
        if not selected:
            return

        self.confirm_dialog = QtWidgets.QDialog(self)
        self.confirm_dialog.setWindowTitle("Confirmer la suppression")
        self.confirm_dialog.setModal(True)
        self.confirm_dialog.setFixedSize(500, 350)

        self.confirm_dialog.setStyleSheet(
            f"""QDialog {{background-color: {PRINCIPAL_COLOR};font-family: 'Segoe UI', Arial, sans-serif;}}QLabel {{color: {PRINCIPAL_TEXT_COLOR};background-color: transparent;}}QTextEdit {{background-color: {SECONDARY_COLOR};color: {PRINCIPAL_TEXT_COLOR};border: 1px solid {THIRD_COLOR};border-radius: 6px;padding: 10px;font-size: 14px;}}"""
        )

        confirm_layout = QtWidgets.QVBoxLayout(self.confirm_dialog)
        confirm_layout.setSpacing(16)
        confirm_layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QtWidgets.QHBoxLayout()
        confirm_icon = QtWidgets.QLabel("⚠️")
        confirm_icon.setStyleSheet(
            f"""QLabel {{font-size: 32px;color: {ACCENT_COLOR};background-color: transparent;}}"""
        )
        confirm_icon.setFixedSize(40, 40)

        confirm_title = QtWidgets.QLabel("Confirmer la suppression")
        confirm_title.setStyleSheet(
            f"""QLabel {{font-size: 18px;font-weight: bold;color: {PRINCIPAL_TEXT_COLOR};background-color: transparent;}}"""
        )
        header_layout.addWidget(confirm_icon)
        header_layout.addWidget(confirm_title)
        header_layout.addStretch()

        message_widget = QtWidgets.QWidget()
        message_widget.setStyleSheet("background-color: transparent;")
        message_layout = QtWidgets.QVBoxLayout(message_widget)
        message_layout.setSpacing(12)
        message_layout.setContentsMargins(0, 0, 0, 0)

        if len(selected) == 1:
            main_message = QtWidgets.QLabel(f"Supprimer la playlist '{selected[0]}' ?")
        else:
            main_message = QtWidgets.QLabel(f"Supprimer {len(selected)} playlists ?")
        main_message.setStyleSheet(
            f"""QLabel {{font-size: 16px;font-weight: 500;color: {PRINCIPAL_TEXT_COLOR};background-color: transparent;}}"""
        )

        warning_label = QtWidgets.QLabel("Cette action est irréversible.")
        warning_label.setStyleSheet(
            f"""QLabel {{font-size: 14px;color: {ACCENT_COLOR};font-weight: 500;background-color: transparent;}}"""
        )

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

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(12)

        btn_back = QtWidgets.QPushButton("Revoir la sélection")
        btn_back.setStyleSheet(
            f"""QPushButton {{background-color: transparent;color: {PRINCIPAL_TEXT_COLOR};padding: 10px 20px;border: 1px solid {THIRD_COLOR};border-radius: 6px;font-weight: 500;}}QPushButton:hover {{background-color: {HOVER_COLOR};border-color: {HOVER_COLOR};}}QPushButton:pressed {{background-color: {PRESSED_COLOR};}}"""
        )
        btn_back.clicked.connect(self.back_to_selection)

        btn_confirm_cancel = QtWidgets.QPushButton("Annuler")
        btn_confirm_cancel.setStyleSheet(
            f"""QPushButton {{background-color: {THIRD_COLOR};color: {PRINCIPAL_TEXT_COLOR};padding: 10px 24px;border-radius: 6px;border: none;font-weight: 600;}}QPushButton:hover {{background-color: {HOVER_COLOR};}}QPushButton:pressed {{background-color: {PRESSED_COLOR};}}"""
        )
        btn_confirm_cancel.clicked.connect(self.cancel_confirm)

        btn_confirm_delete = QtWidgets.QPushButton("Supprimer")
        btn_confirm_delete.setStyleSheet(
            f"""QPushButton {{background-color: {ACCENT_COLOR};color: {PRINCIPAL_TEXT_COLOR};padding: 10px 24px;border-radius: 6px;border: none;font-weight: 600;}}QPushButton:hover {{background-color: #ff5a52;}}QPushButton:pressed {{background-color: #d70015;}}"""
        )
        btn_confirm_delete.clicked.connect(self.final_delete)

        button_layout.addWidget(btn_back)
        button_layout.addStretch()
        button_layout.addWidget(btn_confirm_cancel)
        button_layout.addWidget(btn_confirm_delete)

        confirm_layout.addLayout(header_layout)
        confirm_layout.addWidget(message_widget)
        confirm_layout.addStretch()
        confirm_layout.addLayout(button_layout)

        self.confirm_dialog.finished.connect(self.on_confirm_dialog_closed)
        self.confirm_dialog.show()

    def on_confirm_dialog_closed(self, result):
        if result == QtWidgets.QDialog.DialogCode.Rejected:
            if not hasattr(self, "_back_to_selection_flag") or not self._back_to_selection_flag:
                self.reject()
            else:
                self._back_to_selection_flag = False
        elif result == QtWidgets.QDialog.DialogCode.Accepted:
            self.accept()

    def back_to_selection(self):
        if self.confirm_dialog:
            self._back_to_selection_flag = True
            self.confirm_dialog.reject()

    def cancel_confirm(self):
        if self.confirm_dialog:
            self.confirm_dialog.reject()

    def final_delete(self):
        self.selected_playlists = self.get_selected_playlists()
        if self.confirm_dialog:
            self.confirm_dialog.accept()


__all__ = ["DeletePlaylistDialog", "DockWidget", "VideoListItem"]
