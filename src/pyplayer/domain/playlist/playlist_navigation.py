"""Playlist navigation logic — next/previous/video order management."""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from src.pyplayer.domain.media.video import Video
from src.pyplayer.domain.playlist.play_mode import PlayMode


class PlaylistNavigation:
    """Handles playlist navigation logic (next, previous, shuffle, loop)."""

    def __init__(self, videos: List[Video], play_mode: PlayMode,
                 current_index: int, shuffle_order: List[int],
                 shuffle_position: int, shuffle_history: List[int]):
        self._videos = videos
        self._play_mode = play_mode
        self._current_index = current_index
        self._shuffle_order = shuffle_order
        self._shuffle_position = shuffle_position
        self._shuffle_history = shuffle_history

    def get_next_video(self) -> Tuple[Optional[Video], int]:
        """Get next video based on play mode."""
        if not self._videos:
            return None, -1

        current_idx = self._current_index
        if self._play_mode == PlayMode.NORMAL:
            video, new_idx = self._next_normal(current_idx)
        elif self._play_mode == PlayMode.LOOP_ONE:
            video, new_idx = self._next_loop_one(current_idx)
        elif self._play_mode == PlayMode.LOOP_ALL:
            video, new_idx = self._next_loop_all(current_idx)
        elif self._play_mode == PlayMode.SHUFFLE:
            video, new_idx = self._next_shuffle(current_idx)
        else:
            return None, -1

        if video is None or new_idx < 0 or new_idx >= len(self._videos):
            return None, -1

        return video, new_idx

    def get_previous_video(self) -> Tuple[Optional[Video], int]:
        """Get previous video based on play mode."""
        if not self._videos:
            return None, -1

        current_idx = self._current_index
        if self._play_mode == PlayMode.NORMAL:
            video, new_idx = self._previous_normal(current_idx)
        elif self._play_mode == PlayMode.LOOP_ONE:
            video, new_idx = self._previous_loop_one(current_idx)
        elif self._play_mode == PlayMode.LOOP_ALL:
            video, new_idx = self._previous_loop_all(current_idx)
        elif self._play_mode == PlayMode.SHUFFLE:
            video, new_idx = self._previous_shuffle()
        else:
            return None, -1

        if video is None or new_idx < 0 or new_idx >= len(self._videos):
            return None, -1

        return video, new_idx

    def _next_normal(self, current_index: int) -> Tuple[Optional[Video], int]:
        next_index = current_index + 1
        if next_index >= len(self._videos):
            return None, -1
        return self._videos[next_index], next_index

    def _next_loop_one(self, current_index: int) -> Tuple[Optional[Video], int]:
        if current_index < 0 or current_index >= len(self._videos):
            return self._videos[0], 0 if self._videos else -1
        return self._videos[current_index], current_index

    def _next_loop_all(self, current_index: int) -> Tuple[Optional[Video], int]:
        if not self._videos:
            return None, -1

        next_index = current_index + 1
        if next_index >= len(self._videos):
            next_index = 0
        return self._videos[next_index], next_index

    def _next_shuffle(self, current_index: int) -> Tuple[Optional[Video], int]:
        if not self._videos:
            return None, -1

        if not self._shuffle_order:
            self._generate_shuffle_order()
            if not self._shuffle_order:
                return None, -1

        self._shuffle_position += 1
        if self._shuffle_position >= len(self._shuffle_order):
            self._generate_shuffle_order()
            self._shuffle_position = 0

        try:
            shuffle_index = self._shuffle_order[self._shuffle_position]
            if not 0 <= shuffle_index < len(self._videos):
                return None, -1
        except (IndexError, TypeError):
            return None, -1

        if current_index >= 0:
            self._shuffle_history.append(current_index)
            if len(self._shuffle_history) > 50:
                self._shuffle_history.pop(0)

        return self._videos[shuffle_index], shuffle_index

    def _previous_normal(self, current_index: int) -> Tuple[Optional[Video], int]:
        if current_index <= 0:
            return None, -1
        prev_index = current_index - 1
        return self._videos[prev_index], prev_index

    def _previous_loop_one(self, current_index: int) -> Tuple[Optional[Video], int]:
        if current_index < 0 or current_index >= len(self._videos):
            return self._videos[0], 0 if self._videos else -1
        return self._videos[current_index], current_index

    def _previous_loop_all(self, current_index: int) -> Tuple[Optional[Video], int]:
        if not self._videos:
            return None, -1

        if current_index <= 0:
            prev_index = len(self._videos) - 1
        else:
            prev_index = current_index - 1
        return self._videos[prev_index], prev_index

    def _previous_shuffle(self) -> Tuple[Optional[Video], int]:
        if not self._videos:
            return None, -1

        if self._shuffle_history:
            try:
                prev_index = self._shuffle_history.pop()
                if 0 <= prev_index < len(self._videos):
                    self._shuffle_position -= 1
                    return self._videos[prev_index], prev_index
            except (IndexError, ValueError):
                pass

        if self._shuffle_order and self._shuffle_position > 0:
            self._shuffle_position -= 1
            try:
                shuffle_index = self._shuffle_order[self._shuffle_position]
                if 0 <= shuffle_index < len(self._videos):
                    return self._videos[shuffle_index], shuffle_index
            except (IndexError, TypeError):
                pass

        return None, -1

    def _generate_shuffle_order(self) -> None:
        """Generate random shuffle order, storing result in internal state."""
        if not self._videos:
            self._shuffle_order.clear()
            self._shuffle_position = -1
            self._shuffle_history.clear()
            return

        indices = list(range(len(self._videos)))
        random.shuffle(indices)
        if self._shuffle_order and indices[0] == self._shuffle_order[-1] and len(indices) > 1:
            swap_pos = random.randint(1, len(indices) - 1)
            indices[0], indices[swap_pos] = indices[swap_pos], indices[0]

        self._shuffle_order[:] = indices
        self._shuffle_position = -1
        self._shuffle_history.clear()