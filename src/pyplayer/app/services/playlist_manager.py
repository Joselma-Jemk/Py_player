"""PlaylistManager — orchestrator for playlist lifecycle."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.pyplayer.app.services.playlist_registry import PlaylistRegistry
from src.pyplayer.domain.playlist import Playlist
from src.pyplayer.infrastructure.backup.backup_cleaner import BackupCleaner
from src.pyplayer.infrastructure.config.settings import CONFIG
from src.pyplayer.infrastructure.persistence.manager_config_store import ManagerConfigStore
from src.pyplayer.infrastructure.persistence.playlist_repository import PlaylistRepository
from src.pyplayer.infrastructure.persistence.last_played_store import LastPlayedStore

logger = logging.getLogger(__name__)


class PlaylistManager:
    """
    Gestionnaire de playlists — orchestrateur léger.
    Délègue la logique technique aux modules spécialisés.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        registry: Optional[PlaylistRegistry] = None,
        repository: Optional[PlaylistRepository] = None,
        config_store: Optional[ManagerConfigStore] = None,
        last_played_store: Optional[LastPlayedStore] = None,
        backup_cleaner: Optional[BackupCleaner] = None,
    ):
        if data_dir:
            self.data_dir = Path(data_dir)
            self.data_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.data_dir = CONFIG.runtime_dir / "playlists"
            self.data_dir.mkdir(parents=True, exist_ok=True)

        self._config_file = self.data_dir / "manager_config.json"
        self._last_played_file = self.data_dir / "last_played.json"

        # Inject dependencies or create defaults
        self._registry = registry if registry is not None else PlaylistRegistry()
        self._repository = repository if repository is not None else PlaylistRepository(self.data_dir)
        self._config_store = config_store if config_store is not None else ManagerConfigStore(self._config_file)
        self._last_played_store = last_played_store if last_played_store is not None else LastPlayedStore(self._last_played_file)
        self._backup_cleaner = backup_cleaner if backup_cleaner is not None else BackupCleaner(self.data_dir)

        self._volume: float = 0.45
        self._last_played_id: Optional[str] = None
        self._active_playlist_id: Optional[str] = None

        self._load_config()
        self._load_all_playlists()

        self._backup_cleaner.auto_cleanup_backups_if_needed(threshold_count=5)

        if self.playlist_count == 0:
            self.create_playlist(name="PLAYLIST")

        if self.active_playlist is None:
            for playlist_id, playlist in self._registry.iterate_items():
                self.set_active_playlist_by_name(playlist.name)
                break

        logger.info(
            "PlaylistManager initialise: %s playlists chargees",
            self.playlist_count,
        )

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        self._save_config()

    @property
    def active_playlist(self) -> Optional[Playlist]:
        if self._active_playlist_id:
            return self._registry.get(self._active_playlist_id)
        return None

    @property
    def all_playlist(self) -> Dict[str, Playlist]:
        return self._registry.all_items()

    @property
    def last_played_playlist(self) -> Optional[Playlist]:
        if self._last_played_id:
            return self._registry.get(self._last_played_id)
        return None

    @property
    def playlist_count(self) -> int:
        return len(self._registry)

    @property
    def playlist_ids(self) -> List[str]:
        return self._registry.all_ids()

    @property
    def playlist_names(self) -> Dict[str, str]:
        return self._registry.names_map()

    def create_playlist(
        self,
        source_path: Optional[Path] = None,
        name: Optional[str] = None,
    ) -> Playlist:
        try:
            playlist = Playlist(source_path)
            if name:
                playlist.name = name

            base_name = source_path.stem if source_path else playlist.name.replace(" ", "_")
            file_name = self._repository.generate_filename(base_name)
            save_path = self.data_dir / file_name

            playlist.set_auto_save(save_path)
            self._registry.add(playlist)
            self._repository.save(playlist)
            self._save_config()

            logger.info("Playlist creee: %s", playlist.name)
            return playlist

        except Exception as error:
            logger.error("Erreur creation playlist: %s", error)
            raise

    def load_playlist(self, playlist_id: str) -> Optional[Playlist]:
        return self._registry.get(playlist_id)

    def get_playlist(self, playlist_id: str) -> Optional[Playlist]:
        return self.load_playlist(playlist_id)

    def set_active_playlist(self, playlist_id: str) -> bool:
        if playlist_id not in self._registry:
            logger.error("Playlist non trouvee: %s", playlist_id)
            return False

        self._active_playlist_id = playlist_id
        self._last_played_id = playlist_id

        self._last_played_store.save(self._last_played_id)
        self._save_config()

        logger.info("Playlist active: %s", playlist_id)
        return True

    def set_active_playlist_by_name(self, name: str) -> bool:
        for playlist_id, playlist in self._registry.iterate_items():
            if playlist.name == name:
                return self.set_active_playlist(playlist_id)

        logger.error("Playlist non trouvee: %s", name)
        return False

    def save_all_playlists(self) -> bool:
        success = True
        for playlist in self._registry.iterate_items():
            if hasattr(playlist, "save_file_path") and playlist.save_file_path:
                if not playlist.save_to_file(playlist.save_file_path):
                    success = False
                    logger.error("Echec sauvegarde: %s", playlist.name)

        if success:
            logger.info("Toutes les playlists sauvegardees")

        return success

    def remove_playlist(self, playlist_id: str, delete_file: bool = True) -> bool:
        if playlist_id not in self._registry:
            return False

        playlist = self._registry.get(playlist_id)

        if delete_file and hasattr(playlist, "save_file_path") and playlist.save_file_path:
            self._repository.delete_file(playlist)

        self._registry.remove(playlist_id)

        if playlist_id == self._active_playlist_id:
            self._active_playlist_id = None

        if playlist_id == self._last_played_id:
            self._last_played_id = None

        self._save_config()

        logger.info("Playlist supprimee: %s", playlist.name)
        return True

    def rename_playlist(self, playlist_id: str, new_name: str) -> bool:
        if playlist_id not in self._registry:
            return False

        playlist = self._registry.get(playlist_id)
        playlist.name = new_name

        if hasattr(playlist, "_auto_save_if_needed"):
            playlist._auto_save_if_needed()

        self._save_config()

        logger.info("Playlist renommee: %s", playlist.name)
        return True

    def get_all_playlists(self) -> List[Dict[str, Any]]:
        playlists: List[Dict[str, Any]] = []
        for playlist_id, playlist in self._registry.iterate_items():
            playlists.append({
                "id": playlist_id,
                "name": playlist.name,
                "description": playlist.description,
                "video_count": playlist.total,
                "total_duration": playlist.total_duration,
                "is_active": playlist_id == self._active_playlist_id,
                "is_last_played": playlist_id == self._last_played_id,
                "path": str(playlist.path) if playlist.path else None,
                "save_path": (
                    str(playlist.save_file_path)
                    if hasattr(playlist, "save_file_path") and playlist.save_file_path
                    else None
                ),
            })
        return playlists

    def find_playlist_by_name(self, name: str) -> List[str]:
        return self._registry.find_all_by_name(name)

    def find_playlist(self, search_term: str, search_by: str = "name") -> Optional[Playlist]:
        search_term_lower = search_term.lower().strip()

        for playlist_id, playlist in self._registry.iterate_items():
            try:
                if search_by == "id":
                    if playlist_id == search_term:
                        return playlist
                elif search_by == "name":
                    if search_term_lower in playlist.name.lower():
                        return playlist
                elif search_by == "path":
                    if playlist.path and search_term_lower in str(playlist.path).lower():
                        return playlist
                    if hasattr(playlist, "save_file_path") and playlist.save_file_path:
                        if search_term_lower in str(playlist.save_file_path).lower():
                            return playlist
                elif search_by == "description":
                    if playlist.description and search_term_lower in playlist.description.lower():
                        return playlist
                elif search_by == "all":
                    if (
                        search_term_lower in playlist.name.lower()
                        or playlist_id == search_term
                        or (playlist.path and search_term_lower in str(playlist.path).lower())
                        or (playlist.description and search_term_lower in playlist.description.lower())
                    ):
                        return playlist
            except AttributeError:
                continue

        return None

    def get_playlist_info(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        if playlist_id not in self._registry:
            return None

        playlist = self._registry.get(playlist_id)

        return {
            "id": playlist_id,
            "name": playlist.name,
            "description": playlist.description,
            "video_count": playlist.total,
            "total_duration": playlist.total_duration,
            "current_index": playlist.current_index,
            "play_mode": str(playlist.play_mode),
            "path": str(playlist.path) if playlist.path else None,
            "created_at": playlist.unique_id,
            "is_active": playlist_id == self._active_playlist_id,
            "is_last_played": playlist_id == self._last_played_id,
        }

    def cleanup(self) -> Dict[str, int]:
        removed = 0
        cleaned = 0

        for playlist in list(self._registry.iterate_items()):
            if hasattr(playlist, "remove_missing_files"):
                removed_videos = playlist.remove_missing_files()
                if removed_videos:
                    removed += len(removed_videos)
                    cleaned += 1
                    logger.info(
                        "Playlist nettoyee: %s (%s videos supprimees)",
                        playlist.name,
                        len(removed_videos),
                    )

        if removed > 0:
            self.save_all_playlists()

        return {
            "playlists_cleaned": cleaned,
            "videos_removed": removed,
        }

    def cleanup_backups(
        self,
        max_backups_per_playlist: int = 5,
        max_total_backups: int = 50,
        delete_older_than_days: Optional[int] = 30,
    ) -> Dict[str, Any]:
        return self._backup_cleaner.cleanup(
            max_backups_per_playlist=max_backups_per_playlist,
            max_total_backups=max_total_backups,
            delete_older_than_days=delete_older_than_days,
        )

    def _group_backups_by_playlist(self, backup_files: List[Path]) -> Dict[str, List[Path]]:
        return self._backup_cleaner._group_by_playlist(backup_files)

    def auto_cleanup_backups_if_needed(
        self,
        threshold_count: int = 100,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        return self._backup_cleaner.auto_cleanup_backups_if_needed(
            threshold_count=threshold_count,
            force=force,
        )

    def get_backup_stats(self) -> Dict[str, Any]:
        return self._backup_cleaner.get_stats()

    def _load_config(self) -> None:
        config = self._config_store.load()
        self._last_played_id = config.get("last_played_id")
        self._active_playlist_id = config.get("active_playlist_id") or self._last_played_id
        self._volume = config.get("volume", 0.45)
        logger.debug("Configuration chargee")

    def _save_config(self) -> None:
        self._config_store.save(
            volume=self._volume,
            last_played_id=self._last_played_id,
            active_playlist_id=self._active_playlist_id,
            playlist_count=len(self._registry),
        )

    def _load_all_playlists(self) -> None:
        for playlist in self._repository.load_all():
            self._registry.add(playlist)

    def _generate_filename(self, base_name: str) -> str:
        return self._repository.generate_filename(base_name)

    def __str__(self) -> str:
        active = f" (active: {self._active_playlist_id})" if self._active_playlist_id else ""
        return f"PlaylistManager[{self.playlist_count} playlists{active}]"

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, playlist_id: str) -> bool:
        return playlist_id in self._registry

    def __getitem__(self, playlist_id: str) -> Playlist:
        return self._registry[playlist_id]