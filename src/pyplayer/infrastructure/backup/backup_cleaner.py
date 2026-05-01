"""Backup management — cleanup and stats for playlist backup files."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BackupCleaner:
    """Handles backup file management and cleanup."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _group_by_playlist(self, backup_files: List[Path]) -> Dict[str, List[Path]]:
        """Group backup files by playlist name derived from filename."""
        grouped: Dict[str, List[Path]] = {}
        for backup_file in backup_files:
            parts = backup_file.stem.split(".")
            playlist_name = parts[0] if len(parts) >= 3 else "unknown"
            grouped.setdefault(playlist_name, []).append(backup_file)
        return grouped

    def cleanup(
        self,
        max_backups_per_playlist: int = 5,
        max_total_backups: int = 50,
        delete_older_than_days: Optional[int] = 30,
    ) -> Dict[str, Any]:
        """Execute backup cleanup with given limits."""
        results: Dict[str, Any] = {
            "total_backups_before": 0,
            "total_backups_after": 0,
            "backups_deleted_by_playlist_limit": 0,
            "backups_deleted_by_age": 0,
            "backups_deleted_by_total_limit": 0,
            "files_deleted": [],
            "errors": [],
        }

        try:
            backup_files = list(self.data_dir.glob("*.backup.*.json"))
            results["total_backups_before"] = len(backup_files)

            if not backup_files:
                logger.info("Aucun backup a nettoyer")
                return results

            # Limit per playlist
            backups_by_playlist = self._group_by_playlist(backup_files)
            for backups in backups_by_playlist.values():
                if len(backups) > max_backups_per_playlist:
                    backups.sort(key=lambda fp: fp.stat().st_mtime, reverse=True)
                    for backup_file in backups[max_backups_per_playlist:]:
                        try:
                            if backup_file.exists():
                                backup_file.unlink()
                                results["backups_deleted_by_playlist_limit"] += 1
                                results["files_deleted"].append(str(backup_file))
                                logger.debug("Backup supprime (limite playlist): %s", backup_file.name)
                        except Exception as error:
                            results["errors"].append(f"{backup_file}: {error}")

            # Age-based deletion
            if delete_older_than_days:
                cutoff_time = datetime.now().timestamp() - (delete_older_than_days * 24 * 3600)
                for backup_file in list(self.data_dir.glob("*.backup.*.json")):
                    try:
                        if backup_file.stat().st_mtime < cutoff_time:
                            backup_file.unlink()
                            results["backups_deleted_by_age"] += 1
                            results["files_deleted"].append(str(backup_file))
                            logger.debug("Backup supprime (age): %s", backup_file.name)
                    except Exception as error:
                        results["errors"].append(f"{backup_file}: {error}")

            # Global total limit
            backup_files = list(self.data_dir.glob("*.backup.*.json"))
            if len(backup_files) > max_total_backups:
                backup_files.sort(key=lambda fp: fp.stat().st_mtime)
                for backup_file in backup_files[:len(backup_files) - max_total_backups]:
                    try:
                        backup_file.unlink()
                        results["backups_deleted_by_total_limit"] += 1
                        results["files_deleted"].append(str(backup_file))
                        logger.debug("Backup supprime (limite totale): %s", backup_file.name)
                    except Exception as error:
                        results["errors"].append(f"{backup_file}: {error}")

            backup_files = list(self.data_dir.glob("*.backup.*.json"))
            results["total_backups_after"] = len(backup_files)

            total_deleted = (
                results["backups_deleted_by_playlist_limit"]
                + results["backups_deleted_by_age"]
                + results["backups_deleted_by_total_limit"]
            )
            if total_deleted > 0:
                logger.info("Nettoyage backups: %s supprimes, %s restants",
                            total_deleted, results["total_backups_after"])

            return results

        except Exception as error:
            logger.error("Erreur nettoyage backups: %s", error)
            results["errors"].append(str(error))
            return results

    def get_stats(self) -> Dict[str, Any]:
        try:
            backup_files = list(self.data_dir.glob("*.backup.*.json"))

            if not backup_files:
                return {
                    "total_count": 0,
                    "total_size_mb": 0,
                    "oldest_backup": None,
                    "newest_backup": None,
                    "by_playlist": {},
                }

            total_size = sum(fp.stat().st_size for fp in backup_files)
            backup_files.sort(key=lambda fp: fp.stat().st_mtime)
            oldest, newest = backup_files[0], backup_files[-1]

            by_playlist: Dict[str, Dict[str, Any]] = {}
            for backup_file in backup_files:
                parts = backup_file.stem.split(".")
                playlist_name = parts[0] if len(parts) >= 3 else "unknown"

                if playlist_name not in by_playlist:
                    by_playlist[playlist_name] = {
                        "count": 0, "size_bytes": 0,
                        "oldest": None, "newest": None,
                    }

                data = by_playlist[playlist_name]
                data["count"] += 1
                data["size_bytes"] += backup_file.stat().st_size
                mtime = backup_file.stat().st_mtime

                if data["oldest"] is None or mtime < data["oldest"].stat().st_mtime:
                    data["oldest"] = backup_file
                if data["newest"] is None or mtime > data["newest"].stat().st_mtime:
                    data["newest"] = backup_file

            for data in by_playlist.values():
                data["size_mb"] = data["size_bytes"] / (1024 * 1024)
                if data["oldest"]:
                    data["oldest_date"] = datetime.fromtimestamp(
                        data["oldest"].stat().st_mtime).isoformat()
                if data["newest"]:
                    data["newest_date"] = datetime.fromtimestamp(
                        data["newest"].stat().st_mtime).isoformat()

            return {
                "total_count": len(backup_files),
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "oldest_backup": {
                    "path": str(oldest),
                    "date": datetime.fromtimestamp(oldest.stat().st_mtime).isoformat(),
                    "size_mb": oldest.stat().st_size / (1024 * 1024),
                },
                "newest_backup": {
                    "path": str(newest),
                    "date": datetime.fromtimestamp(newest.stat().st_mtime).isoformat(),
                    "size_mb": newest.stat().st_size / (1024 * 1024),
                },
                "by_playlist": by_playlist,
            }

        except Exception as error:
            logger.error("Erreur statistiques backups: %s", error)
            return {"error": str(error)}

    def auto_cleanup_backups_if_needed(
        self,
        threshold_count: int = 100,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Run cleanup automatically if backup count exceeds threshold."""
        try:
            backup_count = len(list(self.data_dir.glob("*.backup.*.json")))
            logger.debug("Backups actuels: %s (seuil: %s)", backup_count, threshold_count)

            if backup_count >= threshold_count or force:
                logger.info("Nettoyage auto backups declenche: %s fichiers", backup_count)
                return self.cleanup(
                    max_backups_per_playlist=3,
                    max_total_backups=50,
                    delete_older_than_days=7,
                )
            return None

        except Exception as error:
            logger.error("Erreur nettoyage auto backups: %s", error)
            return None