"""Playlist validation — missing file detection and removal."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.pyplayer.domain.media.video import Video


class PlaylistValidation:
    """Handles playlist validation — missing file detection and removal."""

    @staticmethod
    def get_validation_report(
        videos: List[Video],
        load_validation: Dict[str, Any] = None,
        name: str = "",
        description: str = None,
    ) -> Dict[str, Any]:
        """Generate validation report for a playlist."""
        if load_validation is not None:
            return load_validation.copy()

        missing_files: List[Dict[str, Any]] = []
        valid_files: List[Dict[str, Any]] = []

        for i, video in enumerate(videos):
            if video.file_path and video.file_path.exists():
                valid_files.append({"index": i, "path": str(video.file_path), "name": video.name})
            else:
                missing_files.append(
                    {"index": i, "path": str(video.file_path) if video.file_path else "None", "name": video.name}
                )

        return {
            "missing_files": missing_files,
            "valid_files": valid_files,
            "total_videos": len(videos),
            "valid_count": len(valid_files),
            "missing_count": len(missing_files),
            "check_time": datetime.now().isoformat(),
            "name": name,
            "description": description,
        }

    @staticmethod
    def find_missing_files(
        videos: List[Video],
        source_path: Path = None,
        source_file: Path = None,
    ) -> List[Dict[str, Any]]:
        """Try to find locations for missing files."""
        found_files: List[Dict[str, Any]] = []

        report = PlaylistValidation.get_validation_report(videos)
        missing_files = report.get("missing_files", [])

        for item in missing_files:
            original_path = Path(item["path"])
            search_locations = [
                source_path / original_path.name if source_path else None,
                source_path.parent / original_path.name if source_path and source_path.parent else None,
                source_file.parent / original_path.name if source_file else None,
                Path.home() / "Downloads" / original_path.name,
                Path.home() / "Desktop" / original_path.name,
            ]

            for location in search_locations:
                if location and location.exists() and location.is_file():
                    found_files.append({
                        "original": item,
                        "found_at": str(location),
                        "location": str(location)
                    })
                    break

        return found_files