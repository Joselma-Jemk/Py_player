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

    # ------------------------------------------------------------------ logique
    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier contenant des vidéos", self.start_dir)
        if folder:
            self.edit_folder.setText(folder)
            if not self.edit_name.text().strip():
                self.edit_name.setText(Path(folder).name or "nouvelle_playlist")

    def _on_folder_text_changed(self):
        text = self.edit_folder.text().strip()
        if text and not self.edit_name.text().strip():
            self.edit_name.setText(Path(text).name or "nouvelle_playlist")
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
    """Informations sur le média en cours : fichier, durée, résolution, codecs…"""

    def __init__(self, rows: list[tuple[str, str]], title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informations sur le média")
        self.setModal(True)
        self.resize(560, 420)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {constant.PRINCIPAL_COLOR}; }}
            QLabel {{ color: {constant.PRINCIPAL_TEXT_COLOR}; background: transparent; }}
            QTextBrowser {{ background-color: {constant.SECONDARY_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR};
                           border: 1px solid {constant.THIRD_COLOR}; border-radius: 6px; padding: 8px; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: 600;
                          background-color: {constant.THIRD_COLOR}; color: {constant.PRINCIPAL_TEXT_COLOR}; }}
            QPushButton:hover {{ background-color: {constant.HOVER_COLOR}; }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QtWidgets.QLabel(title)
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        body = "".join(
            f"<tr><td style='color:#a0a0a0; padding:3px 14px 3px 0; white-space:nowrap;'>{html.escape(k)}</td>"
            f"<td style='padding:3px 0;'>{html.escape(v)}</td></tr>"
            for k, v in rows if v
        )
        browser = QtWidgets.QTextBrowser()
        browser.setHtml(f"<table cellspacing='0'>{body}</table>")
        layout.addWidget(browser, 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        copy = QtWidgets.QPushButton("Copier")
        copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(
            "\n".join(f"{k}: {v}" for k, v in rows if v)))
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.accept)
        buttons.addWidget(copy)
        buttons.addWidget(close)
        layout.addLayout(buttons)
