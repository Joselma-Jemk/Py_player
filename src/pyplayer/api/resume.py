"""Mémoire de reprise de lecture, indépendante des playlists.

Une seule source de vérité pour « où en est-on dans ce fichier » : la position n'est plus
dupliquée dans chaque playlist, ce qui évite de réécrire les playlists à chaque seconde.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from .io_utils import read_json, write_json_atomic
from .media import path_key

logger = logging.getLogger(__name__)

MAX_ENTRIES = 1000
MIN_RESUME_MS = 5_000        # en dessous : on repart du début
END_MARGIN_MS = 10_000       # à moins de 10 s de la fin : considéré comme terminé…
END_RATIO = 0.03             # …ou dans les 3 % finaux pour les médias courts (marge = le plus petit des deux)


class ResumeStore:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = Path(file_path) if file_path else None
        self._entries: dict[str, dict[str, Any]] = {}
        self.dirty = False
        self.load()

    # ------------------------------------------------------------------ persistance
    def load(self) -> None:
        self._entries = {}
        if not self.file_path or not self.file_path.exists():
            return
        try:
            data = read_json(self.file_path)
        except (OSError, ValueError) as error:
            logger.warning("resume.json illisible (%s) : repart de zéro", error)
            return
        entries = data.get("entries") if isinstance(data, dict) else None
        if isinstance(entries, dict):
            for key, raw in entries.items():
                entry = self._clean(raw)
                if entry is not None:
                    self._entries[str(key)] = entry

    def save(self) -> bool:
        if not self.dirty or not self.file_path:
            return True
        try:
            write_json_atomic(self.file_path, {"version": 1, "entries": self._entries}, indent=None)
            self.dirty = False
            return True
        except OSError as error:
            logger.error("Impossible d'écrire %s : %s", self.file_path, error)
            return False

    @staticmethod
    def _clean(raw: object) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        try:
            return {
                "pos": max(0, int(raw.get("pos", 0))),
                "dur": max(0, int(raw.get("dur", 0))),
                "ts": float(raw.get("ts", 0.0)),
                "done": bool(raw.get("done", False)),
            }
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------ API
    def position(self, path: str | Path) -> int:
        """Position de reprise en ms (0 = repartir du début)."""
        entry = self._entries.get(path_key(path))
        if not entry or entry["done"] or entry["pos"] < MIN_RESUME_MS:
            return 0
        return entry["pos"]

    def update(self, path: str | Path, position: int, duration: int = 0) -> None:
        """Enregistre la position courante. Début ou fin de média : l'entrée est supprimée/marquée terminée."""
        key = path_key(path)
        position, duration = max(0, int(position)), max(0, int(duration))

        if duration and self._is_near_end(position, duration):
            self._set(key, {"pos": 0, "dur": duration, "ts": time.time(), "done": True})
        elif position < MIN_RESUME_MS:
            if key in self._entries and not self._entries[key]["done"]:
                del self._entries[key]
                self.dirty = True
        else:
            self._set(key, {"pos": position, "dur": duration, "ts": time.time(), "done": False})

    def mark_finished(self, path: str | Path) -> None:
        key = path_key(path)
        previous = self._entries.get(key, {})
        self._set(key, {"pos": 0, "dur": previous.get("dur", 0), "ts": time.time(), "done": True})

    def is_finished(self, path: str | Path) -> bool:
        entry = self._entries.get(path_key(path))
        return bool(entry and entry["done"])

    def progress(self, path: str | Path, duration: int = 0) -> float:
        """Avancement 0.0–1.0 (1.0 si terminé)."""
        entry = self._entries.get(path_key(path))
        if not entry:
            return 0.0
        if entry["done"]:
            return 1.0
        total = duration or entry["dur"]
        return min(1.0, entry["pos"] / total) if total > 0 else 0.0

    def forget(self, path: str | Path) -> None:
        if self._entries.pop(path_key(path), None) is not None:
            self.dirty = True

    def import_position(self, path_key_value: str, position: int, duration: int = 0) -> None:
        """Migration depuis l'ancien format : n'écrase jamais une entrée existante, ignore début et fin de média."""
        position, duration = int(position), max(0, int(duration))
        if path_key_value in self._entries or position < MIN_RESUME_MS:
            return
        if duration and self._is_near_end(position, duration):
            return
        self._set(path_key_value, {"pos": position, "dur": duration, "ts": 0.0, "done": False})

    def __len__(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------ interne
    @staticmethod
    def _is_near_end(position: int, duration: int) -> bool:
        margin = min(END_MARGIN_MS, int(duration * END_RATIO))
        return position >= duration - margin

    def _set(self, key: str, entry: dict[str, Any]) -> None:
        self._entries[key] = entry
        self.dirty = True
        if len(self._entries) > MAX_ENTRIES:
            oldest = sorted(self._entries, key=lambda k: self._entries[k]["ts"])
            for stale in oldest[: len(self._entries) - MAX_ENTRIES]:
                del self._entries[stale]
