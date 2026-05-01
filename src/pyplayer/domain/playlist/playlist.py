"""Playlist domain model — facade over specialized modules."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.pyplayer.domain.media.media_formats import VIDEO_EXTENSIONS
from src.pyplayer.domain.media.video import Video
from src.pyplayer.domain.playlist.play_mode import PlayMode
from src.pyplayer.domain.playlist.playlist_navigation import PlaylistNavigation
from src.pyplayer.domain.playlist.playlist_serializer import PlaylistSerializer
from src.pyplayer.domain.playlist.playlist_state import PlaylistState
from src.pyplayer.domain.playlist.playlist_file_service import PlaylistFileService
from src.pyplayer.domain.playlist.playlist_validation import PlaylistValidation

logger = logging.getLogger(__name__)


class Playlist:
    """Represente une playlist de videos, chargee depuis un dossier ou vide."""

    def __init__(self, video_path: Optional[Path] = None):
        self.path = video_path
        self.name = video_path.name if video_path else "Playlist sans titre"
        self.unique_id = self._generate_id()
        self.play_mode = PlayMode.NORMAL
        self.videos: List[Video] = []
        self.description = None
        self._save_file_path: Optional[Path] = None
        self.p_state = PlaylistState(
            playlist_id=self.unique_id,
            total_videos=len(self.videos),
            total_duration=self.total_duration,
        )
        self._current_index = -1
        self._shuffle_order: List[int] = []
        self._shuffle_position = -1
        self._shuffle_history: List[int] = []

        if video_path and video_path.exists():
            if video_path.is_dir():
                self._load_videos_from_folder()
            else:
                self.add_video(video_path)

    def _generate_id(self) -> str:
        if not self.path:
            return uuid.uuid4().hex[:8].upper()
        try:
            path_str = str(self.path.absolute())
            hash_obj = hashlib.sha256(path_str.encode("utf-8"))
            return hash_obj.hexdigest()[:8].upper()
        except Exception:
            return uuid.uuid4().hex[:8].upper()

    @property
    def all_video(self) -> List[Video]:
        return self.videos

    @property
    def id(self) -> str:
        return self.unique_id

    @property
    def total(self) -> int:
        return len(self.videos)

    @property
    def total_duration(self) -> int:
        return sum(video.duration for video in self.videos if video.duration > 0)

    @property
    def current_index(self) -> int:
        if not self.videos:
            return -1

        if self.play_mode != PlayMode.SHUFFLE:
            if self._current_index < 0:
                return -1
            return min(self._current_index, len(self.videos) - 1)

        if (
            not self._shuffle_order
            or self._shuffle_position < 0
            or self._shuffle_position >= len(self._shuffle_order)
        ):
            return -1

        try:
            shuffle_index = self._shuffle_order[self._shuffle_position]
            if 0 <= shuffle_index < len(self.videos):
                return shuffle_index
            return -1
        except (IndexError, TypeError):
            return -1

    @current_index.setter
    def current_index(self, value: int) -> None:
        if not self.videos:
            self._current_index = -1
            return

        if value < -1 or value >= len(self.videos):
            raise ValueError(f"Index {value} invalide. Doit etre entre -1 et {len(self.videos) - 1}")

        if self.play_mode != PlayMode.SHUFFLE:
            self._current_index = value
        else:
            if value >= 0:
                try:
                    self._shuffle_position = self._shuffle_order.index(value)
                except ValueError:
                    self._shuffle_position = 0 if self._shuffle_order else -1
            else:
                self._shuffle_position = -1

        self.p_state.update_state(
            index=value,
            video_path=self.videos[value].file_path if value >= 0 else None,
        )
        self._auto_save_if_needed()

    @property
    def current_video(self) -> Optional[Video]:
        current_idx = self.current_index
        if 0 <= current_idx < len(self.videos):
            return self.videos[current_idx]
        return None

    @property
    def current_video_info(self) -> Dict[str, Any]:
        video = self.current_video
        if not video:
            return {
                "has_video": False,
                "index": -1,
                "name": None,
                "path": None,
                "duration": 0,
                "position": 0,
                "progress": 0.0,
            }

        return {
            "has_video": True,
            "index": self.current_index,
            "name": video.name,
            "path": str(video.file_path) if video.file_path else None,
            "duration": video.duration,
            "position": video.state.position if hasattr(video, "state") else 0,
            "progress": video.state.progress if hasattr(video, "state") and video.duration > 0 else 0.0,
            "playing": video.state.playing if hasattr(video, "state") else False,
            "muted": video.state.muted if hasattr(video, "state") else False,
            "volume": video.state.volume if hasattr(video, "state") else 1.0,
            "resolution": f"{video.width}x{video.height}" if video.width > 0 and video.height > 0 else "Inconnue",
        }

    @property
    def save_file_path(self) -> Optional[Path]:
        return self._save_file_path

    @save_file_path.setter
    def save_file_path(self, value: Optional[Path]) -> None:
        self._save_file_path = value
        if value:
            value.parent.mkdir(parents=True, exist_ok=True)

    def update_current_video_state(
        self,
        position: Optional[int] = None,
        duration: Optional[int] = None,
        playing: Optional[bool] = None,
        volume: Optional[float] = None,
        muted: Optional[bool] = None,
    ) -> bool:
        current_video = self.current_video
        if not current_video:
            return False

        current_video.update_state(
            playing=playing,
            position=position,
            duration=duration,
            volume=volume,
            muted=muted,
        )

        if playing is not None:
            self.p_state.is_playing = playing

        self._auto_save_if_needed()
        return True

    def _auto_save_if_needed(self) -> None:
        if self._save_file_path and self._save_file_path.parent.exists():
            try:
                self.save_to_file(self._save_file_path, create_backup=False)
            except Exception as e:
                logger.debug(f"Auto-save echoue: {e}")

    def auto_save(self):
        self._auto_save_if_needed()

    def set_auto_save(self, file_path: Optional[Path]) -> None:
        self.save_file_path = file_path
        if file_path:
            logger.info(f"Sauvegarde automatique activee: {file_path}")
        else:
            logger.info("Sauvegarde automatique desactivee")

    def ensure_active(self) -> bool:
        if not self.videos:
            return False

        if 0 <= self.current_index < len(self.videos):
            return True

        self.current_index = 0
        if self.play_mode == PlayMode.SHUFFLE:
            self._generate_shuffle_order()
            self._shuffle_position = 0 if self._shuffle_order else -1
        return True

    def get_next_video(self) -> Tuple[Optional[Video], int]:
        nav = PlaylistNavigation(
            self.videos, self.play_mode, self._current_index,
            self._shuffle_order, self._shuffle_position, self._shuffle_history,
        )
        video, new_idx = nav.get_next_video()
        if video is None or new_idx < 0 or new_idx >= len(self.videos):
            return None, -1

        self._current_index = new_idx

        if self.play_mode == PlayMode.SHUFFLE:
            self._shuffle_position = nav._shuffle_position

        self.p_state.update_state(
            index=new_idx,
            playing=True,
            video_path=video.file_path if video else None,
            mode=self.play_mode,
        )
        self.p_state.total_videos = self.total
        self.p_state.total_duration = self.total_duration
        self._auto_save_if_needed()
        return video, new_idx

    def get_previous_video(self) -> Tuple[Optional[Video], int]:
        nav = PlaylistNavigation(
            self.videos, self.play_mode, self._current_index,
            self._shuffle_order, self._shuffle_position, self._shuffle_history,
        )
        video, new_idx = nav.get_previous_video()
        if video is None or new_idx < 0 or new_idx >= len(self.videos):
            return None, -1

        self._current_index = new_idx

        if self.play_mode == PlayMode.SHUFFLE:
            self._shuffle_position = nav._shuffle_position

        self.p_state.update_state(index=new_idx, video_path=video.file_path if video else None)
        self._auto_save_if_needed()
        return video, new_idx

    def set_play_mode(self, mode: PlayMode) -> None:
        try:
            if mode == self.play_mode:
                return

            old_mode = self.play_mode
            if old_mode == PlayMode.SHUFFLE:
                current_video_idx = -1
                if self._shuffle_order and 0 <= self._shuffle_position < len(self._shuffle_order):
                    try:
                        current_video_idx = self._shuffle_order[self._shuffle_position]
                    except (IndexError, TypeError):
                        current_video_idx = -1
            else:
                current_video_idx = self._current_index

            self.play_mode = mode
            self.p_state.update_state(mode=mode, index=current_video_idx if current_video_idx >= 0 else -1)

            if mode == PlayMode.SHUFFLE:
                self._generate_shuffle_order()
                if current_video_idx >= 0 and self._shuffle_order:
                    try:
                        self._shuffle_position = self._shuffle_order.index(current_video_idx)
                    except ValueError:
                        self._shuffle_position = 0 if self._shuffle_order else -1
                else:
                    self._shuffle_position = -1
            elif old_mode == PlayMode.SHUFFLE and mode != PlayMode.SHUFFLE:
                self._shuffle_order.clear()
                self._shuffle_history.clear()
                self._shuffle_position = -1
                self._current_index = current_video_idx if current_video_idx >= 0 else -1

            self._auto_save_if_needed()
        except Exception as e:
            logger.error(f"Erreur set_play_mode {self.play_mode} -> {mode}: {e}")
            self.play_mode = PlayMode.NORMAL
            self._current_index = -1
            self._shuffle_order.clear()
            self._shuffle_history.clear()
            self._shuffle_position = -1
            self.p_state.reset_playback()

    def add_video_from_dir_path(self, dir_path: Path) -> List[Video]:
        added_videos = []
        if not dir_path.exists():
            logger.warning(f"Dossier introuvable: {dir_path}")
            return added_videos

        if not dir_path.is_dir():
            logger.warning(f"Le chemin n'est pas un dossier: {dir_path}")
            return added_videos

        try:
            for file_path in dir_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
                    video = self.add_video(file_path)
                    if video:
                        added_videos.append(video)

            logger.info(f"Ajoute {len(added_videos)} videos depuis: {dir_path}")
            return added_videos
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout des videos depuis {dir_path}: {e}")
            return added_videos

    def add_video(self, file_path: Path) -> Optional[Video]:
        try:
            if not file_path.exists() or file_path.is_dir():
                return None

            suffix = file_path.suffix.lower()
            if suffix not in VIDEO_EXTENSIONS:
                return None

            if any(v.file_path == file_path for v in self.videos):
                return None

            video = Video(file_path)
            self.videos.append(video)
            self.p_state.total_videos = self.total
            self.p_state.total_duration = self.total_duration
            self._auto_save_if_needed()
            return video
        except Exception as e:
            logger.error(f"Erreur add_video {file_path}: {e}")
            return None

    def remove_video(self, identifier: Union[Video, Path, int]) -> bool:
        try:
            if isinstance(identifier, int):
                if 0 <= identifier < len(self.videos):
                    if identifier == self._current_index:
                        self._current_index = -1
                        self.p_state.update_state(index=-1, video_path=None)
                    elif identifier < self._current_index:
                        self._current_index -= 1

                    if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                        if identifier in self._shuffle_order:
                            self._shuffle_order.remove(identifier)
                            self._shuffle_order = [
                                idx if idx < identifier else idx - 1 for idx in self._shuffle_order
                            ]
                            if self._shuffle_position >= len(self._shuffle_order):
                                self._shuffle_position = -1

                    del self.videos[identifier]
                    self.p_state.total_videos = self.total
                    self.p_state.total_duration = self.total_duration
                    self._auto_save_if_needed()
                    return True
                return False

            target_path = identifier.file_path if isinstance(identifier, Video) else identifier
            for i, video in enumerate(self.videos):
                if video.file_path == target_path:
                    if i == self._current_index:
                        self._current_index = -1
                    elif i < self._current_index:
                        self._current_index -= 1

                    if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                        if i in self._shuffle_order:
                            self._shuffle_order.remove(i)
                            self._shuffle_order = [idx if idx < i else idx - 1 for idx in self._shuffle_order]
                            if self._shuffle_position >= len(self._shuffle_order):
                                self._shuffle_position = -1

                    del self.videos[i]
                    self._auto_save_if_needed()
                    return True
            return False
        except Exception as e:
            logger.error(f"Erreur remove_video: {e}")
            return False

    def move_video(self, from_index: int, to_index: int) -> bool:
        try:
            if not 0 <= from_index < len(self.videos) or not 0 <= to_index <= len(self.videos):
                return False
            if from_index == to_index:
                return True

            video = self.videos.pop(from_index)
            self.videos.insert(to_index, video)

            if self._current_index == from_index:
                self._current_index = to_index
            elif from_index < self._current_index <= to_index:
                self._current_index -= 1
            elif to_index <= self._current_index < from_index:
                self._current_index += 1

            if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                new_shuffle_order = []
                for idx in self._shuffle_order:
                    if idx == from_index:
                        new_shuffle_order.append(to_index)
                    elif from_index < to_index:
                        if from_index < idx <= to_index:
                            new_shuffle_order.append(idx - 1)
                        else:
                            new_shuffle_order.append(idx)
                    else:
                        if to_index <= idx < from_index:
                            new_shuffle_order.append(idx + 1)
                        else:
                            new_shuffle_order.append(idx)
                self._shuffle_order = new_shuffle_order

            self._auto_save_if_needed()
            return True
        except Exception as e:
            logger.error(f"Erreur move_video {from_index}->{to_index}: {e}")
            return False

    def swap_videos(self, idx1: int, idx2: int) -> bool:
        try:
            if not 0 <= idx1 < len(self.videos) or not 0 <= idx2 < len(self.videos):
                return False
            if idx1 == idx2:
                return True

            self.videos[idx1], self.videos[idx2] = self.videos[idx2], self.videos[idx1]

            if self._current_index == idx1:
                self._current_index = idx2
            elif self._current_index == idx2:
                self._current_index = idx1

            if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                new_shuffle_order = []
                for idx in self._shuffle_order:
                    if idx == idx1:
                        new_shuffle_order.append(idx2)
                    elif idx == idx2:
                        new_shuffle_order.append(idx1)
                    else:
                        new_shuffle_order.append(idx)
                self._shuffle_order = new_shuffle_order

            self._auto_save_if_needed()
            return True
        except Exception as e:
            logger.error(f"Erreur swap_videos {idx1}<->{idx2}: {e}")
            return False

    def update_playlist_state(self) -> None:
        self.p_state.playlist_id = self.unique_id
        self.p_state.play_mode = self.play_mode
        self.p_state.current_index = self.current_index
        self.p_state.total_videos = self.total
        self.p_state.total_duration = self.total_duration

        if 0 <= self.current_index < len(self.videos):
            self.p_state.current_video_path = self.videos[self.current_index].file_path
        else:
            self.p_state.current_video_path = None

    def set_metadata(self, name: Optional[str] = None, description: Optional[str] = None) -> None:
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description

        self._auto_save_if_needed()
        logger.info(f"Metadonnees mises a jour: name={self.name}, description={self.description}")

    def find_video_by_id(self, identifier: Union[int, str, Video, Path]) -> Optional[Video]:
        if not self.videos:
            return None

        if isinstance(identifier, Video):
            return identifier if identifier in self.videos else None

        if isinstance(identifier, int):
            if 0 <= identifier < len(self.videos):
                return self.videos[identifier]
            return None

        if isinstance(identifier, Path):
            for video in self.videos:
                if video.file_path and video.file_path.absolute() == identifier.absolute():
                    return video

            identifier_name = identifier.name
            for video in self.videos:
                if video.file_path and video.file_path.name == identifier_name:
                    return video
            return None

        if isinstance(identifier, str):
            for video in self.videos:
                if video.name == identifier:
                    return video

            identifier_lower = identifier.lower()
            for video in self.videos:
                if identifier_lower in video.name.lower():
                    return video

            for video in self.videos:
                if video.file_path and identifier_lower in str(video.file_path).lower():
                    return video
            return None

        logger.warning(f"Type d'identifiant non supporte: {type(identifier)}")
        return None

    def get_video_index(self, identifier: Union[int, str, Video, Path]) -> int:
        if not self.videos:
            return -1

        if isinstance(identifier, int):
            return identifier if 0 <= identifier < len(self.videos) else -1

        if isinstance(identifier, Video):
            try:
                return self.videos.index(identifier)
            except ValueError:
                return -1

        video = self.find_video_by_id(identifier)
        if video:
            try:
                return self.videos.index(video)
            except ValueError:
                return -1

        return -1

    def get_index_by_name(self, video_name: str, exact_match: bool = True) -> int:
        if not self.videos:
            return -1

        for i, video in enumerate(self.videos):
            current_name = video.name
            if exact_match:
                if current_name == video_name:
                    return i
            else:
                if video_name.lower() in current_name.lower():
                    return i
        return -1

    def jump_to_video_by_name(self, video_name: str, exact_match: bool = True) -> bool:
        idx = self.get_index_by_name(video_name, exact_match)
        if idx >= 0:
            self.current_index = idx
            if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                try:
                    self._shuffle_position = self._shuffle_order.index(idx)
                except ValueError:
                    self._generate_shuffle_order()
                    self._shuffle_position = 0 if self._shuffle_order else -1
            logger.info(f"Saut vers la video : '{video_name}' (index {idx})")
            return True
        logger.warning(f"Video introuvable : '{video_name}'")
        return False

    def find_videos_by_name(self, name: str, case_sensitive: bool = False) -> List[Video]:
        if not self.videos:
            return []

        results = []
        search_name = name if case_sensitive else name.lower()
        for video in self.videos:
            video_name = video.name if case_sensitive else video.name.lower()
            if search_name in video_name:
                results.append(video)
        return results

    def find_videos_by_path(self, path_pattern: str) -> List[Video]:
        if not self.videos:
            return []

        results = []
        pattern_lower = path_pattern.lower()
        for video in self.videos:
            if video.file_path and pattern_lower in str(video.file_path).lower():
                results.append(video)
        return results

    def get_video_info(self, identifier: Union[int, str, Video, Path]) -> Optional[Dict[str, Any]]:
        video = self.find_video_by_id(identifier)
        if not video:
            return None

        try:
            index = self.videos.index(video)
        except ValueError:
            index = -1

        return {
            "index": index,
            "name": video.name,
            "path": str(video.file_path) if video.file_path else None,
            "size": video.size if hasattr(video, "size") else 0,
            "size_mb": video.size / (1024 * 1024) if hasattr(video, "size") and video.size > 0 else 0,
            "duration": video.duration,
            "duration_formatted": f"{video.duration // 60000}:{(video.duration % 60000) // 1000:02d}" if video.duration > 0 else "0:00",
            "width": video.width,
            "height": video.height,
            "resolution": f"{video.width}x{video.height}" if video.width > 0 and video.height > 0 else "Inconnue",
            "aspect_ratio": video.aspect_ratio if hasattr(video, "aspect_ratio") else 0.0,
            "extension": video.extension if hasattr(video, "extension") else "",
            "is_current": index == self.current_index,
            "state": video.state.to_dict() if hasattr(video, "state") else {},
            "file_exists": video.file_path.exists() if video.file_path else False,
        }

    def clear(self, reset_state: bool = True) -> None:
        if not reset_state:
            current_mode = self.play_mode
            was_playing = self.p_state.is_playing if hasattr(self, "p_state") else False
        else:
            current_mode = None
            was_playing = False

        self.videos.clear()
        self._current_index = -1

        if hasattr(self, "_shuffle_order"):
            self._shuffle_order.clear()
            self._shuffle_history.clear()
            self._shuffle_position = -1

        if reset_state:
            self.p_state.reset_playback()
        else:
            self.p_state.update_state(index=-1, video_path=None, playing=was_playing)

        if not reset_state and current_mode:
            self.play_mode = current_mode

        self.p_state.total_videos = 0
        self.p_state.total_duration = 0
        self._auto_save_if_needed()
        logger.info(f"Playlist videe: {self.name}")

    def clear_and_reset(self) -> None:
        self.clear(reset_state=True)

    def clear_videos_only(self) -> None:
        self.clear(reset_state=False)

    def _generate_shuffle_order(self) -> None:
        if not self.videos:
            self._shuffle_order = []
            self._shuffle_position = -1
            self._shuffle_history.clear()
            return

        import random
        indices = list(range(len(self.videos)))
        random.shuffle(indices)
        if self._shuffle_order and indices[0] == self._shuffle_order[-1] and len(indices) > 1:
            swap_pos = random.randint(1, len(indices) - 1)
            indices[0], indices[swap_pos] = indices[swap_pos], indices[0]

        self._shuffle_order = indices
        self._shuffle_position = -1
        self._shuffle_history.clear()

    def _load_videos_from_folder(self) -> None:
        if not self.path or not self.path.exists() or not self.path.is_dir():
            return

        try:
            for file_path in self.path.rglob("*"):
                if file_path.is_file():
                    self.add_video(file_path)
        except Exception as e:
            logger.error(f"Erreur _load_videos_from_folder: {e}")

    def __str__(self) -> str:
        return f"Playlist '{self.name}' ({self.total} videos, mode: {self.play_mode})"

    def __len__(self) -> int:
        return len(self.videos)

    def to_dict(self, include_video_states: bool = True) -> Dict[str, Any]:
        return PlaylistSerializer.to_dict(
            videos=self.videos,
            play_mode=self.play_mode,
            current_index=self._current_index,
            shuffle_order=self._shuffle_order,
            shuffle_position=self._shuffle_position,
            shuffle_history=self._shuffle_history,
            p_state=self.p_state,
            path=self.path,
            name=self.name,
            description=self.description,
            unique_id=self.unique_id,
            include_video_states=include_video_states,
        )

    @classmethod
    def from_dict(cls, data: dict, validate_files: bool = True) -> "Playlist":
        result = PlaylistSerializer.from_dict(data, validate_files=validate_files)

        playlist = cls(video_path=None)
        playlist.path = result["path"]
        playlist.name = result["name"]
        playlist.description = result["description"]
        playlist.unique_id = result["unique_id"] or playlist._generate_id()
        playlist.play_mode = result["play_mode"]
        playlist.videos = result["videos"]
        playlist._current_index = result["current_index"]
        playlist._shuffle_order = result["shuffle_order"]
        playlist._shuffle_position = result["shuffle_position"]
        playlist._shuffle_history = result["shuffle_history"]
        playlist.p_state = result["p_state"]

        errors = result["errors"]
        playlist._load_validation = {
            "missing_files": errors["missing_files"],
            "corrupted_files": errors["corrupted_files"],
            "total_loaded": errors["total_loaded"],
            "load_time": errors["load_time"],
        }

        if validate_files and errors["missing_files"]:
            if 0 <= playlist.current_index < len(playlist.videos):
                current_video = playlist.videos[playlist.current_index]
                if not current_video.file_path.exists():
                    logger.warning("Video courante manquante, reinitialisation index")
                    playlist.current_index = -1
                    playlist.p_state.update_state(index=-1, video_path=None)

        playlist.update_playlist_state()
        if errors["missing_files"]:
            logger.info(f"Playlist chargee avec {len(errors['missing_files'])} fichiers manquants")
        if errors["corrupted_files"]:
            logger.info(f"Playlist chargee avec {len(errors['corrupted_files'])} fichiers corrompus")
        return playlist

    def save_to_file(
        self,
        file_path: Path,
        create_backup: bool = True,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        original_name = self.name
        original_description = self.description

        if name is not None:
            self.name = name
        if description is not None:
            self.description = description

        data = self.to_dict()
        result = PlaylistFileService.save_to_file(file_path, data, create_backup=create_backup)

        if name is not None:
            self.name = original_name
        if description is not None:
            self.description = original_description
        return result

    @classmethod
    def load_from_file(
        cls,
        file_path: Path,
        validate_files: bool = True,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional["Playlist"]:
        data = PlaylistFileService.load_from_file(file_path)
        if data is None:
            backup_data = PlaylistFileService.try_load_from_backup(file_path)
            if backup_data is None:
                return None
            data = backup_data

        playlist = cls.from_dict(data, validate_files=validate_files)
        if name is not None:
            playlist.name = name
        if description is not None:
            playlist.description = description

        playlist._source_file = file_path
        logger.info(f"Playlist chargee: {file_path} ({playlist.total} videos)")
        return playlist

    def get_validation_report(self) -> Dict[str, Any]:
        if hasattr(self, "_load_validation"):
            return PlaylistValidation.get_validation_report(
                self.videos,
                load_validation=self._load_validation,
                name=self.name,
                description=self.description,
            )
        return PlaylistValidation.get_validation_report(
            self.videos, name=self.name, description=self.description
        )

    def remove_missing_files(self) -> List[Dict[str, Any]]:
        report = self.get_validation_report()
        missing_files = report.get("missing_files", [])
        removed = []

        for item in sorted(missing_files, key=lambda x: x["index"], reverse=True):
            idx = item["index"]
            if 0 <= idx < len(self.videos):
                removed_video = self.videos[idx]
                if self.remove_video(idx):
                    removed.append({"index": idx, "name": removed_video.name, "path": str(removed_video.file_path)})
                    logger.info(f"Video supprimee (fichier manquant): {removed_video.name}")

        self.update_playlist_state()
        return removed

    def find_missing_files(self) -> List[Dict[str, Any]]:
        return PlaylistValidation.find_missing_files(
            self.videos,
            source_path=self.path,
            source_file=getattr(self, "_source_file", None),
        )