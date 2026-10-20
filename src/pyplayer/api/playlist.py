"""Playlist : ordre des médias, vidéo courante, modes de lecture et sérialisation.

Conception :

* La vidéo courante est référencée par **objet** (pas par index) : supprimer, déplacer ou trier
  ne peut donc jamais la désynchroniser.
* Le mode aléatoire tire au sort parmi les vidéos pas encore jouées du « tour » en cours ; il reste
  donc cohérent après un saut manuel, une suppression ou un ajout.
* Les modifications marquent ``dirty`` ; l'écriture sur disque est faite par le gestionnaire
  (``PlaylistManager.flush``), jamais à chaque tick de lecture.
"""

from __future__ import annotations

import random
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

from .media import is_media, natural_key, path_key, scan_folder
from .video import Video, as_timestamp

SCHEMA_VERSION = 2
HISTORY_LIMIT = 100


class PlayMode(str, Enum):
    NORMAL = "normal"
    LOOP_ONE = "loop_one"
    LOOP_ALL = "loop_all"
    SHUFFLE = "shuffle"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_value(cls, value: object, default: "PlayMode | None" = None) -> "PlayMode":
        try:
            return cls(value)
        except ValueError:
            return default or cls.NORMAL

    # Compatibilité avec l'ancienne API
    @classmethod
    def from_dict(cls, data: object) -> "PlayMode":
        return cls.from_value(data)

    def to_dict(self) -> str:
        return self.value


SORT_KEYS: dict[str, Callable[[Video], Any]] = {
    "name": lambda v: natural_key(v.name),
    "path": lambda v: natural_key(str(v.path)),
    "date": lambda v: v.added_at,
    "size": lambda v: v.size,
    "duration": lambda v: v.duration,
}


