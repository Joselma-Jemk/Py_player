"""Tests for atomic save behavior — original file preserved when json.dump fails."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pyplayer.domain.playlist import Playlist
from src.pyplayer.app.services.playlist_manager import PlaylistManager
from src.pyplayer.infrastructure.persistence.manager_config_store import ManagerConfigStore
from src.pyplayer.infrastructure.persistence.last_played_store import LastPlayedStore


class AtomicSaveTests(unittest.TestCase):
    """Verify that save failures leave the original file untouched."""

    def setUp(self) -> None:
        self.temp_dir_obj = tempfile.TemporaryDirectory(prefix="pyplayer_atomic_")
        self.temp_dir = Path(self.temp_dir_obj.name)

    def tearDown(self) -> None:
        self.temp_dir_obj.cleanup()

    def _failing_dump(self, data: object, stream: object, **kwargs: object) -> None:
        stream.write('{"corrupted":')
        raise RuntimeError("forced dump failure")

    def test_playlist_save_to_file_preserves_original_on_dump_failure(self) -> None:
        """Playlist.save_to_file must not corrupt the target when json.dump fails."""
        playlist = Playlist()
        video_file = self.temp_dir / "sample.mp4"
        video_file.touch()
        self.assertTrue(playlist.add_video(video_file))

        target = self.temp_dir / "playlist.json"
        baseline = '{"stable": true}\n'
        target.write_text(baseline, encoding="utf-8")

        with patch(
            "src.pyplayer.infrastructure.persistence.io_utils.json.dump",
            side_effect=self._failing_dump,
        ):
            result = playlist.save_to_file(target, create_backup=False)

        self.assertFalse(result)
        self.assertEqual(target.read_text(encoding="utf-8"), baseline)

    def test_manager_save_config_preserves_original_on_dump_failure(self) -> None:
        """PlaylistManager._save_config must not corrupt manager_config.json."""
        manager = PlaylistManager(data_dir=self.temp_dir)
        manager.volume = 0.33

        config_path = self.temp_dir / "manager_config.json"
        baseline = config_path.read_text(encoding="utf-8")

        with patch(
            "src.pyplayer.infrastructure.persistence.io_utils.json.dump",
            side_effect=self._failing_dump,
        ):
            manager._save_config()

        self.assertEqual(config_path.read_text(encoding="utf-8"), baseline)

    def test_last_played_store_preserves_original_on_dump_failure(self) -> None:
        """LastPlayedStore.save must not corrupt last_played.json."""
        last_played_path = self.temp_dir / "last_played.json"
        baseline = '{"playlist_id": "old_id"}\n'
        last_played_path.write_text(baseline, encoding="utf-8")

        store = LastPlayedStore(last_played_path)

        with patch(
            "src.pyplayer.infrastructure.persistence.io_utils.json.dump",
            side_effect=self._failing_dump,
        ):
            store.save("new_id")

        self.assertEqual(last_played_path.read_text(encoding="utf-8"), baseline)