"""Modèle d'un média de playlist."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .media import path_key


@dataclass(eq=False)
class Video:
    """Un fichier média et ses métadonnées en cache.

    L'égalité est celle de l'identité d'objet : deux ``Video`` de playlists différentes
    sont distinctes même si elles pointent vers le même fichier.
    L'état de lecture (position, vu/non vu) vit dans :class:`~pyplayer.api.resume.ResumeStore`.
    """

    path: Path
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)
    size: int = 0
    duration: int = 0  # ms
    width: int = 0
    height: int = 0
    added_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    @classmethod
    def from_path(cls, path: str | Path) -> "Video":
        video = cls(Path(path))
        try:
            video.size = video.path.stat().st_size
        except OSError:
            video.size = 0
        return video

    # ------------------------------------------------------------------ propriétés
    @property
    def name(self) -> str:
        return self.path.name

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    @property
    def parent(self) -> Path:
        return self.path.parent

    @property
    def key(self) -> str:
        return path_key(self.path)

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}" if self.width > 0 and self.height > 0 else ""

    @property
    def aspect_ratio(self) -> float:
        return round(self.width / self.height, 3) if self.width > 0 and self.height > 0 else 0.0

    def exists(self) -> bool:
        try:
            return self.path.is_file()
        except OSError:
            return False

    def update_metadata(self, *, width: int = 0, height: int = 0, duration: int = 0) -> bool:
        """Met à jour les métadonnées connues (valeurs > 0 uniquement). Retourne True si quelque chose a changé."""
        changed = False
        if width > 0 and width != self.width:
            self.width, changed = int(width), True
        if height > 0 and height != self.height:
            self.height, changed = int(height), True
        if duration > 0 and duration != self.duration:
            self.duration, changed = int(duration), True
        return changed

    # ------------------------------------------------------------------ sérialisation
    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "path": str(self.path),
            "size": self.size,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "added_at": self.added_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Video":
        """Accepte le format v2 (``path``) et le format historique v1 (``file_path`` + ``state``)."""
        raw_path = data.get("path") or data.get("file_path")
        if not raw_path:
            raise ValueError("entrée de playlist sans chemin")

        duration = _as_int(data.get("duration"))
        legacy_state = data.get("state")
        if not duration and isinstance(legacy_state, dict):
            duration = _as_int(legacy_state.get("duration"))

        return cls(
            path=Path(raw_path),
            uid=str(data.get("uid") or uuid.uuid4().hex),
            size=_as_int(data.get("size")),
            duration=duration,
            width=_as_int(data.get("width")),
            height=_as_int(data.get("height")),
            added_at=as_timestamp(data.get("added_at")),
        )

    @staticmethod
    def legacy_position(data: dict[str, Any]) -> int:
        """Position (ms) stockée par l'ancien format v1, 0 si absente."""
        state = data.get("state")
        return _as_int(state.get("position")) if isinstance(state, dict) else 0

    def __repr__(self) -> str:
        return f"Video({self.name!r}, {self.resolution or '?'}, {self.duration}ms)"


def as_timestamp(value: object, default: float | None = None) -> float:
    """Horodatage tolérant : nombre, chaîne numérique ou date ISO (format de l'ancienne version). Jamais d'exception."""
    fallback = time.time() if default is None else default
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value) if value == value and abs(value) < 1e14 else fallback
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(value).timestamp()
        except (ValueError, OverflowError, OSError):
            return fallback
    return fallback


def _as_int(value: object) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return 0
