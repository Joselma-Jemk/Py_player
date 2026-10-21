"""Boîtes de dialogue de l'application (même charte graphique que le reste de l'interface)."""

from __future__ import annotations

import html
import os
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from pyplayer import APP_AUTHOR, APP_NAME, APP_URL, __version__
from pyplayer.api import media, paths
from pyplayer.ui import theme as constant

GREEN = "#4CAF50"


def _flat_button_style(color: str = constant.PRINCIPAL_TEXT_COLOR, hover_bg: str = constant.HOVER_COLOR,
                       bg: str = constant.THIRD_COLOR, hover_color: str | None = None) -> str:
    hover_color = hover_color or color
    return f"""
        QPushButton {{ background-color: {bg}; color: {color}; }}
        QPushButton:hover {{ background-color: {hover_bg}; color: {hover_color}; }}
        QPushButton:disabled {{ background-color: {constant.THIRD_COLOR}; color: #8e8e93; }}
    """


class NewPlaylistDialog(QtWidgets.QDialog):
    """Création d'une playlist depuis un dossier (nom, dossier, description)."""

    def __init__(self, parent=None, start_dir: str = ""):
        super().__init__(parent)
        self.start_dir = start_dir or str(Path.home())
        self._media_count = 0
        self.setWindowTitle("Créer une nouvelle playlist")
        self.setModal(True)
        self.setMinimumWidth(450)
        self._build()

    # ------------------------------------------------------------------ interface
    def _build(self):
        self.setStyleSheet(f"""
            QDialog {{ background-color: {constant.PRINCIPAL_COLOR}; font-family: 'Segoe UI', Arial, sans-serif; }}
            QLabel {{ color: {constant.PRINCIPAL_TEXT_COLOR}; background-color: transparent; }}
            QLineEdit, QTextEdit {{
                background-color: {constant.SECONDARY_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR};
                border: 1px solid {constant.THIRD_COLOR}; border-radius: 4px; padding: 6px;
            }}
            QLineEdit:focus, QTextEdit:focus {{ border: 1px solid {constant.ACCENT_COLOR}; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: 600; }}
        """)

        self.edit_folder = QtWidgets.QLineEdit()
        self.edit_folder.setPlaceholderText("Sélectionnez un dossier contenant des vidéos...")
        self.btn_browse = QtWidgets.QPushButton("📂 Parcourir...")
        self.btn_browse.setFixedWidth(120)
        self.btn_browse.setStyleSheet(_flat_button_style())

        self.edit_name = QtWidgets.QLineEdit()
        self.edit_name.setPlaceholderText("Ex: Mes Favoris, Chill Vibes...")
        self.edit_desc = QtWidgets.QTextEdit()
        self.edit_desc.setMaximumHeight(100)
        self.edit_desc.setPlaceholderText("Description optionnelle de la playlist...")

        self.folder_label = QtWidgets.QLabel("")
        self.name_label = QtWidgets.QLabel("")
        for label in (self.folder_label, self.name_label):
            label.setVisible(False)

        self.btn_save = QtWidgets.QPushButton("Créer la playlist")
        self.btn_save.setStyleSheet(_flat_button_style(color=GREEN, hover_bg=GREEN,
                                                       hover_color=constant.PRINCIPAL_TEXT_COLOR))
        self.btn_cancel = QtWidgets.QPushButton("Annuler")
        self.btn_cancel.setStyleSheet(_flat_button_style())
        self.btn_save.setEnabled(False)
        self.btn_save.setDefault(True)

        folder_row = QtWidgets.QHBoxLayout()
        folder_row.addWidget(self.edit_folder)
        folder_row.addWidget(self.btn_browse)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_save)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(QtWidgets.QLabel("Dossier de destination :"))
        layout.addLayout(folder_row)
        layout.addWidget(self.folder_label)
        layout.addSpacing(10)
        layout.addWidget(QtWidgets.QLabel("Nom de la playlist :"))
        layout.addWidget(self.edit_name)
        layout.addWidget(self.name_label)
        layout.addSpacing(10)
        layout.addWidget(QtWidgets.QLabel("Description :"))
        layout.addWidget(self.edit_desc)
        layout.addStretch(1)
        layout.addLayout(buttons)

        # La vérification du dossier (parcours récursif) est différée pour ne pas tourner à chaque frappe.
        self._check_timer = QtCore.QTimer(self)
        self._check_timer.setSingleShot(True)
        self._check_timer.setInterval(350)
        self._check_timer.timeout.connect(self._check_folder)

        self.btn_browse.clicked.connect(self._browse)
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.edit_folder.textChanged.connect(self._on_folder_text_changed)
        self.edit_name.textChanged.connect(self._update_state)
        self._name_auto = True                                  # le nom suit le dossier tant qu'on ne l'a pas modifié
        self.edit_name.textEdited.connect(lambda _text: setattr(self, "_name_auto", False))

    # ------------------------------------------------------------------ logique
    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier contenant des vidéos", self.start_dir)
        if folder:
            self.edit_folder.setText(folder)
            if self._name_auto or not self.edit_name.text().strip():
                self.edit_name.setText(Path(folder).name or "nouvelle_playlist")

    def _on_folder_text_changed(self):
        text = self.edit_folder.text().strip()
        if text and (self._name_auto or not self.edit_name.text().strip()):
            self.edit_name.setText(Path(text).name or "nouvelle_playlist")   # setText n'émet pas textEdited
        self._media_count = 0
        self._set_folder_message("", ok=False)
        self._check_timer.start()
        self._update_state()

    def _set_folder_message(self, text: str, ok: bool):
        color = GREEN if ok else constant.ACCENT_COLOR
        self.folder_label.setStyleSheet(
            f"QLabel {{ color: {color}; font-size: 12px; background-color: transparent; }}")
        self.folder_label.setText(text)
        self.folder_label.setVisible(bool(text))

    def _check_folder(self):
        text = self.edit_folder.text().strip()
        self._media_count = 0
        if not text:
            self._set_folder_message("", ok=False)
        else:
            folder = Path(text)
            if not folder.exists():
                self._set_folder_message("❌ Ce dossier n'existe pas", ok=False)
            elif not folder.is_dir():
                self._set_folder_message("❌ Le chemin spécifié n'est pas un dossier", ok=False)
            elif not os.access(folder, os.R_OK | os.X_OK):
                self._set_folder_message("❌ Pas de permission de lecture dans ce dossier", ok=False)
            else:
                count, truncated = media.count_media(folder)
                if count == 0:
                    self._set_folder_message("❌ Ce dossier ne contient aucun fichier vidéo ou audio", ok=False)
                else:
                    self._media_count = count
                    plus = "+" if truncated else ""
                    word = "fichier" if count == 1 else "fichiers"
                    self._set_folder_message(f"✓ {count}{plus} {word} trouvé{'s' if count > 1 else ''}", ok=True)
        self._update_state()

    def _name_error(self) -> str:
        name = self.edit_name.text().strip()
        if not name:
            return ""
        if len(name) < 2:
            return "❌ Le nom doit avoir au moins 2 caractères"
        if len(name) > 100:
            return "❌ Le nom ne doit pas dépasser 100 caractères"
        return ""

    def _update_state(self):
        error = self._name_error()
        self.name_label.setStyleSheet(
            f"QLabel {{ color: {constant.ACCENT_COLOR}; font-size: 12px; background-color: transparent; }}")
        self.name_label.setText(error)
        self.name_label.setVisible(bool(error))
        self.btn_save.setEnabled(bool(self.edit_name.text().strip()) and not error and self._media_count > 0)

    def result_data(self) -> dict:
        return {
            "name": self.edit_name.text().strip(),
            "path": Path(self.edit_folder.text().strip()),
            "description": self.edit_desc.toPlainText().strip(),
        }

    def done(self, result):
        self._check_timer.stop()
        super().done(result)


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"À propos de {APP_NAME}")
        self.setModal(True)
        self.setFixedSize(500, 450)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #f0f0f0; }
            QLabel { color: #f0f0f0; }
        """)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(20)

        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(64, 64)
        pixmap = QtGui.QPixmap(str(paths.placeholder_icon_path()))
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(64, 64, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                               QtCore.Qt.TransformationMode.SmoothTransformation))
        else:
            icon_label.setText("🎬")
            icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        text_widget = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QtWidgets.QLabel(APP_NAME)
        title_label.setStyleSheet("QLabel { font-size: 24px; font-weight: bold; color: #0a74da; padding-top: 5px; }")
        version_label = QtWidgets.QLabel(f"Version {__version__}")
        version_label.setStyleSheet("font-size: 14px; color: #a0a0a0;")
        text_layout.addWidget(title_label)
        text_layout.addWidget(version_label)
        text_layout.addStretch()

        header.addWidget(icon_label)
        header.addWidget(text_widget)
        header.addStretch()
        header.setAlignment(icon_label, QtCore.Qt.AlignmentFlag.AlignVCenter)
        header.setAlignment(text_widget, QtCore.Qt.AlignmentFlag.AlignVCenter)
        main_layout.addLayout(header)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3a3a3a;")
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)

        formats = " • ".join(sorted(e.lstrip(".").upper() for e in media.VIDEO_EXTENSIONS)[:10]) + " …"
        info = QtWidgets.QTextBrowser()
        info.setOpenExternalLinks(True)
        info.setHtml(f"""
        <div style='margin: 10px;'>
            <p style='font-size: 11pt; color: #d0d0d0;'>
            <b>Développé par :</b> {html.escape(APP_AUTHOR)}<br><br>
            <b>Description :</b><br>
            Lecteur vidéo et audio minimaliste et rapide pour vos fichiers multimédias locaux.<br><br>
            <b>Formats supportés :</b><br>
            <span style='color: #0a74da; font-family: monospace;'>{formats}</span><br>
            et tout ce que décode FFmpeg.<br><br>
            <b>Technologies :</b><br>
            • Python<br>• Qt for Python (PySide6)<br>• FFmpeg<br>• Icônes Material Symbols<br><br>
            <b>Code source :</b> <a href='{APP_URL}' style='color:#0a74da;'>{APP_URL}</a><br><br>
            <b>Licence :</b> MIT — © 2025 Joselma.
            </p>
        </div>
        """)
        info.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        main_layout.addWidget(info)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        close_button = QtWidgets.QPushButton("Fermer")
        close_button.setFixedWidth(100)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        main_layout.addLayout(buttons)


class MediaInfoDialog(QtWidgets.QDialog):
    """Informations détaillées sur un média : résumé, fichier, conteneur, pistes, chapitres, métadonnées, pochette.

    ``rows`` : résumé affiché en tête. ``sections`` : sections supplémentaires (``InfoSection``). ``cover`` : pochette
    ou image du média (``QImage``). ``path`` : active le calcul de l'empreinte SHA-256 du fichier."""

    hash_ready = QtCore.Signal(str)

    def __init__(self, rows: list[tuple[str, str]], title: str, parent=None, *, sections=None, cover=None,
                 path: Path | str | None = None):
        super().__init__(parent)
        from pyplayer.api import mediainfo
        self._mediainfo = mediainfo
        self._title = title
        self._path = Path(path) if path else None
        self._sections = [mediainfo.InfoSection("Résumé", [(k, v) for k, v in rows if v])] + list(sections or [])
        self._cancel_hash = False
        self.setWindowTitle("Informations sur le média")
        self.setModal(True)
        self.resize(680, 560)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {constant.PRINCIPAL_COLOR}; }}
            QLabel {{ color: {constant.PRINCIPAL_TEXT_COLOR}; background: transparent; }}
            QTextBrowser {{ background-color: {constant.SECONDARY_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR};
                           border: 1px solid {constant.THIRD_COLOR}; border-radius: 6px; padding: 8px; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: 600;
                          background-color: {constant.THIRD_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR}; }}
            QPushButton:hover {{ background-color: {constant.HOVER_COLOR}; }}
            QPushButton:disabled {{ color: #8e8e93; }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QtWidgets.QLabel(title)
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        self.cover_label = QtWidgets.QLabel()
        self.cover_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        if cover is not None and not cover.isNull():
            pixmap = QtGui.QPixmap.fromImage(cover).scaledToHeight(
                140, QtCore.Qt.TransformationMode.SmoothTransformation)
            self.cover_label.setPixmap(pixmap)
            layout.addWidget(self.cover_label)
        else:
            self.cover_label.hide()

        self.browser = QtWidgets.QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self._render()
        layout.addWidget(self.browser, 1)

        self.hash_label = QtWidgets.QLabel("")
        self.hash_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        self.hash_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.hash_label.setWordWrap(True)
        self.hash_label.hide()
        layout.addWidget(self.hash_label)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_hash = QtWidgets.QPushButton("Empreinte SHA-256")
        self.btn_hash.setEnabled(self._path is not None and self._path.is_file())
        self.btn_hash.clicked.connect(self._compute_hash)
        self.hash_ready.connect(self._show_hash)
        buttons.addWidget(self.btn_hash)
        buttons.addStretch()
        self.btn_copy = QtWidgets.QPushButton("Copier")
        self.btn_copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.as_text()))
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.accept)
        buttons.addWidget(self.btn_copy)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def as_text(self) -> str:
        return self._mediainfo.to_text(self._title, self._sections)

    def _render(self) -> None:
        parts = []
        for section in self._sections:
            rows = "".join(
                f"<tr><td style='color:#a0a0a0; padding:2px 14px 2px 0; white-space:nowrap;' valign='top'>"
                f"{html.escape(k)}</td><td style='padding:2px 0;'>{html.escape(v)}</td></tr>"
                for k, v in section.rows if v)
            parts.append(f"<h3 style='color:{constant.OK_ONE_COLOR}; margin:14px 0 4px 0;'>"
                         f"{html.escape(section.title)}</h3><table cellspacing='0'>{rows}</table>")
        self.browser.setHtml("".join(parts))

    def _compute_hash(self) -> None:
        import threading
        self.btn_hash.setEnabled(False)
        self.hash_label.setText("Calcul de l'empreinte en cours…")
        self.hash_label.show()
        path = self._path

        def work():
            digest = self._mediainfo.sha256_file(path, cancelled=lambda: self._cancel_hash)
            self.hash_ready.emit(digest or "")

        threading.Thread(target=work, daemon=True).start()

    def _show_hash(self, digest: str) -> None:
        if not digest:
            self.hash_label.setText("Empreinte indisponible (fichier illisible ou calcul annulé).")
            self.btn_hash.setEnabled(True)
            return
        self.hash_label.setText(f"SHA-256 : {digest}")
        self._sections.append(self._mediainfo.InfoSection("Empreinte", [("SHA-256", digest)]))
        self._render()

    def done(self, result: int) -> None:  # noqa: N802 -- surcharge Qt
        self._cancel_hash = True                     # un calcul en cours s'arrête à la fermeture
        super().done(result)


