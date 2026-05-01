"""Playlist registry — pure in-memory playlist store."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator, List, Optional

from src.pyplayer.domain.playlist import Playlist

logger = __import__("logging").getLogger(__name__)


class PlaylistRegistry:
    """In-memory registry of Playlist instances."""

    def __init__(self) -> None:
        self._playlists: Dict[str, Playlist] = {}

    # --- read access ---
    def get(self, playlist_id: str) -> Optional[Playlist]:
        return self._playlists.get(playlist_id)

    def find_by_name(self, name: str) -> Optional[Playlist]:
        name_lower = name.lower()
        for playlist in self._playlists.values():
            if name_lower in playlist.name.lower():
                return playlist
        return None

    def find_all_by_name(self, name: str) -> List[str]:
        name_lower = name.lower()
        return [
            pid for pid, p in self._playlists.items()
            if name_lower in p.name.lower()
        ]

    def all_ids(self) -> List[str]:
        return list(self._playlists.keys())

    def all_items(self) -> Dict[str, Playlist]:
        return self._playlists

    def names_map(self) -> Dict[str, str]:
        return {pid: p.name for pid, p in self._playlists.items()}

    def __len__(self) -> int:
        return len(self._playlists)

    def __contains__(self, playlist_id: str) -> bool:
        return playlist_id in self._playlists

    def __getitem__(self, playlist_id: str) -> Playlist:
        if playlist_id not in self._playlists:
            raise KeyError(f"Playlist non trouvee: {playlist_id}")
        return self._playlists[playlist_id]

    def __iter__(self) -> Iterator[Playlist]:
        return iter(self._playlists.values())

    # --- write access ---
    def add(self, playlist: Playlist) -> None:
        self._playlists[playlist.id] = playlist

    def remove(self, playlist_id: str) -> Optional[Playlist]:
        return self._playlists.pop(playlist_id, None)

    def clear(self) -> None:
        self._playlists.clear()

    def iterate_items(self) -> Iterator[tuple[str, Playlist]]:
        return iter(self._playlists.items())