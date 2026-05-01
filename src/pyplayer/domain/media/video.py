"""Video domain model."""

from pathlib import Path
from typing import Any, Dict, Optional


class VideoState:
    """Playback state for a video."""

    def __init__(self):
        self.playing = False
        self.position = 0
        self._duration = 0
        self.volume = 1.0
        self.muted = False

    @property
    def duration(self) -> int:
        """Return duration in milliseconds."""
        return self._duration

    @duration.setter
    def duration(self, value: int) -> None:
        """Set duration in milliseconds."""
        self._duration = max(0, value)

    @property
    def progress(self) -> float:
        """Return playback progress as a ratio between 0.0 and 1.0."""
        if self._duration > 0:
            return self.position / self._duration
        return 0.0

    def update_state(
        self,
        playing: Optional[bool] = None,
        position: Optional[int] = None,
        duration: Optional[int] = None,
        volume: Optional[float] = None,
        muted: Optional[bool] = None,
    ) -> None:
        """Update playback state with validated values."""
        if duration is not None:
            self.duration = duration

        if playing is not None:
            self.playing = playing

        if position is not None:
            max_pos = self._duration if self._duration > 0 else position
            self.position = max(0, min(position, max_pos))

        if volume is not None:
            self.volume = max(0.0, min(1.0, volume))

        if muted is not None:
            self.muted = muted

    def reset_state(self) -> None:
        """Reset playback state while keeping the known duration."""
        self.playing = False
        self.position = 0
        self.volume = 1.0
        self.muted = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state into a JSON-ready dictionary."""
        return {
            "playing": self.playing,
            "position": self.position,
            "duration": self._duration,
            "volume": self.volume,
            "muted": self.muted,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoState":
        """Build a state object from serialized data."""
        state = cls()
        state.playing = data.get("playing", False)
        state.position = data.get("position", 0)
        state.duration = data.get("duration", 0)
        state.volume = data.get("volume", 1.0)
        state.muted = data.get("muted", False)
        return state

    def __str__(self) -> str:
        status = "▶️" if self.playing else "⏸️"
        return f"{status} {self.position}/{self._duration}ms"


class Video:
    """Represents a local video file and its metadata."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.name = file_path.name
        self.parent_path = file_path.parent
        self.extension = file_path.suffix.lower()

        self.state = VideoState()

        self.size = self._get_file_size()
        self.width = 0
        self.height = 0

    def _get_file_size(self) -> int:
        try:
            return self.file_path.stat().st_size
        except Exception:
            return 0

    @property
    def progress(self):
        return self.get_progress_bar(self.state.progress)

    @property
    def resolution(self) -> str:
        """Return formatted resolution."""
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return "Inconnue"

    @property
    def duration(self) -> int:
        """Return duration from the playback state."""
        return self.state.duration

    @duration.setter
    def duration(self, value: int) -> None:
        self.state.duration = value

    @property
    def aspect_ratio(self) -> float:
        """Compute the aspect ratio."""
        if self.width > 0 and self.height > 0:
            return round(self.width / self.height, 2)
        return 0.0

    @property
    def is_played(self):
        return self.state.progress > 0.9 and self.state.playing

    def update_metadata(self, width: int = 0, height: int = 0, duration: int = 0) -> None:
        """Update video metadata."""
        if width > 0:
            self.width = width
        if height > 0:
            self.height = height
        if duration > 0:
            self.duration = duration

    def update_state(
        self,
        playing: Optional[bool] = None,
        position: Optional[int] = None,
        duration: Optional[int] = None,
        volume: Optional[float] = None,
        muted: Optional[bool] = None,
    ) -> bool:
        """Update the playback state for the video."""
        self.state.update_state(
            playing=playing,
            position=position,
            duration=duration,
            volume=volume,
            muted=muted,
        )
        return True

    def get_progress_bar(self, progress: float) -> str:
        """Return a simple unicode progress bar."""
        progress = max(0.0, min(1.0, progress))
        full_blocks = round(progress * 10)

        full = "▰"
        empty = "▱"

        bar = full * full_blocks + empty * (10 - full_blocks)
        return f"{bar}"

    def reset_state(self) -> bool:
        """Reset playback state to zero while keeping duration."""
        current_duration = self.state.duration
        self.state.reset_state()
        self.state.duration = current_duration
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the video into a JSON-ready dictionary."""
        return {
            "file_path": str(self.file_path),
            "name": self.name,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "extension": self.extension,
            "state": self.state.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Video":
        """Build a video from serialized data."""
        video = cls(Path(data["file_path"]))
        video.size = data.get("size", 0)
        video.width = data.get("width", 0)
        video.height = data.get("height", 0)

        duration = data.get("duration", 0)
        state_data = data.get("state")
        if isinstance(state_data, dict):
            video.state = VideoState.from_dict(state_data)
            if duration > 0:
                video.duration = duration
        elif duration > 0:
            video.duration = duration

        return video

    def __str__(self) -> str:
        """Readable representation including playback state."""
        size_mb = self.size / (1024 * 1024) if self.size > 0 else 0
        status = "▶️ Lecture" if self.state.playing else "⏸️ Pause" if self.state.position > 0 else "⏹️ Arrêt"
        progress_pct = f"{self.state.progress:.1%}" if self.state.duration > 0 else "0%"
        position_str = f"{self.state.position / 1000:.1f}s" if self.state.position > 0 else "0s"
        duration_str = f"{self.state.duration / 1000:.1f}s" if self.state.duration > 0 else "N/A"
        return f"{self.name} | {size_mb:.1f}MB | {status} | {position_str}/{duration_str} ({progress_pct})"
