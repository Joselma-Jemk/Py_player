"""Onglet « Téléchargements » : saisie d'un lien, file d'attente, progression, actions, options avancées.

La liste est dessinée directement par un délégué (aucun widget par ligne) : des centaines d'éléments ne coûtent ni
mémoire ni temps. Les événements du moteur arrivent depuis des fils de travail et sont remis dans le fil de
l'interface par un signal Qt.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from pyplayer.api import downloads as dl
from pyplayer.api import links, online
from pyplayer.api.media import format_duration, format_size
from pyplayer.ui import theme

ItemRole = QtCore.Qt.ItemDataRole.UserRole + 1
ROW_HEIGHT = 60
QUALITIES = [("best", "Meilleure qualité"), ("1080p", "1080p maximum"), ("720p", "720p maximum"),
             ("480p", "480p maximum"), ("audio_mp3", "Audio MP3"), ("audio_m4a", "Audio M4A"),
             ("audio_opus", "Audio Opus"), ("custom", "Format personnalisé…")]
STATE_COLORS = {dl.State.RUNNING: theme.OK_ONE_COLOR, dl.State.QUEUED: "#8e8e93", dl.State.PAUSED: "#ffb300",
                dl.State.DONE: theme.GREEN, dl.State.ERROR: theme.ACCENT_COLOR, dl.State.CANCELLED: "#636366"}


def speed_text(speed: float) -> str:
    return f"{format_size(int(speed))}/s" if speed and speed > 0 else ""


def status_text(item: dl.DownloadItem) -> str:
    """Ligne d'état d'un élément (sans Qt, testée à part)."""
    percent = f"{item.progress * 100:.0f} %"
    if item.state == dl.State.RUNNING:
        parts = [percent]
        if item.total:
            parts.append(f"{format_size(item.downloaded)} / {format_size(item.total)}")
        elif item.downloaded:
            parts.append(format_size(item.downloaded))
        if item.speed:
            parts.append(speed_text(item.speed))
        if item.eta >= 0:
            parts.append(f"reste {format_duration(item.eta * 1000)}")
        return " · ".join(parts)
    if item.state == dl.State.QUEUED:
        return item.error or "En attente"
    if item.state == dl.State.PAUSED:
        return f"En pause · {percent}"
    if item.state == dl.State.DONE:
        if item.archived:
            return "Déjà téléchargé ou écarté par un filtre"
        size = ""
        try:
            size = format_size(Path(item.filepath).stat().st_size) if item.filepath else ""
        except OSError:
            size = ""
        return "Terminé" + (f" · {size}" if size else "")
    if item.state == dl.State.ERROR:
        return f"Erreur : {item.error}" if item.error else "Erreur"
    return "Annulé"


def summary_text(items: list[dl.DownloadItem]) -> str:
    counts = {state: 0 for state in dl.State}
    speed = 0.0
    for item in items:
        counts[item.state] += 1
        if item.state == dl.State.RUNNING:
            speed += item.speed or 0.0
    parts = []
    for state, label in ((dl.State.RUNNING, "en cours"), (dl.State.QUEUED, "en attente"), (dl.State.PAUSED, "en pause"),
                         (dl.State.DONE, "terminé(s)"), (dl.State.ERROR, "en erreur")):
        if counts[state]:
            parts.append(f"{counts[state]} {label}")
    if speed:
        parts.append(speed_text(speed))
    return " · ".join(parts) if parts else "Aucun téléchargement"


class DownloadsBridge(QtCore.QObject):
    """Remet dans le fil de l'interface les événements émis par les fils de téléchargement."""
    event = QtCore.Signal(str, object)
    playlist_done = QtCore.Signal(object, str)


