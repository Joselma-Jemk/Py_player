"""Tests for Playlist, PlaylistState, PlayMode domain models."""

import tempfile
import unittest
from pathlib import Path

from src.pyplayer.domain.playlist import Playlist, PlaylistState, PlayMode


class TestPlayMode(unittest.TestCase):
    """Tests for PlayMode enum."""

    def test_play_mode_values(self):
        """Test all play mode values exist."""
        self.assertEqual(PlayMode.NORMAL.value, "normal")
        self.assertEqual(PlayMode.LOOP_ONE.value, "loop_one")
        self.assertEqual(PlayMode.LOOP_ALL.value, "loop_all")
        self.assertEqual(PlayMode.SHUFFLE.value, "shuffle")

    def test_play_mode_str(self):
        """Test str representation."""
        self.assertEqual(str(PlayMode.NORMAL), "normal")
        self.assertEqual(str(PlayMode.SHUFFLE), "shuffle")

    def test_play_mode_to_dict(self):
        """Test serialization to dict."""
        self.assertEqual(PlayMode.NORMAL.to_dict(), "normal")
        self.assertEqual(PlayMode.LOOP_ALL.to_dict(), "loop_all")

    def test_play_mode_from_dict(self):
        """Test deserialization from dict."""
        self.assertEqual(PlayMode.from_dict("normal"), PlayMode.NORMAL)
        self.assertEqual(PlayMode.from_dict("shuffle"), PlayMode.SHUFFLE)
        self.assertEqual(PlayMode.from_dict("invalid"), PlayMode.NORMAL)
        self.assertEqual(PlayMode.from_dict(None), PlayMode.NORMAL)


class TestPlaylistState(unittest.TestCase):
    """Tests for PlaylistState dataclass."""

    def test_default_values(self):
        """Test default state values."""
        state = PlaylistState()
        self.assertEqual(state.playlist_id, "")
        self.assertEqual(state.play_mode, PlayMode.NORMAL)
        self.assertEqual(state.current_index, -1)
        self.assertIsNone(state.current_video_path)
        self.assertEqual(state.total_videos, 0)
        self.assertEqual(state.total_duration, 0)
        self.assertFalse(state.is_playing)

    def test_has_video_property(self):
        """Test has_video property."""
        state = PlaylistState()
        self.assertFalse(state.has_video)

        state.current_index = 0
        state.current_video_path = Path("/some/video.mp4")
        self.assertTrue(state.has_video)

    def test_is_empty_property(self):
        """Test is_empty property."""
        state = PlaylistState()
        self.assertTrue(state.is_empty)

        state.total_videos = 5
        self.assertFalse(state.is_empty)

    def test_update_state(self):
        """Test update_state method."""
        state = PlaylistState()
        state.update_state(index=2, playing=True, video_path=Path("/video.mp4"))
        self.assertEqual(state.current_index, 2)
        self.assertTrue(state.is_playing)
        self.assertEqual(state.current_video_path, Path("/video.mp4"))

    def test_update_state_mode(self):
        """Test update_state with mode change."""
        state = PlaylistState()
        state.update_state(mode=PlayMode.LOOP_ALL)
        self.assertEqual(state.play_mode, PlayMode.LOOP_ALL)

    def test_update_state_appends_to_history(self):
        """Test that update_state with index appends to play_history."""
        state = PlaylistState()
        state.update_state(index=0)
        self.assertIn(0, state.play_history)
        state.update_state(index=1)
        self.assertIn(1, state.play_history)

    def test_reset_playback(self):
        """Test reset_playback method."""
        state = PlaylistState(current_index=3, is_playing=True)
        state.reset_playback()
        self.assertEqual(state.current_index, -1)
        self.assertIsNone(state.current_video_path)
        self.assertFalse(state.is_playing)

    def test_to_dict(self):
        """Test serialization to dict."""
        state = PlaylistState(
            playlist_id="TEST123",
            play_mode=PlayMode.LOOP_ALL,
            current_index=2,
            total_videos=5,
            is_playing=True,
        )
        data = state.to_dict()
        self.assertEqual(data["playlist_id"], "TEST123")
        self.assertEqual(data["play_mode"], "loop_all")
        self.assertEqual(data["current_index"], 2)
        self.assertTrue(data["is_playing"])

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "playlist_id": "ABCD",
            "play_mode": "shuffle",
            "current_index": 1,
            "current_video_path": "/path/to/video.mp4",
            "total_videos": 10,
            "is_playing": False,
        }
        state = PlaylistState.from_dict(data)
        self.assertEqual(state.playlist_id, "ABCD")
        self.assertEqual(state.play_mode, PlayMode.SHUFFLE)
        self.assertEqual(state.current_index, 1)
        self.assertEqual(state.current_video_path, Path("/path/to/video.mp4"))


