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

    def test_import_playlist_from_api(self):
        """Test importing Playlist from src.main.python.api.playlist."""
        from src.main.python.api.playlist import Playlist

        self.assertIsNotNone(Playlist)
        self.assertTrue(hasattr(Playlist, "__init__"))

    def test_import_playlist_state_from_domain(self):
        """Test importing PlaylistState from src.pyplayer.domain.playlist."""
        from src.pyplayer.domain.playlist import PlaylistState

        self.assertIsNotNone(PlaylistState)
        self.assertTrue(callable(PlaylistState))

    def test_import_playlist_state_from_api(self):
        """Test importing PlaylistState from src.main.python.api.playlist."""
        from src.main.python.api.playlist import PlaylistState

        self.assertIsNotNone(PlaylistState)
        self.assertTrue(callable(PlaylistState))

    def test_import_play_mode_from_domain(self):
        """Test importing PlayMode from src.pyplayer.domain.playlist."""
        from src.pyplayer.domain.playlist import PlayMode

        self.assertIsNotNone(PlayMode)
        self.assertTrue(hasattr(PlayMode, "NORMAL"))

    def test_import_play_mode_from_api(self):
        """Test importing PlayMode from src.main.python.api.playlist."""
        from src.main.python.api.playlist import PlayMode

        self.assertIsNotNone(PlayMode)
        self.assertTrue(hasattr(PlayMode, "NORMAL"))

    def test_both_imports_same_class(self):
        """Test that both import paths resolve to the same class."""
        from src.pyplayer.domain.playlist import Playlist as PlaylistDomain
        from src.main.python.api.playlist import Playlist as PlaylistApi

        self.assertIs(PlaylistDomain, PlaylistApi)


class TestLegacyMainWindowImports(unittest.TestCase):
    """Tests for legacy MainWindow import compatibility."""

    def test_import_main_window_from_pyplayer_ui(self):
        """Test importing MainWindow from src.pyplayer.ui.main_window."""
        from src.pyplayer.ui.main_window import MainWindow

        self.assertIsNotNone(MainWindow)
        self.assertTrue(hasattr(MainWindow, "__init__"))

    def test_import_main_window_from_main_python_ui(self):
        """Test importing MainWindow from src.main.python.ui.main_window."""
        from src.main.python.ui.main_window import MainWindow

        self.assertIsNotNone(MainWindow)
        self.assertTrue(hasattr(MainWindow, "__init__"))

    def test_both_main_window_imports_same_class(self):
        """Test that both import paths resolve to the same MainWindow class."""
        from src.pyplayer.ui.main_window import MainWindow as MainWindowPyplayer
        from src.main.python.ui.main_window import MainWindow as MainWindowMain

        self.assertIs(MainWindowPyplayer, MainWindowMain)


if __name__ == "__main__":
    unittest.main()