class DownloadsModel(QtCore.QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rows: list[dl.DownloadItem] = []
        self._row_of: dict[str, int] = {}

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802 -- surcharge Qt
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        item = self.rows[index.row()]
        if role == ItemRole:
            return item
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return item.title or item.url
        return None

    def set_items(self, items: list[dl.DownloadItem]) -> None:
        self.beginResetModel()
        self.rows = list(items)
        self._row_of = {item.id: row for row, item in enumerate(self.rows)}
        self.endResetModel()

    def upsert(self, item: dl.DownloadItem) -> None:
        row = self._row_of.get(item.id)
        if row is None:
            self.beginInsertRows(QtCore.QModelIndex(), len(self.rows), len(self.rows))
            self.rows.append(item)
            self._row_of[item.id] = len(self.rows) - 1
            self.endInsertRows()
        else:
            self.rows[row] = item
            index = self.index(row)
            self.dataChanged.emit(index, index)

    def remove(self, item_id: str) -> None:
        row = self._row_of.get(item_id)
        if row is None:
            return
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        del self.rows[row]
        self._row_of = {item.id: r for r, item in enumerate(self.rows)}
        self.endRemoveRows()

    def item_at(self, index) -> dl.DownloadItem | None:
        return self.rows[index.row()] if index.isValid() and 0 <= index.row() < len(self.rows) else None


class DownloadDelegate(QtWidgets.QStyledItemDelegate):
    def sizeHint(self, option, index):  # noqa: N802 -- surcharge Qt
        return QtCore.QSize(option.rect.width(), ROW_HEIGHT)

    def paint(self, painter, option, index):
        item = index.data(ItemRole)
        if item is None:
            return
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = QtCore.QRectF(option.rect).adjusted(3, 2, -3, -2)
        selected = bool(option.state & QtWidgets.QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QtWidgets.QStyle.StateFlag.State_MouseOver)
        background = QtGui.QColor(76, 175, 80, 40) if selected else QtGui.QColor(255, 255, 255, 18 if hovered else 8)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 6, 6)

        title = item.title or item.url
        if item.group:
            title = f"{item.index:02d}  {title}" if item.index else title
        left, right = rect.left() + 10, rect.right() - 10
        font = QtGui.QFont(option.font)
        font.setPointSizeF(max(8.0, font.pointSizeF()))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(theme.PRINCIPAL_TEXT_COLOR))
        metrics = QtGui.QFontMetrics(font)
        painter.drawText(QtCore.QRectF(left, rect.top() + 6, right - left, 18),
                         QtCore.Qt.AlignmentFlag.AlignVCenter,
                         metrics.elidedText(title, QtCore.Qt.TextElideMode.ElideRight, int(right - left)))

        small = QtGui.QFont(option.font)
        small.setPointSizeF(max(7.5, small.pointSizeF() - 1))
        painter.setFont(small)
        painter.setPen(QtGui.QColor("#ff8a80" if item.state == dl.State.ERROR else "#a0a0a0"))
        text = status_text(item)
        painter.drawText(QtCore.QRectF(left, rect.top() + 25, right - left, 16), QtCore.Qt.AlignmentFlag.AlignVCenter,
                         QtGui.QFontMetrics(small).elidedText(text, QtCore.Qt.TextElideMode.ElideRight,
                                                              int(right - left)))

        bar = QtCore.QRectF(left, rect.bottom() - 11, right - left, 4)
        painter.setBrush(QtGui.QColor(theme.HOVER_COLOR))
        painter.drawRoundedRect(bar, 2, 2)
        fraction = 1.0 if item.state == dl.State.DONE else max(0.0, min(1.0, item.progress))
        if fraction > 0:
            painter.setBrush(QtGui.QColor(STATE_COLORS.get(item.state, theme.OK_ONE_COLOR)))
            painter.drawRoundedRect(QtCore.QRectF(bar.left(), bar.top(), bar.width() * fraction, bar.height()), 2, 2)
        painter.restore()


