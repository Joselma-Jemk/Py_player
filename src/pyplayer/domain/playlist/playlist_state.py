"""PlaylistState dataclass for capturing playlist playback state."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.pyplayer.domain.playlist.play_mode import PlayMode


@dataclass
class PlaylistState:
    """
    Capture l'etat courant d'une playlist.
    Simple, epure et auto-descriptif.
    """

    playlist_id: str = ""
    play_mode: PlayMode = PlayMode.NORMAL
    current_index: int = -1
    current_video_path: Optional[Path] = None
    total_videos: int = 0
    total_duration: int = 0
    is_playing: bool = False
    play_history: List[int] = field(default_factory=list)

    @property
    def has_video(self) -> bool:
        """Indique si une video est actuellement active."""
        return self.current_index >= 0 and self.current_video_path is not None

    @property
    def is_empty(self) -> bool:
        """Indique si la playlist contient zero video."""
        return self.total_videos == 0

    @property
    def last_played_index(self) -> int:
        """Retourne l'index de la derniere video jouee."""
        return self.play_history[-1] if self.play_history else -1

    def update_state(
        self,
        index: Optional[int] = None,
        playing: Optional[bool] = None,
        video_path: Optional[Path] = None,
        mode: Optional[PlayMode] = None,
    ) -> None:
        """
        Met a jour l'etat actuel.

        Args:
            index: Nouvel index courant
            playing: Nouvel etat de lecture
            video_path: Nouveau chemin de video
            mode: Nouveau mode de lecture
        """
        if index is not None:
            self.current_index = index
            if index >= 0 and index not in self.play_history:
                self.play_history.append(index)

        if playing is not None:
            self.is_playing = playing

        if video_path is not None:
            self.current_video_path = video_path

        if mode is not None:
            self.play_mode = mode

    def reset_playback(self) -> None:
        """Reinitialise l'etat de lecture."""
        self.current_index = -1
        self.current_video_path = None
        self.is_playing = False

    def __str__(self) -> str:
        if self.is_empty:
            return "Playlist vide"

        status = "▶️" if self.is_playing else "⏸️"
        video_name = self.current_video_path.name if self.current_video_path else "Aucune"
        return f"{status} {video_name} ({self.current_index + 1}/{self.total_videos}) [{self.play_mode}]"

    def to_dict(self) -> dict:
        return {
            "playlist_id": self.playlist_id,
            "play_mode": self.play_mode.value if self.play_mode else None,
            "current_index": self.current_index,
            "current_video_path": str(self.current_video_path) if self.current_video_path else None,
            "total_videos": self.total_videos,
            "total_duration": self.total_duration,
            "is_playing": self.is_playing,
            "play_history": self.play_history.copy() if self.play_history else [],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlaylistState":
        video_path = Path(data["current_video_path"]) if data.get("current_video_path") else None
        play_mode = None
        if data.get("play_mode"):
            play_mode = PlayMode.from_dict(data["play_mode"])

        return cls(
            playlist_id=data.get("playlist_id", ""),
            play_mode=play_mode if play_mode else PlayMode.NORMAL,
            current_index=data.get("current_index", -1),
            current_video_path=video_path,
            total_videos=data.get("total_videos", 0),
            total_duration=data.get("total_duration", 0),
            is_playing=data.get("is_playing", False),
            play_history=data.get("play_history", []),
        )