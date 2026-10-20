"""Gestionnaire de playlists : chargement, persistance, sauvegardes, playlist active."""

from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterator

from . import paths
from .io_utils import read_json, write_json_atomic
from .m3u import read_playlist_file, write_m3u
from .media import path_key
from .playlist import Playlist
from .resume import ResumeStore
from .settings import Settings

logger = logging.getLogger(__name__)

DEFAULT_PLAYLIST_NAME = "PLAYLIST"
QUICK_PLAYLIST_NAME = "Lecture rapide"
BACKUPS_PER_PLAYLIST = 5
LEGACY_NON_PLAYLIST_FILES = {"manager_config.json", "last_played.json"}


class PlaylistManager:
    """Possède les playlists, les réglages et la mémoire de reprise.

    Disposition sur disque (``data_dir`` = ``~/.pyplayer`` par défaut)::

        playlists/<nom>-<id8>.json     une playlist par fichier
        playlists/backups/             instantanés rotatifs (jamais rechargés comme playlists)
        settings.json                  réglages
        resume.json                    positions de reprise
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else paths.data_dir()
        self.playlists_dir = self.data_dir / "playlists"
        self.backups_dir = self.playlists_dir / "backups"
        self.playlists_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        settings_path = self.data_dir / "settings.json"
        first_run_with_legacy = not settings_path.exists()
        self.settings = Settings(settings_path)
        self.resume = ResumeStore(self.data_dir / "resume.json")

        self._playlists: dict[str, Playlist] = {}
        self._active_id: str | None = None
        self._legacy_last_played: str | None = None

        self._migrate_stray_backups()
        if first_run_with_legacy:
            self._import_legacy_config()
        self._load_all()
        self._ensure_at_least_one()
        self._restore_active()
        logger.info("PlaylistManager : %d playlist(s) chargée(s) depuis %s", len(self._playlists), self.playlists_dir)

    # ------------------------------------------------------------------ accès
    @property
    def playlists(self) -> list[Playlist]:
        return list(self._playlists.values())

    def __len__(self) -> int:
        return len(self._playlists)

    def __iter__(self) -> Iterator[Playlist]:
        return iter(self._playlists.values())

    def __contains__(self, playlist_id: object) -> bool:
        return playlist_id in self._playlists

    def get(self, playlist_id: str | None) -> Playlist | None:
        return self._playlists.get(playlist_id) if playlist_id else None

    @property
    def active(self) -> Playlist:
        """Playlist active. Il y en a toujours une (le gestionnaire en recrée une vide si besoin)."""
        playlist = self._playlists.get(self._active_id or "")
        if playlist is None:
            self._ensure_at_least_one()
            playlist = next(iter(self._playlists.values()))
            self._active_id = playlist.id
        return playlist

    @property
    def volume(self) -> float:
        return float(self.settings.get("volume"))

    @volume.setter
    def volume(self, value: float) -> None:
        self.settings.set("volume", value)  # écrit par flush(), pas à chaque cran du slider

    # ------------------------------------------------------------------ opérations
    def create_playlist(self, name: str | None = None, source_path: Path | str | None = None,
                        description: str = "", kind: str = "user") -> Playlist:
        """Crée (et enregistre) une playlist, éventuellement remplie depuis un dossier ou un fichier."""
        source = Path(source_path) if source_path else None
        base_name = (name or (source.name if source and source.name else DEFAULT_PLAYLIST_NAME)).strip()
        playlist = Playlist(
            self._unique_name(base_name),
            source=source if source and source.is_dir() else None,
            description=description,
            kind=kind,
        )
        if source:
            if source.is_dir():
                playlist.add_folder(source)
            elif source.is_file():
                playlist.add(source)
        self._register(playlist)
        self._write(playlist)
        return playlist

    def quick_playlist(self) -> Playlist:
        """Playlist « Lecture rapide » : reçoit les fichiers ouverts depuis l'explorateur, la ligne de commande ou le glisser-déposer."""
        for playlist in self._playlists.values():
            if playlist.kind == "quick":
                return playlist
        return self.create_playlist(QUICK_PLAYLIST_NAME, kind="quick")

    def set_active(self, playlist_id: str) -> bool:
        if playlist_id not in self._playlists:
            logger.error("Playlist introuvable : %s", playlist_id)
            return False
        self._active_id = playlist_id
        self.settings.set("last_playlist_id", playlist_id)
        return True

    def rename(self, playlist_id: str, new_name: str) -> bool:
        playlist = self._playlists.get(playlist_id)
        new_name = new_name.strip()
        if playlist is None or not new_name:
            return False
        playlist.name = new_name
        playlist.mark_dirty()
        return True

    def remove_playlist(self, playlist_id: str) -> bool:
        """Supprime une playlist (fichier et sauvegardes comprises) et choisit une nouvelle playlist active."""
        playlist = self._playlists.pop(playlist_id, None)
        if playlist is None:
            return False
        if playlist.file_path:
            try:
                playlist.file_path.unlink(missing_ok=True)
                for backup in self.backups_dir.glob(f"{playlist.file_path.stem}.*.json"):
                    backup.unlink(missing_ok=True)
            except OSError as error:
                logger.error("Suppression de %s impossible : %s", playlist.file_path, error)
        if self._active_id == playlist_id:
            self._active_id = None
        self._ensure_at_least_one()
        if self._active_id is None:
            self._active_id = next(iter(self._playlists))
            self.settings.set("last_playlist_id", self._active_id)
        return True

    # ------------------------------------------------------------------ M3U
    def import_playlist_file(self, file_path: Path | str) -> Playlist:
        """Importe un fichier .m3u/.m3u8/.pls comme nouvelle playlist."""
        name, media = read_playlist_file(file_path)
        playlist = self.create_playlist(name or "Playlist importée")
        playlist.add_many(media)
        self._write(playlist)
        return playlist

    def export_playlist(self, playlist: Playlist, destination: Path | str) -> None:
        write_m3u(((v.path, v.stem, v.duration) for v in playlist), destination)

    # ------------------------------------------------------------------ persistance
    def flush(self) -> bool:
        """Écrit tout ce qui a changé (playlists, réglages, reprise). Appelé par un timer et à la fermeture."""
        ok = True
        for playlist in self._playlists.values():
            if playlist.dirty:
                ok &= self._write(playlist)
        ok &= self.settings.save()
        ok &= self.resume.save()
        return ok

    def _write(self, playlist: Playlist) -> bool:
        if playlist.file_path is None:
            playlist.file_path = self.playlists_dir / self._file_name(playlist)
        try:
            write_json_atomic(playlist.file_path, playlist.to_dict(), indent=None)
            playlist.dirty = False
            return True
        except OSError as error:
            logger.error("Sauvegarde de %r impossible : %s", playlist.name, error)
            return False

    def _register(self, playlist: Playlist) -> None:
        while playlist.id in self._playlists:  # collision d'ID (fichier copié à la main, etc.)
            playlist.id = Playlist().id
            playlist.mark_dirty()
        self._playlists[playlist.id] = playlist

    # ------------------------------------------------------------------ chargement
    def _load_all(self) -> None:
        for file_path in sorted(self.playlists_dir.glob("*.json")):
            if file_path.name in LEGACY_NON_PLAYLIST_FILES:
                continue
            playlist = self._load_file(file_path)
            if playlist is None:
                continue
            playlist.file_path = file_path
            self._register(playlist)
            for key, (position, duration) in playlist._legacy_positions.items():
                self.resume.import_position(key, position, duration)
            playlist._legacy_positions.clear()
            self._snapshot(file_path, legacy=playlist.dirty)
            if playlist.dirty:
                self._write(playlist)  # migration v1 → v2 immédiate

    def _load_file(self, file_path: Path) -> Playlist | None:
        try:
            return Playlist.from_dict(read_json(file_path))
        except (OSError, ValueError) as error:
            logger.error("Playlist illisible %s : %s", file_path.name, error)

        restored = self._restore_from_backup(file_path)
        if restored is not None:
            return restored
        quarantine = file_path.with_suffix(".corrupt")
        try:
            file_path.replace(quarantine)
            logger.error("%s mis en quarantaine : %s", file_path.name, quarantine.name)
        except OSError:
            pass
        return None

    def _restore_from_backup(self, file_path: Path) -> Playlist | None:
        backups = sorted(self.backups_dir.glob(f"{file_path.stem}.*.json"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        for backup in backups:
            try:
                playlist = Playlist.from_dict(read_json(backup))
            except (OSError, ValueError):
                continue
            logger.warning("%s restauré depuis %s", file_path.name, backup.name)
            playlist.dirty = True
            return playlist
        return None

    def _snapshot(self, file_path: Path, *, legacy: bool = False) -> None:
        """Copie de sécurité au démarrage (dédupliquée), rotation à ``BACKUPS_PER_PLAYLIST``."""
        try:
            existing = sorted(self.backups_dir.glob(f"{file_path.stem}.*.json"),
                              key=lambda p: p.stat().st_mtime)
            content = file_path.read_bytes()
            if existing and not legacy and existing[-1].read_bytes() == content:
                return
            label = "v1" if legacy else datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(file_path, self.backups_dir / f"{file_path.stem}.{label}.json")
            existing = sorted(self.backups_dir.glob(f"{file_path.stem}.*.json"),
                              key=lambda p: p.stat().st_mtime)
            for stale in existing[:-BACKUPS_PER_PLAYLIST]:
                stale.unlink(missing_ok=True)
        except OSError as error:
            logger.warning("Instantané de %s impossible : %s", file_path.name, error)

    def _migrate_stray_backups(self) -> None:
        """Anciennes versions : les backups étaient dans le dossier des playlists et rechargés comme playlists."""
        for stray in self.playlists_dir.glob("*.backup.*.json"):
            try:
                shutil.move(str(stray), self.backups_dir / stray.name.replace(".backup.", ".", 1))
            except OSError as error:
                logger.warning("Backup %s non déplacé : %s", stray.name, error)

    def _import_legacy_config(self) -> None:
        legacy = self.playlists_dir / "manager_config.json"
        if not legacy.exists():
            return
        try:
            data = read_json(legacy)
            if isinstance(data, dict):
                if isinstance(data.get("volume"), (int, float)) and not isinstance(data["volume"], bool):
                    self.settings.set("volume", data["volume"])
                if isinstance(data.get("last_played_id"), str):
                    self._legacy_last_played = data["last_played_id"]
        except (OSError, ValueError):
            pass

    def _ensure_at_least_one(self) -> None:
        if not self._playlists:
            self.create_playlist(DEFAULT_PLAYLIST_NAME)

    def _restore_active(self) -> None:
        wanted = self.settings.get("last_playlist_id")
        if wanted in self._playlists:
            self._active_id = wanted
            return
        if self._legacy_last_played:                      # migration : l'ancienne « dernière playlist jouée »
            for playlist in self._playlists.values():
                if playlist.legacy_id == self._legacy_last_played:
                    self._active_id = playlist.id
                    self.settings.set("last_playlist_id", playlist.id)
                    return
        user_lists = [p for p in self._playlists.values() if p.kind != "quick"]
        self._active_id = (user_lists or list(self._playlists.values()))[0].id

    # ------------------------------------------------------------------ utilitaires
    def _unique_name(self, name: str) -> str:
        existing = {p.name.casefold() for p in self._playlists.values()}
        if name.casefold() not in existing:
            return name
        counter = 2
        while f"{name} ({counter})".casefold() in existing:
            counter += 1
        return f"{name} ({counter})"

    @staticmethod
    def _file_name(playlist: Playlist) -> str:
        slug = re.sub(r"[^\w-]+", "_", playlist.name, flags=re.UNICODE).strip("_")[:40] or "playlist"
        return f"{slug}-{playlist.id[:8]}.json"

    def find_by_source(self, folder: Path | str) -> Playlist | None:
        key = path_key(folder)
        for playlist in self._playlists.values():
            if playlist.source and path_key(playlist.source) == key:
                return playlist
        return None