class DownloadsPanel(QtWidgets.QWidget):
    """Onglet complet : saisie, qualité, liste, actions groupées."""

    play_requested = QtCore.Signal(str)              # chemin d'un fichier téléchargé
    stream_requested = QtCore.Signal(str)            # adresse à lire en ligne pendant le téléchargement
    folder_requested = QtCore.Signal(str)
    message = QtCore.Signal(str)
    finished_item = QtCore.Signal(object)            # élément terminé (auto-ajout à la playlist, bascule locale…)
    options_changed = QtCore.Signal()
    ytdlp_missing = QtCore.Signal(str)               # texte à rejouer une fois yt-dlp installé

    def __init__(self, manager: dl.DownloadManager, settings, parent=None) -> None:
        super().__init__(parent)
        self._warned_ffmpeg = False
        self.manager = manager
        self.settings = settings
        self.bridge = DownloadsBridge(self)
        self.bridge.event.connect(self._on_event)
        self.bridge.playlist_done.connect(self._on_playlist_done)
        manager.subscribe(lambda kind, item: self.bridge.event.emit(kind, dataclasses.replace(item)))

        self.model = DownloadsModel(self)
        self._build()
        self.model.set_items([dataclasses.replace(i) for i in manager.items()])
        self._refresh_summary()
        self._clock = QtCore.QTimer(self)             # le résumé (vitesse totale) se rafraîchit une fois par seconde
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._refresh_summary)
        self._clock.start()

    # ------------------------------------------------------------------ interface
    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)
        field_style = f"""
            QLineEdit, QComboBox {{ background-color: {theme.SECONDARY_COLOR}; color: {theme.PRINCIPAL_TEXT_COLOR};
                border: 1px solid {theme.THIRD_COLOR}; border-radius: 6px; padding: 6px 8px; }}
            QLineEdit:focus, QComboBox:focus {{ border: 1px solid {theme.OK_ONE_COLOR}; }}
            QComboBox QAbstractItemView {{ background-color: {theme.SECONDARY_COLOR}; color: {theme.PRINCIPAL_TEXT_COLOR};
                selection-background-color: {theme.THIRD_COLOR}; }}
            QCheckBox {{ color: {theme.PRINCIPAL_TEXT_COLOR}; }}
        """
        button_style = f"""
            QPushButton {{ background-color: {theme.THIRD_COLOR}; color: {theme.PRINCIPAL_TEXT_COLOR};
                border: none; border-radius: 6px; padding: 7px 10px; font-weight: 600; }}
            QPushButton:hover {{ background-color: {theme.HOVER_COLOR}; }}
            QPushButton:disabled {{ color: #8e8e93; }}
        """
        self.setStyleSheet(field_style + button_style)

        top = QtWidgets.QHBoxLayout()
        self.edit_url = QtWidgets.QLineEdit()
        self.edit_url.setPlaceholderText("Coller un lien (vidéo, playlist, audio…)")
        self.edit_url.setClearButtonEnabled(True)
        self.btn_add = QtWidgets.QPushButton("Télécharger")
        self.btn_add.setStyleSheet(f"QPushButton {{ background-color: {theme.GREEN}; color: white; border-radius: 6px;"
                                   f" padding: 7px 12px; font-weight: 700; }} QPushButton:hover {{ background-color: #66BB6A; }}")
        top.addWidget(self.edit_url, 1)
        top.addWidget(self.btn_add)
        layout.addLayout(top)

        options = QtWidgets.QHBoxLayout()
        self.combo_quality = QtWidgets.QComboBox()
        for key, label in QUALITIES:
            self.combo_quality.addItem(label, key)
        self.check_playlist = QtWidgets.QCheckBox("Playlist entière")
        self.btn_options = QtWidgets.QPushButton("Options…")
        options.addWidget(self.combo_quality, 1)
        options.addWidget(self.check_playlist)
        options.addWidget(self.btn_options)
        layout.addLayout(options)

        self.view = QtWidgets.QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(DownloadDelegate(self.view))
        self.view.setUniformItemSizes(True)
        self.view.setMouseTracking(True)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setStyleSheet("QListView { background-color: rgba(30,30,30,0.7); border: 1px solid rgba(255,255,255,0.08);"
                                " border-radius: 4px; outline: none; }")
        layout.addWidget(self.view, 1)

        self.lbl_summary = QtWidgets.QLabel("")
        self.lbl_summary.setStyleSheet("color: #a0a0a0; font-size: 12px; padding: 0 2px;")
        layout.addWidget(self.lbl_summary)

        bottom = QtWidgets.QHBoxLayout()
        self.btn_pause_all = QtWidgets.QPushButton("Tout suspendre")
        self.btn_resume_all = QtWidgets.QPushButton("Tout reprendre")
        self.btn_clear = QtWidgets.QPushButton("Nettoyer")
        for button in (self.btn_pause_all, self.btn_resume_all, self.btn_clear):
            bottom.addWidget(button)
        layout.addLayout(bottom)

        self.btn_add.clicked.connect(self.submit)
        self.edit_url.returnPressed.connect(self.submit)
        self.btn_options.clicked.connect(self.options_requested)
        self.btn_pause_all.clicked.connect(self.manager.pause_all)
        self.btn_resume_all.clicked.connect(self.manager.resume_all)
        self.btn_clear.clicked.connect(self.manager.clear_finished)
        self.view.doubleClicked.connect(lambda index: self.play_item(self.model.item_at(index)))
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.combo_quality.currentIndexChanged.connect(self._remember_quality)
        saved = self.settings.get("download_preset")
        position = max(0, self.combo_quality.findData(saved))
        self.combo_quality.setCurrentIndex(position)

    options_requested = QtCore.Signal()

    # ------------------------------------------------------------------ options
    def download_folder(self) -> Path:
        chosen = (self.settings.get("download_dir") or "").strip()
        return Path(chosen) if chosen else dl.default_download_dir()

    def current_options(self, force_playlist: bool = False) -> dl.DownloadOptions:
        options = dl.DownloadOptions.from_dict(self.settings.get("download_options"))
        options.preset = self.combo_quality.currentData() or "best"
        if options.preset == "custom" and not options.custom_format:
            options.preset = "best"                    # aucun format personnalisé défini : qualité maximale
        options.playlist = options.playlist or self.check_playlist.isChecked() or force_playlist
        return options

    def _remember_quality(self) -> None:
        self.settings.set("download_preset", self.combo_quality.currentData() or "best")

    # ------------------------------------------------------------------ ajout
    def submit(self) -> None:
        self.add_text(self.edit_url.text())
        self.edit_url.clear()

    def add_text(self, text: str, *, play: bool = False) -> int:
        """Ajoute tous les liens trouvés dans ``text``. Retourne le nombre de liens pris en compte."""
        urls = links.extract_urls(text)
        if not urls:
            self.message.emit("Aucun lien valide à télécharger.")
            return 0
        if not self.manager.command_available():
            self.ytdlp_missing.emit(text)                  # l'interface propose d'installer yt-dlp, puis relance l'ajout
            return 0
        if dl.ffmpeg_dir() is None and not self._warned_ffmpeg:
            self._warned_ffmpeg = True
            self.message.emit("FFmpeg absent : qualité limitée (menu Support → Installer FFmpeg)")
        accepted = 0
        for url in urls:
            kind = links.classify(url)
            as_playlist = kind is not None and kind.kind == "playlist"
            try:
                options = self.current_options(force_playlist=as_playlist)
                folder = self.download_folder()
                if options.playlist:
                    self.manager.add_playlist(url, options, folder,
                                              on_done=lambda items, error: self.bridge.playlist_done.emit(items, error))
                    self.message.emit("Lecture de la playlist…")
                else:
                    self.manager.add(url, options, folder)
                accepted += 1
            except (ValueError, online.OnlineError) as error:
                self.message.emit(f"Téléchargement refusé : {error}")
        return accepted

    def _on_playlist_done(self, items, error: str) -> None:
        if items is None:
            self.message.emit(f"Playlist illisible : {error}")
        else:
            self.message.emit(f"{len(items)} vidéo(s) ajoutée(s) à la file")

    # ------------------------------------------------------------------ événements du moteur
    def _on_event(self, kind: str, item: dl.DownloadItem) -> None:
        if kind == "removed":
            self.model.remove(item.id)
        else:
            self.model.upsert(item)
        if kind == "state" and item.state == dl.State.DONE and item.filepath:
            self.finished_item.emit(item)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        self.lbl_summary.setText(summary_text(self.model.rows))

    # ------------------------------------------------------------------ actions sur les éléments
    def selected_items(self) -> list[dl.DownloadItem]:
        rows = sorted({i.row() for i in self.view.selectionModel().selectedIndexes()})
        return [self.model.rows[r] for r in rows if 0 <= r < len(self.model.rows)]

    def play_item(self, item: dl.DownloadItem | None) -> None:
        """Lecture « intelligente » : le fichier s'il est terminé, sinon le flux en ligne pendant le téléchargement."""
        if item is None:
            return
        if item.state == dl.State.DONE and item.filepath and Path(item.filepath).is_file():
            self.play_requested.emit(item.filepath)
        elif item.state != dl.State.DONE:
            self.stream_requested.emit(item.url)

    def _context_menu(self, position: QtCore.QPoint) -> None:
        selected = self.selected_items() or ([self.model.item_at(self.view.indexAt(position))]
                                             if self.view.indexAt(position).isValid() else [])
        selected = [i for i in selected if i is not None]
        menu = QtWidgets.QMenu(self)
        for label, action in self.actions_for(selected):
            menu.addAction(label).triggered.connect(action)
        if not menu.isEmpty():
            menu.exec(self.view.viewport().mapToGlobal(position))

    def actions_for(self, items: list[dl.DownloadItem]):
        """Actions proposées pour la sélection : liste de (libellé, fonction). Testable sans menu."""
        if not items:
            return []
        first = items[0]
        out = []
        playable = first.state == dl.State.DONE and first.filepath and Path(first.filepath).is_file()
        if playable:
            out.append(("Lire", lambda: self.play_item(first)))
            out.append(("Afficher dans le dossier", lambda: self.folder_requested.emit(first.filepath)))
        elif first.state in (dl.State.RUNNING, dl.State.QUEUED, dl.State.PAUSED):
            out.append(("Lire en ligne maintenant", lambda: self.play_item(first)))
        if any(i.state in dl.ACTIVE_STATES for i in items):
            out.append(("Mettre en pause", lambda: [self.manager.pause(i.id) for i in items]))
        if any(i.state in (dl.State.PAUSED, dl.State.ERROR, dl.State.CANCELLED) for i in items):
            label = "Réessayer" if any(i.state == dl.State.ERROR for i in items) else "Reprendre"
            out.append((label, lambda: [self.manager.resume(i.id) for i in items]))
        if any(i.state not in (dl.State.DONE, dl.State.CANCELLED) for i in items):
            out.append(("Annuler", lambda: [self.manager.cancel(i.id, delete_partial=True) for i in items]))
        out.append(("Copier le lien", lambda: QtWidgets.QApplication.clipboard().setText("\n".join(i.url for i in items))))
        out.append(("Retirer de la liste", lambda: [self.manager.remove(i.id) for i in items]))
        if any(i.filepath and Path(i.filepath).is_file() for i in items):
            out.append(("Supprimer le fichier", lambda: [self.manager.remove(i.id, delete_file=True) for i in items]))
        return out


