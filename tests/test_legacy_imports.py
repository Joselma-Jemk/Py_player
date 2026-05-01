"""Tests for legacy import compatibility — ensure both import paths work."""

import sys
import unittest


class TestLegacyImports(unittest.TestCase):
    """Tests for legacy import compatibility."""

    def test_import_playlist_from_domain(self):
        """Test importing Playlist from src.pyplayer.domain.playlist."""
        from src.pyplayer.domain.playlist import Playlist

        self.assertIsNotNone(Playlist)
        self.assertTrue(hasattr(Playlist, "__init__"))

    def test_import_playlist_state_from_domain(self):
        """Test importing PlaylistState from src.pyplayer.domain.playlist."""
        from src.pyplayer.domain.playlist import PlaylistState

        self.assertIsNotNone(PlaylistState)
        self.assertTrue(callable(PlaylistState))

    def test_import_play_mode_from_domain(self):
        """Test importing PlayMode from src.pyplayer.domain.playlist."""
        from src.pyplayer.domain.playlist import PlayMode

        self.assertIsNotNone(PlayMode)
        self.assertTrue(hasattr(PlayMode, "NORMAL"))

    def test_import_video_from_domain(self):
        """Test importing Video from src.pyplayer.domain.media.video."""
        from src.pyplayer.domain.media.video import Video

        self.assertIsNotNone(Video)
        self.assertTrue(hasattr(Video, "__init__"))

    def test_import_playlist_manager_from_services(self):
        """Test importing PlaylistManager from src.pyplayer.app.services."""
        from src.pyplayer.app.services import PlaylistManager

        self.assertIsNotNone(PlaylistManager)
        self.assertTrue(hasattr(PlaylistManager, "__init__"))


class TestLegacyMainWindowImports(unittest.TestCase):
    """Tests for legacy MainWindow import compatibility."""

    def test_import_main_window_from_pyplayer_ui(self):
        """Test importing MainWindow from src.pyplayer.ui.main_window."""
        from src.pyplayer.ui.main_window import MainWindow

        self.assertIsNotNone(MainWindow)
        self.assertTrue(hasattr(MainWindow, "__init__"))


if __name__ == "__main__":
    unittest.main()