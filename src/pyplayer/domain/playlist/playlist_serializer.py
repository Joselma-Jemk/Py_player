"""Playlist serialization logic — to_dict/from_dict transformation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.pyplayer.domain.media.video import Video
from src.pyplayer.domain.playlist.play_mode import PlayMode
from src.pyplayer.domain.playlist.playlist_state import PlaylistState


class PlaylistSerializer:
    """Handles playlist serialization to/from dict."""

    @staticmethod
    def to_dict(
        videos: List[Video],
        play_mode: PlayMode,
        current_index: int,
        shuffle_order: List[int],
        shuffle_position: int,
        shuffle_history: List[int],
        p_state: PlaylistState,
        path: Optional[Path],
        name: str,
        description: Optional[str],
        unique_id: str,
        include_video_states: bool = True,
    ) -> Dict[str, Any]:
        """Serialize playlist to dict."""
        videos_data = []
        valid_video_count = 0
        missing_video_count = 0

        for video in videos:
            file_exists = video.file_path.exists() if video.file_path else False
            video_dict = video.to_dict()
            video_dict["file_exists"] = file_exists
            if not include_video_states:
                video_dict.pop("state", None)
            videos_data.append(video_dict)

            if file_exists:
                valid_video_count += 1
            else:
                missing_video_count += 1

        shuffle_state = None
        if play_mode == PlayMode.SHUFFLE:
            shuffle_state = {
                "shuffle_order": shuffle_order.copy() if shuffle_order else [],
                "shuffle_position": shuffle_position,
                "shuffle_history": shuffle_history.copy() if shuffle_history else [],
            }

        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "file_validation": {
                "total_videos": len(videos),
                "valid_videos": valid_video_count,
                "missing_videos": missing_video_count,
                "validation_date": datetime.now().isoformat(),
            },
            "path": str(path) if path else None,
            "name": name,
            "description": description,
            "unique_id": unique_id,
            "play_mode": play_mode.value,
            "videos": videos_data,
            "current_index": current_index,
            "shuffle_state": shuffle_state,
            "playlist_state": p_state.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict, validate_files: bool = True) -> Dict[str, Any]:
        """
        Deserialize playlist from dict.
        Returns a dict with keys: path, name, description, unique_id, play_mode, videos,
        current_index, shuffle_order, shuffle_position, shuffle_history, p_state, errors.
        """
        if not isinstance(data, dict):
            raise ValueError("Les donnees doivent etre un dictionnaire")

        version = data.get("version", "1.0")
        if version not in ["1.0"]:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Version {version} non supportee, tentative de chargement")

        path_data = data.get("path")
        path = Path(path_data) if path_data else None

        name = data.get("name", "Playlist restauree")
        description = data.get("description", None)
        unique_id = data.get("unique_id", "")
        play_mode_str = data.get("play_mode", "normal")
        play_mode = PlayMode.from_dict(play_mode_str)

        videos: List[Video] = []
        missing_files: List[Dict[str, Any]] = []
        corrupted_files: List[Dict[str, Any]] = []

        for i, video_data in enumerate(data.get("videos", [])):
            try:
                video = Video.from_dict(video_data)
                if validate_files and video.file_path:
                    if not video.file_path.exists():
                        missing_files.append({"index": i, "path": str(video.file_path), "name": video.name})
                    elif video.file_path.is_dir():
                        corrupted_files.append(
                            {"index": i, "path": str(video.file_path), "reason": "Est un dossier, pas un fichier"}
                        )
                videos.append(video)
            except Exception as e:
                corrupted_files.append(
                    {"index": i, "path": video_data.get("file_path", "inconnu"), "reason": str(e)}
                )
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erreur chargement video {i}: {e}")

        current_index = data.get("current_index", -1)
        shuffle_state = data.get("shuffle_state")
        shuffle_order = []
        shuffle_position = -1
        shuffle_history: List[int] = []

        if shuffle_state and play_mode == PlayMode.SHUFFLE:
            shuffle_order = shuffle_state.get("shuffle_order", [])
            shuffle_position = shuffle_state.get("shuffle_position", -1)
            shuffle_history = shuffle_state.get("shuffle_history", [])

        p_state: PlaylistState = PlaylistState()
        playlist_state_data = data.get("playlist_state")
        if playlist_state_data:
            p_state = PlaylistState.from_dict(playlist_state_data)

        errors = {
            "missing_files": missing_files,
            "corrupted_files": corrupted_files,
            "total_loaded": len(videos),
            "load_time": datetime.now().isoformat(),
        }

        return {
            "path": path,
            "name": name,
            "description": description,
            "unique_id": unique_id,
            "play_mode": play_mode,
            "videos": videos,
            "current_index": current_index,
            "shuffle_order": shuffle_order,
            "shuffle_position": shuffle_position,
            "shuffle_history": shuffle_history,
            "p_state": p_state,
            "errors": errors,
        }