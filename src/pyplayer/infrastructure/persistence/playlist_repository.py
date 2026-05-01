"""Playlist persistence — load/save playlists from filesystem."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from src.pyplayer.domain.playlist import Playlist

logger = logging.getLogger(__name__)


class PlaylistRepository:
    """Handles loading and saving Playlist objects to/from disk."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> List[Playlist]:
        """Load all *.json playlist files from data_dir, skipping config files."""
        config_files = {
            self.data_dir / "manager_config.json",
            self.data_dir / "last_played.json",
        }
        playlists: List[Playlist] = []

        for file_path in self.data_dir.glob("*.json"):
            if file_path in config_files:
                continue
            try:
                playlist = Playlist.load_from_file(file_path)
                if playlist:
                    playlist.set_auto_save(file_path)
                    playlists.append(playlist)
                    logger.debug("Playlist chargee: %s", playlist.name)
            except Exception as error:
                logger.error("Erreur chargement %s: %s", file_path, error)

        logger.info("%s fichiers playlist trouves, %s charges",
                     len(list(self.data_dir.glob("*.json"))) - len(config_files),
                     len(playlists))
        return playlists

    def save(self, playlist: Playlist) -> bool:
        """Save a single playlist to its auto-save path."""
        if not hasattr(playlist, "save_file_path") or not playlist.save_file_path:
            logger.warning("Playlist sans save_path: %s", playlist.name)
            return False
        try:
            return playlist.save_to_file(playlist.save_file_path, create_backup=False)
        except Exception as error:
            logger.error("Echec sauvegarde playlist %s: %s", playlist.name, error)
            return False

    def save_all(self, playlists: List[Playlist]) -> bool:
        """Save multiple playlists."""
        success = True
        for playlist in playlists:
            if not self.save(playlist):
                success = False
        return success

    def delete_file(self, playlist: Playlist) -> bool:
        """Delete the playlist file from disk."""
        path = getattr(playlist, "save_file_path", None)
        if not path:
            return False
        try:
            if path.exists():
                path.unlink()
                logger.info("Fichier supprime: %s", path)
            return True
        except Exception as error:
            logger.error("Erreur suppression fichier: %s", error)
            return False

    def generate_filename(self, base_name: str) -> str:
        """Generate a unique filename for a playlist."""
        import re
        clean_name = re.sub(r"[^\w\s-]", "", base_name)
        clean_name = re.sub(r"[-\s]+", "_", clean_name).strip("-_")

        counter = 1
        while True:
            filename = f"{clean_name}.json" if counter == 1 else f"{clean_name}_{counter}.json"
            if not (self.data_dir / filename).exists():
                return filename
            counter += 1