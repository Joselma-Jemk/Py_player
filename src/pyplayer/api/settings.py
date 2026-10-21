"""Réglages utilisateur persistants (JSON)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .io_utils import read_json, write_json_atomic

logger = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "volume": 0.45,                # 0.0 – 1.0
    "muted": False,
    "last_playlist_id": None,      # str | None
    "open_siblings": True,         # ouvrir un fichier met aussi en file les médias du même dossier
    "resume_playback": True,
    "aspect_mode": "fit",          # fit | stretch | fill
    "always_on_top": False,
    "thumbnails": True,            # miniatures au survol de la barre de progression
    "download_dir": "",            # dossier des téléchargements (vide = Vidéos/PyPlayer)
    "download_preset": "best",     # qualité choisie dans l'onglet Téléchargements
    "download_options": {},        # options avancées (voir DownloadOptions)
    "download_max_parallel": 2,
    "watch_clipboard": True,       # propose de télécharger/lire un lien copié
    "downloads_to_playlist": True, # ajoute chaque téléchargement terminé à la playlist « Téléchargements »
    "audio_device": "",            # id (base64) du périphérique de sortie, vide = défaut système
    "recent_files": [],            # list[str]
    "last_open_dir": "",
    "window_geometry": "",         # base64 de QMainWindow.saveGeometry()
    "window_state": "",            # base64 de QMainWindow.saveState()
    "playlist_panel_visible": True,
}

RECENT_LIMIT = 15


class Settings:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = Path(file_path) if file_path else None
        self._values: dict[str, Any] = dict(DEFAULTS)
        self.dirty = False
        self.load()

    def load(self) -> None:
        self._values = dict(DEFAULTS)
        if not self.file_path or not self.file_path.exists():
            return
        try:
            data = read_json(self.file_path)
        except (OSError, ValueError) as error:
            logger.warning("settings.json illisible (%s) : valeurs par défaut", error)
            return
        if isinstance(data, dict):
            for key, default in DEFAULTS.items():
                if key in data and self._valid(data[key], default):
                    self._values[key] = data[key]
        self._values["volume"] = min(1.0, max(0.0, float(self._values["volume"])))

    @staticmethod
    def _valid(value: Any, default: Any) -> bool:
        if default is None:
            return value is None or isinstance(value, str)
        if isinstance(default, bool):
            return isinstance(value, bool)
        if isinstance(default, float):
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        return isinstance(value, type(default))

    def get(self, key: str) -> Any:
        return self._values[key]

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULTS:
            raise KeyError(key)
        if key == "volume":
            value = min(1.0, max(0.0, float(value)))
        if self._values.get(key) != value:
            self._values[key] = value
            self.dirty = True

    # ------------------------------------------------------------------ récents
    def add_recent(self, path: str | Path) -> None:
        text = str(path)
        recent = [p for p in self._values["recent_files"] if p != text]
        recent.insert(0, text)
        self.set("recent_files", recent[:RECENT_LIMIT])

    def clear_recent(self) -> None:
        self.set("recent_files", [])

    def save(self) -> bool:
        if not self.dirty or not self.file_path:
            return True
        try:
            write_json_atomic(self.file_path, {"version": 1, **self._values})
            self.dirty = False
            return True
        except OSError as error:
            logger.error("Impossible d'écrire %s : %s", self.file_path, error)
            return False