class Playlist:
    """Liste ordonnée de :class:`Video` avec navigation selon le :class:`PlayMode`."""

    def __init__(self, name: str = "Playlist", *, source: Path | None = None,
                 description: str = "", kind: str = "user", playlist_id: str | None = None) -> None:
        self.id: str = playlist_id or uuid.uuid4().hex
        self.name = name
        self.description = description
        self.kind = kind  # "user" | "quick"
        self.source: Path | None = Path(source) if source else None
        self.play_mode = PlayMode.NORMAL
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.file_path: Path | None = None  # renseigné par le gestionnaire
        self.dirty = False

        self.videos: list[Video] = []
        self._by_key: dict[str, Video] = {}
        self._current: Video | None = None
        self._played: set[int] = set()     # id() des vidéos déjà jouées dans le tour aléatoire en cours
        self._history: list[Video] = []    # vidéos jouées avant la courante (pour « précédent » en aléatoire)
        self._legacy_positions: dict[str, tuple[int, int]] = {}  # migration v1 : clé → (position, durée) → ResumeStore
        self.legacy_id: str | None = None                        # ancien identifiant v1 (hash du dossier)

    # ------------------------------------------------------------------ conteneur
    def __len__(self) -> int:
        return len(self.videos)

    def __bool__(self) -> bool:
        """Une playlist vide reste une playlist : sans cela, ``if not playlist`` la confondrait avec « aucune »."""
        return True

    def __iter__(self) -> Iterator[Video]:
        return iter(self.videos)

    def __getitem__(self, index: int) -> Video:
        return self.videos[index]

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Video):
            return any(v is item for v in self.videos)
        if isinstance(item, (str, Path)):
            return path_key(item) in self._by_key
        return False

    @property
    def total(self) -> int:
        return len(self.videos)

    @property
    def total_duration(self) -> int:
        return sum(v.duration for v in self.videos if v.duration > 0)

    def mark_dirty(self) -> None:
        self.dirty = True
        self.updated_at = time.time()

    def find(self, path: str | Path) -> Video | None:
        return self._by_key.get(path_key(path))

    def get(self, uid: str) -> Video | None:
        for video in self.videos:
            if video.uid == uid:
                return video
        return None

    def index_of(self, video: Video | str | Path | None) -> int:
        """Index d'une vidéo (objet, chemin ou uid), -1 si absente."""
        if video is None:
            return -1
        if not isinstance(video, Video):
            video = self.find(video) or self.get(str(video))
            if video is None:
                return -1
        for i, candidate in enumerate(self.videos):
            if candidate is video:
                return i
        return -1

    # ------------------------------------------------------------------ ajout / suppression
    def add(self, path: str | Path) -> Video | None:
        """Ajoute un fichier média. Retourne la ``Video`` ajoutée, ou ``None`` (inexistant, non média, doublon)."""
        added = self._add_one(Path(path))
        if added:
            self.mark_dirty()
        return added

    def add_many(self, paths: Iterable[str | Path]) -> list[Video]:
        """Ajoute plusieurs fichiers en une opération (une seule marque ``dirty``)."""
        added = [v for v in (self._add_one(Path(p)) for p in paths) if v]
        if added:
            self.mark_dirty()
        return added

    def add_folder(self, folder: str | Path, *, recursive: bool = True) -> list[Video]:
        """Ajoute tous les médias d'un dossier (tri naturel). Dossier invalide → liste vide."""
        folder = Path(folder)
        if not folder.is_dir():
            return []
        return self.add_many(scan_folder(folder, recursive=recursive))

    def refresh_from_source(self) -> list[Video]:
        """Réanalyse le dossier source et ajoute les nouveaux fichiers."""
        if self.source is None:
            return []
        return self.add_folder(self.source)

    def _add_one(self, path: Path) -> Video | None:
        if not is_media(path):
            return None
        key = path_key(path)
        if key in self._by_key:
            return None
        try:
            if not path.is_file():
                return None
        except OSError:
            return None
        video = Video.from_path(path)
        self._attach(video, key)
        return video

    def _attach(self, video: Video, key: str | None = None) -> None:
        self.videos.append(video)
        self._by_key[key or video.key] = video

    def remove(self, video: Video | int | str | Path) -> bool:
        """Supprime une vidéo (objet, index, chemin ou uid)."""
        target = self._resolve(video)
        return target is not None and self.remove_many([target]) == 1

    def remove_many(self, videos: Iterable[Video | int | str | Path]) -> int:
        """Supprime plusieurs vidéos. Retourne le nombre de suppressions effectives."""
        targets: list[Video] = []
        seen: set[int] = set()
        for item in videos:
            video = self._resolve(item)
            if video is not None and id(video) not in seen:
                seen.add(id(video))
                targets.append(video)
        if not targets:
            return 0

        removed_ids = {id(v) for v in targets}
        self.videos = [v for v in self.videos if id(v) not in removed_ids]
        self._by_key = {v.key: v for v in self.videos}
        self._played -= removed_ids
        self._history = [v for v in self._history if id(v) not in removed_ids]
        if self._current is not None and id(self._current) in removed_ids:
            self._current = None
        self.mark_dirty()
        return len(targets)

    def remove_missing(self) -> list[Video]:
        missing = [v for v in self.videos if not v.exists()]
        self.remove_many(missing)
        return missing

    def clear(self) -> None:
        self.videos.clear()
        self._by_key.clear()
        self._played.clear()
        self._history.clear()
        self._current = None
        self.mark_dirty()

    def _resolve(self, item: Video | int | str | Path | None) -> Video | None:
        if isinstance(item, Video):
            return item if self.index_of(item) >= 0 else None
        if isinstance(item, bool):
            return None
        if isinstance(item, int):
            return self.videos[item] if 0 <= item < len(self.videos) else None
        if isinstance(item, (str, Path)):
            return self.find(item) or self.get(str(item))
        return None

    # ------------------------------------------------------------------ réorganisation
    def move(self, from_index: int, to_index: int) -> bool:
        """Déplace une vidéo : après l'opération elle se trouve à ``to_index``."""
        n = len(self.videos)
        if not (0 <= from_index < n and 0 <= to_index < n):
            return False
        if from_index != to_index:
            self.videos.insert(to_index, self.videos.pop(from_index))
            self.mark_dirty()
        return True

    def swap(self, first: int, second: int) -> bool:
        n = len(self.videos)
        if not (0 <= first < n and 0 <= second < n):
            return False
        if first != second:
            self.videos[first], self.videos[second] = self.videos[second], self.videos[first]
            self.mark_dirty()
        return True

    def reorder(self, new_order: Sequence[Video]) -> bool:
        """Applique un nouvel ordre (mêmes vidéos, autre séquence). Refuse si l'ensemble diffère."""
        if len(new_order) != len(self.videos) or {id(v) for v in new_order} != {id(v) for v in self.videos}:
            return False
        if all(a is b for a, b in zip(new_order, self.videos)):
            return True
        self.videos = list(new_order)
        self.mark_dirty()
        return True

    def sort(self, by: str = "name", *, reverse: bool = False) -> None:
        if by not in SORT_KEYS:
            raise ValueError(f"critère de tri inconnu : {by!r} (attendu : {', '.join(SORT_KEYS)})")
        self.videos.sort(key=SORT_KEYS[by], reverse=reverse)
        self.mark_dirty()

    # ------------------------------------------------------------------ vidéo courante
    @property
    def current(self) -> Video | None:
        return self._current

    @property
    def current_index(self) -> int:
        return self.index_of(self._current)

    def set_current(self, video: Video | int | str | Path | None, *, remember: bool = True) -> Video | None:
        """Définit la vidéo courante (saut manuel). ``None`` efface la sélection."""
        target = self._resolve(video) if video is not None else None
        if video is not None and target is None:
            return self._current
        if remember and self._current is not None and target is not self._current:
            self._push_history(self._current)
        self._current = target
        self._mark_played(target)
        self.mark_dirty()
        return target

    def ensure_current(self) -> Video | None:
        """Retourne la vidéo courante ; si aucune, active la première (ou la première de l'ordre aléatoire)."""
        if self._current is not None:
            return self._current
        if not self.videos:
            return None
        first = random.choice(self.videos) if self.play_mode is PlayMode.SHUFFLE else self.videos[0]
        return self.set_current(first, remember=False)

    # ------------------------------------------------------------------ modes de lecture
    def set_mode(self, mode: PlayMode) -> None:
        mode = PlayMode.from_value(mode)
        if mode is self.play_mode:
            return
        self.play_mode = mode
        self._history.clear()
        self._played = {id(self._current)} if self._current is not None else set()
        self.mark_dirty()

    # Alias de compatibilité
    set_play_mode = set_mode

    # ------------------------------------------------------------------ navigation
    def next(self, *, auto: bool = False) -> Video | None:
        """Passe à la vidéo suivante et la rend courante.

        ``auto=True`` : fin naturelle d'un média (``LOOP_ONE`` rejoue la même vidéo).
        ``auto=False`` : action de l'utilisateur (« suivant » avance vraiment, même en ``LOOP_ONE``).
        Retourne ``None`` en fin de liste (mode ``NORMAL``) : la vidéo courante est alors inchangée.
        """
        if not self.videos:
            return None
        if self._current is None:
            return self.ensure_current()

        mode = self.play_mode
        if mode is PlayMode.LOOP_ONE and auto:
            return self._current

        if mode is PlayMode.SHUFFLE:
            return self._shuffle_next()

        index = self.current_index
        if index + 1 < len(self.videos):
            target = self.videos[index + 1]
        elif mode in (PlayMode.LOOP_ALL, PlayMode.LOOP_ONE):
            target = self.videos[0]
        else:
            return None
        return self._move_to(target)

    def previous(self) -> Video | None:
        """Passe à la vidéo précédente. ``None`` si on est déjà au début (modes non cycliques)."""
        if not self.videos:
            return None
        if self._current is None:
            return self.ensure_current()

        mode = self.play_mode
        if mode is PlayMode.SHUFFLE:
            while self._history:
                candidate = self._history.pop()
                if self.index_of(candidate) >= 0:
                    return self._move_to(candidate, remember=False)
            return None

        index = self.current_index
        if index > 0:
            target = self.videos[index - 1]
        elif mode in (PlayMode.LOOP_ALL, PlayMode.LOOP_ONE):
            target = self.videos[-1]
        else:
            return None
        return self._move_to(target, remember=False)

    def _move_to(self, target: Video, *, remember: bool = True) -> Video:
        if remember and self._current is not None and target is not self._current:
            self._push_history(self._current)
        self._current = target
        self._mark_played(target)
        self.mark_dirty()
        return target

    def _push_history(self, video: Video) -> None:
        if self._history and self._history[-1] is video:
            return
        self._history.append(video)
        if len(self._history) > HISTORY_LIMIT:
            del self._history[: len(self._history) - HISTORY_LIMIT]

    # ------------------------------------------------------------------ aléatoire
    def _mark_played(self, video: Video | None) -> None:
        if self.play_mode is PlayMode.SHUFFLE and video is not None:
            self._played.add(id(video))

    def _shuffle_next(self) -> Video | None:
        """Tire au sort une vidéo pas encore jouée ; quand tout est joué, démarre un nouveau tour sans répéter la courante."""
        current = self._current
        candidates = [v for v in self.videos if id(v) not in self._played and v is not current]
        if not candidates:
            self._played = {id(current)} if current is not None else set()
            candidates = [v for v in self.videos if v is not current] or list(self.videos)
        target = random.choice(candidates)
        if current is not None and target is not current:
            self._push_history(current)
        self._current = target
        self._played.add(id(target))
        self.mark_dirty()
        return target

    # ------------------------------------------------------------------ sérialisation
    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "source": str(self.source) if self.source else None,
            "play_mode": self.play_mode.value,
            "current": str(self._current.path) if self._current else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "videos": [v.to_dict() for v in self.videos],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Playlist":
        """Reconstruit une playlist (formats v2 et v1 historique). Lève uniquement ``ValueError`` si les données sont inutilisables."""
        try:
            return cls._from_dict(data)
        except ValueError:
            raise
        except (TypeError, KeyError, AttributeError, OverflowError, OSError, RecursionError) as error:
            raise ValueError(f"playlist invalide : {error}") from error

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Playlist":
        if not isinstance(data, dict):
            raise ValueError("une playlist doit être un objet JSON")

        version = data.get("version")
        legacy = "unique_id" in data or "current_index" in data or "playlist_state" in data \
            or (isinstance(version, str) and version.startswith("1"))
        if not legacy:
            # Un objet JSON quelconque n'est pas une playlist : il faut la signature du format v2.
            if version != SCHEMA_VERSION or not isinstance(data.get("id"), str) or not data["id"] \
                    or not isinstance(data.get("name"), str):
                raise ValueError("format de playlist inconnu (version/id/nom manquants)")
        source = data.get("source") if not legacy else data.get("path")
        playlist = cls(
            name=str(data.get("name") or "Playlist"),
            source=Path(source) if source else None,
            description=str(data.get("description") or ""),
            kind=str(data.get("kind") or "user"),
            playlist_id=None if legacy else (str(data["id"]) if data.get("id") else None),
        )
        playlist.play_mode = PlayMode.from_value(data.get("play_mode"))
        if legacy and data.get("unique_id"):
            playlist.legacy_id = str(data["unique_id"])
        playlist.created_at = as_timestamp(data.get("created_at"), playlist.created_at)
        playlist.updated_at = as_timestamp(data.get("updated_at"), playlist.created_at) if not legacy else playlist.updated_at

        raw_videos = data.get("videos")
        if not isinstance(raw_videos, list):
            raise ValueError("liste de vidéos absente ou invalide")
        if raw_videos and not any(isinstance(r, dict) and (r.get("path") or r.get("file_path")) for r in raw_videos):
            raise ValueError("aucune entrée de playlist exploitable : fichier probablement corrompu")
        for raw in raw_videos:
            try:
                video = Video.from_dict(raw)
            except (ValueError, TypeError, AttributeError):
                continue  # entrée corrompue : ignorée, le reste de la playlist est conservé
            if video.key in playlist._by_key:
                continue
            playlist.videos.append(video)
            playlist._by_key[video.key] = video
            position = Video.legacy_position(raw)
            if position:
                playlist._legacy_positions[video.key] = (position, video.duration)

        current_path: str | None = None
        if legacy:
            index = data.get("current_index", -1)
            if isinstance(index, int) and 0 <= index < len(playlist.videos):
                current_path = str(playlist.videos[index].path)
        else:
            current_path = data.get("current")
        if current_path:
            playlist._current = playlist.find(current_path)

        if playlist.play_mode is PlayMode.SHUFFLE and playlist._current is not None:
            playlist._played = {id(playlist._current)}
        playlist.dirty = legacy  # un ancien fichier est réécrit au nouveau format
        return playlist

    def __repr__(self) -> str:
        return f"Playlist({self.name!r}, {len(self.videos)} médias, {self.play_mode.value})"
