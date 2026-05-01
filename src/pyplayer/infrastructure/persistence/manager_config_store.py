"""Manager config persistence — read/write manager_config.json."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from src.pyplayer.infrastructure.persistence.io_utils import write_json_fast

logger = logging.getLogger(__name__)


class ManagerConfigStore:
    """Manages reading/writing of manager_config.json."""

    def __init__(self, config_file: Path) -> None:
        self.config_file = Path(config_file)

    def load(self) -> dict:
        """Load config from file. Returns defaults if missing."""
        defaults = {
            "version": "1.0",
            "volume": 0.45,
            "last_played_id": None,
            "active_playlist_id": None,
            "playlist_count": 0,
        }
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    "version": data.get("version", "1.0"),
                    "volume": data.get("volume", 0.45),
                    "last_played_id": data.get("last_played_id"),
                    "active_playlist_id": data.get("active_playlist_id", data.get("last_played_id")),
                    "playlist_count": data.get("playlist_count", 0),
                    "last_updated": data.get("last_updated"),
                }
        except Exception as error:
            logger.error("Erreur chargement configuration: %s", error)
        return defaults

    def save(
        self,
        *,
        volume: float,
        last_played_id: str | None,
        active_playlist_id: str | None,
        playlist_count: int,
    ) -> None:
        """Save config to file."""
        try:
            config = {
                "version": "1.0",
                "volume": volume,
                "last_updated": datetime.now().isoformat(),
                "playlist_count": playlist_count,
                "last_played_id": last_played_id,
                "active_playlist_id": active_playlist_id,
            }
            write_json_fast(self.config_file, config, indent=2, ensure_ascii=False)
            logger.debug("Configuration sauvegardee")
        except Exception as error:
            logger.error("Erreur sauvegarde configuration: %s", error)