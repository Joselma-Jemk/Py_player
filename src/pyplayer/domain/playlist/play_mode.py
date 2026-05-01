"""PlayMode enum for playlist playback modes."""

from __future__ import annotations

from enum import Enum


class PlayMode(Enum):
    """Modes de lecture."""

    NORMAL = "normal"
    LOOP_ONE = "loop_one"
    LOOP_ALL = "loop_all"
    SHUFFLE = "shuffle"

    def __str__(self) -> str:
        return self.value

    def to_dict(self) -> str:
        """Serialisation en chaine de caracteres."""
        return self.value

    @classmethod
    def from_dict(cls, data: str) -> "PlayMode":
        """Deserialisation depuis une chaine."""
        try:
            return cls(data)
        except ValueError:
            return cls.NORMAL