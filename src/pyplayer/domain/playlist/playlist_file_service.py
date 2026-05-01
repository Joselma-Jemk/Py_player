"""Playlist file service — save/load/backup operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.pyplayer.infrastructure.persistence.io_utils import write_json_atomic

logger = logging.getLogger(__name__)


class PlaylistFileService:
    """Handles playlist file I/O operations."""

    @staticmethod
    def save_to_file(
        file_path: Path,
        data: dict,
        create_backup: bool = True,
    ) -> bool:
        """Save playlist data to file with optional backup."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if create_backup and file_path.exists():
                backup_path = file_path.with_suffix(f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Backup cree: {backup_path}")
                except Exception as e:
                    logger.warning(f"Impossible de creer le backup: {e}")

            write_json_atomic(file_path, data, indent=2, ensure_ascii=False)
            logger.info(f"Playlist sauvegardee: {file_path}")
            return True
        except IOError as e:
            logger.error(f"Erreur d'E/S lors de la sauvegarde: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de format JSON: {e}")
            return False
        except Exception as e:
            logger.exception(f"Erreur inattendue lors de la sauvegarde: {e}")
            return False

    @staticmethod
    def load_from_file(file_path: Path) -> Optional[dict]:
        """Load playlist data from file."""
        if not file_path.exists():
            logger.error(f"Fichier introuvable: {file_path}")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Fichier JSON corrompu: {file_path} - {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors du chargement de {file_path}: {e}")
            return None

    @classmethod
    def try_load_from_backup(
        cls,
        original_path: Path,
        validate_files: bool = True,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[dict]:
        """Try to load playlist data from most recent backup file."""
        try:
            backup_pattern = original_path.with_suffix(".backup.*.json")
            backups = list(original_path.parent.glob(backup_pattern.name))
            if not backups:
                logger.error(f"Aucun backup trouve pour {original_path}")
                return None

            backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            latest_backup = backups[0]
            logger.info(f"Tentative de chargement depuis backup: {latest_backup}")

            with open(latest_backup, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Echec du chargement depuis backup: {e}")
            return None