class ResetDataDialog(QtWidgets.QDialog):
    """Suppression des données de l'application : l'utilisateur voit ce qui sera supprimé, choisit, puis confirme."""

    def __init__(self, parent=None, home: Path | None = None):
        super().__init__(parent)
        from pyplayer.api import reset
        self._reset = reset
        self.home = Path(home) if home else paths.data_dir()
        self.setWindowTitle("Réinitialiser PyPlayer")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {constant.PRINCIPAL_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR}; }}
            QLabel, QCheckBox {{ color: {constant.PRINCIPAL_TEXT_COLOR}; }}
            QCheckBox {{ padding: 4px 0; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: 600; }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        heading = QtWidgets.QLabel("Supprimer les données de l'application")
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(heading)
        where = QtWidgets.QLabel(f"Dossier : {self.home}")
        where.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        where.setWordWrap(True)
        where.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(where)
        note = QtWidgets.QLabel("Vos fichiers vidéo et audio ne sont jamais touchés, seulement les données de PyPlayer. "
                                "Cette action est <b>irréversible</b>.")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.checks: dict[str, QtWidgets.QCheckBox] = {}
        for info in reset.summarize(self.home):
            box = QtWidgets.QCheckBox(f"{info.label}  —  {info.files} fichier(s), {reset.format_size(info.size)}")
            box.setChecked(True)
            box.setEnabled(info.files > 0)
            box.toggled.connect(self._update_state)
            self.checks[info.key] = box
            layout.addWidget(box)

        self.confirm_box = QtWidgets.QCheckBox("Je comprends que ces données seront définitivement supprimées")
        self.confirm_box.toggled.connect(self._update_state)
        layout.addSpacing(6)
        layout.addWidget(self.confirm_box)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        self.btn_cancel = QtWidgets.QPushButton("Annuler")
        self.btn_cancel.setStyleSheet(_flat_button_style())
        self.btn_reset = QtWidgets.QPushButton("Tout supprimer")
        self.btn_reset.setStyleSheet(_flat_button_style(color=constant.ACCENT_COLOR, hover_bg=constant.ACCENT_COLOR,
                                                        hover_color="white"))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_reset.clicked.connect(self.accept)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_reset)
        layout.addLayout(buttons)
        self.btn_cancel.setDefault(True)
        self._update_state()

    def selected_categories(self) -> list[str]:
        return [key for key, box in self.checks.items() if box.isChecked() and box.isEnabled()]

    def _update_state(self, *_):
        self.btn_reset.setEnabled(self.confirm_box.isChecked() and bool(self.selected_categories()))


