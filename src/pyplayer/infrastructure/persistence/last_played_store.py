"""Last-played state persistence."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src.pyplayer.infrastructure.persistence.io_utils import write_json_fast

logger = logging.getLogger(__name__)


class LastPlayedStore:
    """Manages reading/writing of last_played.json."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = Path(file_path)

    def load(self) -> dict:
        """Load last-played data. Returns empty dict if missing."""
        try:
            if self.file_path.exists():
                import json
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as error:
            logger.error("Erreur chargement last_played: %s", error)
        return {}

    def save(self, playlist_id: str | None) -> None:
        """Save last-played entry."""
        try:
            data = {
                "playlist_id": playlist_id,
                "timestamp": datetime.now().isoformat(),
            }
            write_json_fast(self.file_path, data, indent=2, ensure_ascii=False)
            logger.debug("Derniere playlist sauvegardee")
        except Exception as error:
            logger.error("Erreur sauvegarde derniere playlist: %s", error)