class DownloadOptionsDialog(QtWidgets.QDialog):
    """Options avancées (presque toutes celles de yt-dlp utiles à un lecteur) : valide avant d'accepter."""

    def __init__(self, options: dl.DownloadOptions, folder: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Options de téléchargement")
        self.setModal(True)
        self.resize(560, 640)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {theme.PRINCIPAL_COLOR}; }}
            QLabel, QCheckBox, QGroupBox {{ color: {theme.PRINCIPAL_TEXT_COLOR}; }}
            QGroupBox {{ border: 1px solid {theme.THIRD_COLOR}; border-radius: 6px; margin-top: 12px; padding-top: 10px;
                font-weight: 600; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {theme.OK_ONE_COLOR}; }}
            QLineEdit, QComboBox, QSpinBox {{ background-color: {theme.SECONDARY_COLOR}; color: {theme.PRINCIPAL_TEXT_COLOR};
                border: 1px solid {theme.THIRD_COLOR}; border-radius: 5px; padding: 5px 7px; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: 600; background-color: {theme.THIRD_COLOR};
                color: {theme.PRINCIPAL_TEXT_COLOR}; }}
            QPushButton:hover {{ background-color: {theme.HOVER_COLOR}; }}
        """)
        outer = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        body = QtWidgets.QWidget()
        form_layout = QtWidgets.QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        def group(title: str) -> QtWidgets.QFormLayout:
            box = QtWidgets.QGroupBox(title)
            form = QtWidgets.QFormLayout(box)
            form_layout.addWidget(box)
            return form

        def text(value: str, placeholder: str = "") -> QtWidgets.QLineEdit:
            edit = QtWidgets.QLineEdit(value)
            edit.setPlaceholderText(placeholder)
            return edit

        def check(label: str, value: bool) -> QtWidgets.QCheckBox:
            box = QtWidgets.QCheckBox(label)
            box.setChecked(value)
            return box

        quality = group("Qualité et format")
        self.combo_preset = QtWidgets.QComboBox()
        for key, label in QUALITIES:
            self.combo_preset.addItem(label, key)
        self.combo_preset.setCurrentIndex(max(0, self.combo_preset.findData(options.preset)))
        self.edit_format = text(options.custom_format, "ex. best[height<=480]")
        self.combo_container = QtWidgets.QComboBox()
        for name in ("mp4", "mkv", "webm"):
            self.combo_container.addItem(name)
        self.combo_container.setCurrentText(options.container)
        quality.addRow("Qualité", self.combo_preset)
        quality.addRow("Format personnalisé", self.edit_format)
        quality.addRow("Conteneur vidéo", self.combo_container)

        playlist = group("Playlists")
        self.check_playlist = check("Télécharger la playlist entière", options.playlist)
        self.edit_items = text(options.playlist_items, "ex. 1-5,8 (vide = tout)")
        self.check_reverse = check("Dans l'ordre inverse", options.playlist_reverse)
        playlist.addRow(self.check_playlist)
        playlist.addRow("Éléments", self.edit_items)
        playlist.addRow(self.check_reverse)

        subtitles = group("Sous-titres")
        self.check_subs = check("Télécharger les sous-titres", options.subtitles)
        self.edit_langs = text(options.sub_langs, "fr,en")
        self.check_auto_subs = check("Inclure les sous-titres automatiques", options.auto_subs)
        self.check_embed_subs = check("Les intégrer à la vidéo", options.embed_subs)
        subtitles.addRow(self.check_subs)
        subtitles.addRow("Langues", self.edit_langs)
        subtitles.addRow(self.check_auto_subs)
        subtitles.addRow(self.check_embed_subs)

        embed = group("Intégration au fichier")
        self.check_thumb = check("Pochette / miniature", options.embed_thumbnail)
        self.check_meta = check("Métadonnées (titre, auteur, date…)", options.embed_metadata)
        self.check_chapters = check("Chapitres", options.embed_chapters)
        self.combo_sponsor = QtWidgets.QComboBox()
        for value, label in (("", "Ne rien faire"), ("mark", "Marquer comme chapitres"), ("remove", "Supprimer les segments")):
            self.combo_sponsor.addItem("SponsorBlock : " + label, value)
        self.combo_sponsor.setCurrentIndex(max(0, self.combo_sponsor.findData(options.sponsorblock)))
        for widget in (self.check_thumb, self.check_meta, self.check_chapters):
            embed.addRow(widget)
        embed.addRow(self.combo_sponsor)

        network = group("Réseau et vitesse")
        self.edit_rate = text(options.rate_limit, "ex. 2M (vide = illimité)")
        self.spin_fragments = QtWidgets.QSpinBox()
        self.spin_fragments.setRange(1, 32)
        self.spin_fragments.setValue(options.concurrent_fragments)
        self.spin_retries = QtWidgets.QSpinBox()
        self.spin_retries.setRange(0, 100)
        self.spin_retries.setValue(options.retries)
        self.edit_proxy = text(options.proxy, "ex. http://hote:3128")
        self.edit_cookies = text(options.cookies_from_browser, "ex. firefox (vidéos privées / âge)")
        self.check_aria = check("Accélérer avec aria2c (s'il est installé)", options.use_aria2c)
        network.addRow("Limite de débit", self.edit_rate)
        network.addRow("Fragments simultanés", self.spin_fragments)
        network.addRow("Tentatives", self.spin_retries)
        network.addRow("Proxy", self.edit_proxy)
        network.addRow("Cookies du navigateur", self.edit_cookies)
        network.addRow(self.check_aria)

        files = group("Fichiers")
        self.edit_folder = text(folder, "dossier par défaut")
        browse = QtWidgets.QPushButton("Parcourir…")
        browse.clicked.connect(self._browse)
        folder_row = QtWidgets.QHBoxLayout()
        folder_row.addWidget(self.edit_folder, 1)
        folder_row.addWidget(browse)
        self.edit_template = text(options.output_template, "ex. %(uploader)s/%(title)s.%(ext)s")
        self.check_archive = check("Ne pas retélécharger ce qui l'a déjà été", options.archive)
        self.check_restrict = check("Noms de fichiers simples (ASCII)", options.restrict_filenames)
        self.check_info = check("Enregistrer le fichier d'informations (.info.json)", options.write_info_json)
        self.check_desc = check("Enregistrer la description", options.write_description)
        self.edit_min = text(options.min_filesize, "ex. 50M")
        self.edit_max = text(options.max_filesize, "ex. 2G")
        self.edit_date = text(options.date_after, "AAAAMMJJ ou today-1week")
        self.edit_sections = text(options.sections, "ex. *10:00-12:00")
        files.addRow("Dossier", folder_row)
        files.addRow("Modèle de nom", self.edit_template)
        for widget in (self.check_archive, self.check_restrict, self.check_info, self.check_desc):
            files.addRow(widget)
        files.addRow("Taille minimale", self.edit_min)
        files.addRow("Taille maximale", self.edit_max)
        files.addRow("Depuis le", self.edit_date)
        files.addRow("Extrait seulement", self.edit_sections)
        form_layout.addStretch(1)

        self.lbl_error = QtWidgets.QLabel("")
        self.lbl_error.setStyleSheet(f"color: {theme.ACCENT_COLOR};")
        self.lbl_error.setWordWrap(True)
        outer.addWidget(self.lbl_error)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        cancel = QtWidgets.QPushButton("Annuler")
        self.btn_ok = QtWidgets.QPushButton("Enregistrer")
        self.btn_ok.setStyleSheet(f"QPushButton {{ background-color: {theme.GREEN}; color: white; }}"
                                  "QPushButton:hover { background-color: #66BB6A; }")
        cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.btn_ok)
        outer.addLayout(buttons)

    def _browse(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier de téléchargement", self.edit_folder.text())
        if chosen:
            self.edit_folder.setText(chosen)

    def result_options(self) -> dl.DownloadOptions:
        return dl.DownloadOptions(
            preset=self.combo_preset.currentData(), custom_format=self.edit_format.text().strip(),
            container=self.combo_container.currentText(), subtitles=self.check_subs.isChecked(),
            sub_langs=self.edit_langs.text().strip() or "fr,en", auto_subs=self.check_auto_subs.isChecked(),
            embed_subs=self.check_embed_subs.isChecked(), embed_thumbnail=self.check_thumb.isChecked(),
            embed_metadata=self.check_meta.isChecked(), embed_chapters=self.check_chapters.isChecked(),
            sponsorblock=self.combo_sponsor.currentData() or "", playlist=self.check_playlist.isChecked(),
            playlist_items=self.edit_items.text().strip(), playlist_reverse=self.check_reverse.isChecked(),
            rate_limit=self.edit_rate.text().strip(), concurrent_fragments=self.spin_fragments.value(),
            retries=self.spin_retries.value(), cookies_from_browser=self.edit_cookies.text().strip(),
            proxy=self.edit_proxy.text().strip(), archive=self.check_archive.isChecked(),
            output_template=self.edit_template.text().strip(), restrict_filenames=self.check_restrict.isChecked(),
            write_info_json=self.check_info.isChecked(), write_description=self.check_desc.isChecked(),
            min_filesize=self.edit_min.text().strip(), max_filesize=self.edit_max.text().strip(),
            date_after=self.edit_date.text().strip(), sections=self.edit_sections.text().strip(),
            use_aria2c=self.check_aria.isChecked())

    def result_folder(self) -> str:
        return self.edit_folder.text().strip()

    def _accept(self) -> None:
        try:
            dl.validate(self.result_options())
        except ValueError as error:
            self.lbl_error.setText(str(error))
            return
        self.accept()