class TaskProgressDialog(QtWidgets.QDialog):
    """Exécute un travail long (téléchargement vérifié…) hors du fil de l'interface, avec progression et annulation.

    ``work(progress, cancelled)`` : ``progress(done, total)`` met la barre à jour, ``cancelled()`` vaut vrai si
    l'utilisateur a annulé. Après ``exec()``, lire ``ok``, ``result`` ou ``error``."""

    progressed = QtCore.Signal(int, int)
    finished_ok = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, title: str, label: str, work, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.work = work
        self.ok = False
        self.result = None
        self.error = ""
        self._cancel = False
        self._started = False
        self.setStyleSheet(f"""
            QDialog {{ background-color: {constant.PRINCIPAL_COLOR}; }}
            QLabel {{ color: {constant.PRINCIPAL_TEXT_COLOR}; }}
            QProgressBar {{ background-color: {constant.THIRD_COLOR}; border: none; border-radius: 4px; height: 8px; }}
            QProgressBar::chunk {{ background-color: {constant.OK_ONE_COLOR}; border-radius: 4px; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: 600;
                          background-color: {constant.THIRD_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR}; }}
            QPushButton:hover {{ background-color: {constant.HOVER_COLOR}; }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)
        self.label = QtWidgets.QLabel(label)
        self.label.setWordWrap(True)
        self.detail = QtWidgets.QLabel("")
        self.detail.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        self.bar = QtWidgets.QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 0)                         # indéterminée tant que la taille est inconnue
        self.btn_cancel = QtWidgets.QPushButton("Annuler")
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.btn_cancel)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        layout.addWidget(self.detail)
        layout.addLayout(row)
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.progressed.connect(self._on_progress)
        self.finished_ok.connect(self._on_ok)
        self.failed.connect(self._on_failed)

    def showEvent(self, event):  # noqa: N802 -- surcharge Qt
        super().showEvent(event)
        if not self._started:
            self._started = True
            import threading
            threading.Thread(target=self._run, name="pyp-task", daemon=True).start()

    def _run(self) -> None:
        try:
            result = self.work(lambda done, total: self.progressed.emit(int(done), int(total)), lambda: self._cancel)
        except Exception as error:  # noqa: BLE001 -- l'erreur est affichée, jamais perdue dans le fil
            self.failed.emit(str(error) or error.__class__.__name__)
        else:
            self.finished_ok.emit(result)

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(1000 * min(1.0, done / total)))
            self.detail.setText(f"{media.format_size(done)} / {media.format_size(total)}")
        else:
            self.detail.setText(media.format_size(done))

    def _on_cancel(self) -> None:
        self._cancel = True
        self.btn_cancel.setEnabled(False)
        self.detail.setText("Annulation…")

    def _on_ok(self, result) -> None:
        self.ok, self.result = True, result
        self.accept()

    def _on_failed(self, message: str) -> None:
        self.ok, self.error = False, message
        self.reject()


class UpdateDialog(QtWidgets.QDialog):
    """Annonce une nouvelle version avec ses notes ; l'utilisateur choisit de l'installer, de voir la page ou d'attendre."""

    INSTALL, PAGE, LATER = 1, 2, 0

    def __init__(self, info, current_version: str, parent=None):
        super().__init__(parent)
        self.info = info
        self.choice = self.LATER
        self.setWindowTitle("Mise à jour disponible")
        self.setModal(True)
        self.resize(560, 460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {constant.PRINCIPAL_COLOR}; }}
            QLabel {{ color: {constant.PRINCIPAL_TEXT_COLOR}; }}
            QTextBrowser {{ background-color: {constant.SECONDARY_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR};
                           border: 1px solid {constant.THIRD_COLOR}; border-radius: 6px; padding: 8px; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: 600;
                          background-color: {constant.THIRD_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR}; }}
            QPushButton:hover {{ background-color: {constant.HOVER_COLOR}; }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)
        heading = QtWidgets.QLabel(f"PyPlayer {info.version} est disponible")
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        sub = QtWidgets.QLabel(f"Vous utilisez la version {current_version}."
                               + (f" Téléchargement : {media.format_size(info.size)}." if info.size else ""))
        sub.setStyleSheet("color: #a0a0a0;")
        self.notes = QtWidgets.QTextBrowser()
        self.notes.setOpenExternalLinks(True)
        self.notes.setMarkdown(info.notes or "Aucune note de version.")
        self.lbl_trust = QtWidgets.QLabel(
            "Le fichier est vérifié par sa somme SHA-256 avant installation." if info.can_install else
            "Cette version ne peut pas s'installer automatiquement sur ce système : ouvrez la page pour la télécharger.")
        self.lbl_trust.setWordWrap(True)
        self.lbl_trust.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addWidget(self.notes, 1)
        layout.addWidget(self.lbl_trust)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        self.btn_later = QtWidgets.QPushButton("Plus tard")
        self.btn_page = QtWidgets.QPushButton("Voir la page")
        self.btn_install = QtWidgets.QPushButton("Mettre à jour maintenant")
        self.btn_install.setEnabled(info.can_install)
        self.btn_install.setStyleSheet(f"QPushButton {{ background-color: {GREEN}; color: white; }}"
                                       "QPushButton:hover { background-color: #66BB6A; }"
                                       f"QPushButton:disabled {{ background-color: {constant.THIRD_COLOR}; color: #8e8e93; }}")
        for button in (self.btn_later, self.btn_page, self.btn_install):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.btn_later.clicked.connect(lambda: self._choose(self.LATER))
        self.btn_page.clicked.connect(lambda: self._choose(self.PAGE))
        self.btn_install.clicked.connect(lambda: self._choose(self.INSTALL))

    def _choose(self, choice: int) -> None:
        self.choice = choice
        self.accept()