class TestPlaylist(unittest.TestCase):
    """Tests for Playlist domain model."""

    def setUp(self):
        """Set up temp directory for file operations."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temp directory."""
        self.temp_dir.cleanup()

    def test_playlist_creation_empty(self):
        """Test creating an empty playlist."""
        playlist = Playlist()
        self.assertEqual(playlist.name, "Playlist sans titre")
        self.assertEqual(len(playlist.videos), 0)
        self.assertIsNotNone(playlist.unique_id)
        self.assertEqual(playlist.play_mode, PlayMode.NORMAL)

    def test_playlist_unique_id(self):
        """Test that each playlist has a unique ID."""
        p1 = Playlist()
        p2 = Playlist()
        self.assertNotEqual(p1.unique_id, p2.unique_id)

    def test_playlist_from_path_invalid(self):
        """Test playlist with non-existent path."""
        playlist = Playlist(Path("/invalid/path/that/does/not/exist.mp4"))
        self.assertEqual(len(playlist.videos), 0)

    def test_playlist_add_video_invalid(self):
        """Test adding invalid file."""
        playlist = Playlist()
        result = playlist.add_video(Path("/invalid/video.mp4"))
        self.assertIsNone(result)

    def test_playlist_add_video_valid(self):
        """Test adding a valid video file."""
        playlist = Playlist()
        video_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        video_file.close()
        try:
            video = playlist.add_video(Path(video_file.name))
            self.assertIsNotNone(video)
            self.assertEqual(len(playlist.videos), 1)
        finally:
            Path(video_file.name).unlink()

    def test_playlist_duplicate_video_rejected(self):
        """Test that duplicate videos are rejected."""
        playlist = Playlist()
        video_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        video_file.close()
        try:
            v1 = playlist.add_video(Path(video_file.name))
            v2 = playlist.add_video(Path(video_file.name))
            self.assertIsNotNone(v1)
            self.assertIsNone(v2)
            self.assertEqual(len(playlist.videos), 1)
        finally:
            Path(video_file.name).unlink()

    def test_to_dict(self):
        """Test playlist serialization to dict."""
        playlist = Playlist()
        playlist.name = "Test Playlist"
        data = playlist.to_dict()
        self.assertIn("name", data)
        self.assertIn("unique_id", data)
        self.assertIn("play_mode", data)
        self.assertIn("videos", data)
        self.assertIn("playlist_state", data)

    def test_from_dict(self):
        """Test playlist deserialization from dict."""
        original = Playlist()
        original.name = "Original Name"
        data = original.to_dict()

        restored = Playlist.from_dict(data, validate_files=False)
        self.assertEqual(restored.name, "Original Name")
        self.assertEqual(restored.unique_id, original.unique_id)

    def test_save_and_load_file(self):
        """Test save_to_file and load_from_file roundtrip."""
        playlist = Playlist()
        playlist.name = "Saved Playlist"
        video_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        video_file.close()
        try:
            playlist.add_video(Path(video_file.name))
            save_path = self.temp_path / "test_playlist.json"

            success = playlist.save_to_file(save_path)
            self.assertTrue(success)
            self.assertTrue(save_path.exists())

            loaded = Playlist.load_from_file(save_path, validate_files=False)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.name, "Saved Playlist")
            self.assertEqual(loaded.total, 1)
        finally:
            Path(video_file.name).unlink()

    def test_navigation_normal_mode(self):
        """Test navigation in NORMAL mode."""
        playlist = Playlist()
        for i in range(3):
            f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            f.close()
            playlist.add_video(Path(f.name))
        playlist.current_index = 0

        next_video, next_idx = playlist.get_next_video()
        self.assertIsNotNone(next_video)
        self.assertEqual(next_idx, 1)

        prev_video, prev_idx = playlist.get_previous_video()
        self.assertIsNotNone(prev_video)
        self.assertEqual(prev_idx, 0)

        for f in playlist.videos:
            Path(f.file_path).unlink()

    def test_navigation_loop_one_mode(self):
        """Test navigation in LOOP_ONE mode."""
        playlist = Playlist()
        for i in range(3):
            f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            f.close()
            playlist.add_video(Path(f.name))
        playlist.current_index = 1
        playlist.set_play_mode(PlayMode.LOOP_ONE)

        next_video, next_idx = playlist.get_next_video()
        self.assertIsNotNone(next_video)
        self.assertEqual(next_idx, 1)

        for f in playlist.videos:
            Path(f.file_path).unlink()

    def test_navigation_loop_all_mode(self):
        """Test navigation in LOOP_ALL mode."""
        playlist = Playlist()
        for i in range(3):
            f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            f.close()
            playlist.add_video(Path(f.name))
        playlist.set_play_mode(PlayMode.LOOP_ALL)
        playlist.current_index = 2

        next_video, next_idx = playlist.get_next_video()
        self.assertIsNotNone(next_video)
        self.assertEqual(next_idx, 0)

        for f in playlist.videos:
            Path(f.file_path).unlink()

    def test_navigation_shuffle_mode(self):
        """Test navigation in SHUFFLE mode — next then previous."""
        playlist = Playlist()
        for i in range(5):
            f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            f.close()
            playlist.add_video(Path(f.name))
        playlist.set_play_mode(PlayMode.SHUFFLE)
        playlist.ensure_active()

        self.assertTrue(len(playlist._shuffle_order) > 0, "Shuffle order should be initialized")
        self.assertTrue(playlist._shuffle_position >= 0, "Shuffle position should be >= 0")

        next1, idx1 = playlist.get_next_video()
        self.assertIsNotNone(next1, "get_next_video should return a video in SHUFFLE mode")

        next2, idx2 = playlist.get_next_video()
        self.assertIsNotNone(next2, "second get_next_video should return a video")

        prev, prev_idx = playlist.get_previous_video()
        self.assertIsNotNone(prev, "get_previous_video should return a video after next calls")
        self.assertEqual(prev, next1, "previous should go back to the first video visited")

        prev2, prev2_idx = playlist.get_previous_video()
        self.assertIsNotNone(prev2, "second get_previous_video should still work")
        # After going back to first visited (next1), second previous should go to the
        # start position — the video playing before any next was called.
        start_video, start_idx = playlist.videos[playlist.current_index], playlist.current_index
        self.assertEqual(prev2, start_video, "second previous should return the start video")

        for f in playlist.videos:
            Path(f.file_path).unlink()

    def test_navigation_shuffle_mode_multiple_previous(self):
        """Test multiple consecutive previous calls in SHUFFLE mode."""
        playlist = Playlist()
        for i in range(6):
            f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            f.close()
            playlist.add_video(Path(f.name))
        playlist.set_play_mode(PlayMode.SHUFFLE)
        playlist.ensure_active()

        visited = [playlist.videos[playlist.current_index]]
        for _ in range(4):
            v, _ = playlist.get_next_video()
            visited.append(v)

        for _ in range(4):
            v, _ = playlist.get_previous_video()
            self.assertIsNotNone(v, "previous should work after forward navigation")

        for f in playlist.videos:
            Path(f.file_path).unlink()

    def test_navigation_shuffle_no_history(self):
        """Test get_previous_video when shuffle has no history yet.

        At shuffle start with no history, previous returns None (nothing to go back to).
        After at least one next, previous should work.
        """
        playlist = Playlist()
        for i in range(3):
            f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            f.close()
            playlist.add_video(Path(f.name))
        playlist.set_play_mode(PlayMode.SHUFFLE)
        playlist.ensure_active()

        prev, idx = playlist.get_previous_video()
        self.assertIsNone(prev, "previous should return None at shuffle start with no history")

        playlist.get_next_video()
        prev, idx = playlist.get_previous_video()
        self.assertIsNotNone(prev, "previous should work after at least one next")

        for f in playlist.videos:
            Path(f.file_path).unlink()

    def test_set_play_mode(self):
        """Test set_play_mode method."""
        playlist = Playlist()
        self.assertEqual(playlist.play_mode, PlayMode.NORMAL)

        playlist.set_play_mode(PlayMode.SHUFFLE)
        self.assertEqual(playlist.play_mode, PlayMode.SHUFFLE)

        playlist.set_play_mode(PlayMode.LOOP_ALL)
        self.assertEqual(playlist.play_mode, PlayMode.LOOP_ALL)

    def test_set_play_mode_same_mode(self):
        """Test set_play_mode with same mode is no-op."""
        playlist = Playlist()
        original_id = playlist.unique_id
        playlist.set_play_mode(PlayMode.NORMAL)
        self.assertEqual(playlist.unique_id, original_id)

    def test_get_validation_report(self):
        """Test get_validation_report method."""
        playlist = Playlist()
        playlist.name = "Test"
        report = playlist.get_validation_report()
        self.assertIn("missing_files", report)
        self.assertIn("total_videos", report)
        self.assertEqual(report["total_videos"], 0)

    def test_remove_missing_files(self):
        """Test remove_missing_files method."""
        playlist = Playlist()
        playlist.name = "Test"
        video_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        video_file.close()
        temp_path = Path(video_file.name)
        playlist.add_video(temp_path)

        temp_path.unlink()

        report = playlist.get_validation_report()
        self.assertGreater(len(report["missing_files"]), 0)

        removed = playlist.remove_missing_files()
        self.assertEqual(len(removed), 1)
        self.assertEqual(len(playlist.videos), 0)

    def test_clear(self):
        """Test clear method with reset."""
        playlist = Playlist()
        f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        f.close()
        playlist.add_video(Path(f.name))
        playlist.current_index = 0

        playlist.clear(reset_state=True)
        self.assertEqual(len(playlist.videos), 0)
        self.assertEqual(playlist.current_index, -1)
        Path(f.name).unlink()

    def test_clear_and_reset(self):
        """Test clear_and_reset method."""
        playlist = Playlist()
        f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        f.close()
        playlist.add_video(Path(f.name))
        playlist.current_index = 0

        playlist.clear_and_reset()
        self.assertEqual(len(playlist.videos), 0)
        self.assertEqual(playlist.current_index, -1)
        Path(f.name).unlink()

    def test_clear_videos_only(self):
        """Test clear_videos_only method."""
        playlist = Playlist()
        f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        f.close()
        playlist.add_video(Path(f.name))
        playlist.current_index = 0

        playlist.clear_videos_only()
        self.assertEqual(len(playlist.videos), 0)
        self.assertEqual(playlist.current_index, -1)
        Path(f.name).unlink()

    def test_remove_video_by_index(self):
        """Test remove_video by int index."""
        playlist = Playlist()
        files = []
        for i in range(3):
            f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            f.close()
            files.append(Path(f.name))
            playlist.add_video(files[-1])

        result = playlist.remove_video(1)
        self.assertTrue(result)
        self.assertEqual(len(playlist.videos), 2)

        for fp in files:
            if fp.exists():
                fp.unlink()

    def test_remove_video_by_path(self):
        """Test remove_video by Path."""
        playlist = Playlist()
        f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        f.close()
        video_path = Path(f.name)
        playlist.add_video(video_path)

        result = playlist.remove_video(video_path)
        self.assertTrue(result)
        self.assertEqual(len(playlist.videos), 0)
        if video_path.exists():
            video_path.unlink()

    def test_total_duration(self):
        """Test total_duration property."""
        playlist = Playlist()
        self.assertEqual(playlist.total_duration, 0)

        f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        f.close()
        video = playlist.add_video(Path(f.name))
        if video:
            video.state._duration = 60000

        self.assertEqual(playlist.total_duration, 60000)
        if Path(f.name).exists():
            Path(f.name).unlink()

    def test_playlist_str_repr(self):
        """Test __str__ method."""
        playlist = Playlist()
        playlist.name = "My Playlist"
        result = str(playlist)
        self.assertIn("My Playlist", result)
        self.assertIn("videos", result)


if __name__ == "__main__":
    unittest.main()