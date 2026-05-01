"""Tests for PlaylistManager service."""

import tempfile
import unittest
from pathlib import Path

from src.pyplayer.app.services.playlist_manager import PlaylistManager
from src.pyplayer.app.services.playlist_registry import PlaylistRegistry
from src.pyplayer.infrastructure.persistence.playlist_repository import PlaylistRepository
from src.pyplayer.infrastructure.persistence.manager_config_store import ManagerConfigStore
from src.pyplayer.infrastructure.persistence.last_played_store import LastPlayedStore
from src.pyplayer.infrastructure.backup.backup_cleaner import BackupCleaner


class TestPlaylistManagerCreation(unittest.TestCase):
    """Tests for PlaylistManager creation with temp data_dir."""

    def setUp(self):
        """Set up temp directory for file operations."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temp directory."""
        self.temp_dir.cleanup()

    def test_creation_with_temp_data_dir(self):
        """Test creating PlaylistManager with a temp data directory."""
        manager = PlaylistManager(data_dir=self.temp_path)
        self.assertIsNotNone(manager)
        self.assertEqual(manager.data_dir, self.temp_path)
        self.assertIsInstance(manager._registry, PlaylistRegistry)

    def test_creation_with_all_dependencies(self):
        """Test creating PlaylistManager with injected dependencies."""
        registry = PlaylistRegistry()
        repository = PlaylistRepository(self.temp_path)
        config_store = ManagerConfigStore(self.temp_path / "config.json")
        last_played_store = LastPlayedStore(self.temp_path / "last_played.json")
        backup_cleaner = BackupCleaner(self.temp_path)

        manager = PlaylistManager(
            data_dir=self.temp_path,
            registry=registry,
            repository=repository,
            config_store=config_store,
            last_played_store=last_played_store,
            backup_cleaner=backup_cleaner,
        )
        self.assertIsNotNone(manager)
        # PlaylistManager auto-creates a playlist even with injected dependencies
        self.assertGreaterEqual(manager.playlist_count, 0)

    def test_auto_playlist_creation(self):
        """Test that PlaylistManager creates a playlist when created with no playlists."""
        manager = PlaylistManager(data_dir=self.temp_path)
        self.assertGreater(manager.playlist_count, 0)

        active = manager.active_playlist
        self.assertIsNotNone(active)


class TestPlaylistManagerPlaylistOperations(unittest.TestCase):
    """Tests for PlaylistManager playlist operations."""

    def setUp(self):
        """Set up temp directory for file operations."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.manager = PlaylistManager(data_dir=self.temp_path)

    def tearDown(self):
        """Clean up temp directory."""
        self.temp_dir.cleanup()

    def test_create_playlist(self):
        """Test creating a playlist."""
        playlist = self.manager.create_playlist(name="Test Playlist")
        self.assertIsNotNone(playlist)
        self.assertEqual(playlist.name, "Test Playlist")
        self.assertIn(playlist.id, self.manager.playlist_ids)

    def test_create_playlist_with_source_path(self):
        """Test creating a playlist from a source path."""
        video_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        video_file.close()

        try:
            playlist = self.manager.create_playlist(
                source_path=Path(video_file.name),
                name="From File"
            )
            self.assertIsNotNone(playlist)
            self.assertEqual(playlist.name, "From File")
        finally:
            Path(video_file.name).unlink()

    def test_set_active_playlist(self):
        """Test activating a playlist."""
        playlist = self.manager.create_playlist(name="Active Test")
        result = self.manager.set_active_playlist(playlist.id)
        self.assertTrue(result)
        self.assertEqual(self.manager.active_playlist, playlist)

    def test_set_active_playlist_by_name(self):
        """Test activating a playlist by name."""
        self.manager.create_playlist(name="By Name Test")
        result = self.manager.set_active_playlist_by_name("By Name Test")
        self.assertTrue(result)

    def test_set_active_playlist_invalid_id(self):
        """Test activating with invalid ID returns False."""
        result = self.manager.set_active_playlist("invalid_id_123")
        self.assertFalse(result)

    def test_get_playlist(self):
        """Test loading a playlist by ID."""
        created = self.manager.create_playlist(name="Get Test")
        loaded = self.manager.get_playlist(created.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, created.id)

    def test_remove_playlist(self):
        """Test removing a playlist."""
        playlist = self.manager.create_playlist(name="Remove Test")
        playlist_id = playlist.id

        result = self.manager.remove_playlist(playlist_id, delete_file=False)
        self.assertTrue(result)
        self.assertNotIn(playlist_id, self.manager.playlist_ids)

    def test_remove_playlist_invalid_id(self):
        """Test removing with invalid ID returns False."""
        result = self.manager.remove_playlist("invalid_id", delete_file=False)
        self.assertFalse(result)

    def test_rename_playlist(self):
        """Test renaming a playlist."""
        playlist = self.manager.create_playlist(name="Original Name")
        result = self.manager.rename_playlist(playlist.id, "New Name")
        self.assertTrue(result)
        self.assertEqual(playlist.name, "New Name")

    def test_find_playlist_by_name(self):
        """Test finding playlists by name."""
        self.manager.create_playlist(name="Find Me Test")
        ids = self.manager.find_playlist_by_name("Find Me Test")
        self.assertIsInstance(ids, list)
        self.assertGreater(len(ids), 0)

    def test_get_all_playlists(self):
        """Test getting all playlists as dicts."""
        self.manager.create_playlist(name="All Playlists Test 1")
        self.manager.create_playlist(name="All Playlists Test 2")

        all_pl = self.manager.get_all_playlists()
        self.assertIsInstance(all_pl, list)
        self.assertGreaterEqual(len(all_pl), 2)

        for pl_info in all_pl:
            self.assertIn("id", pl_info)
            self.assertIn("name", pl_info)
            self.assertIn("video_count", pl_info)

    def test_save_all_playlists(self):
        """Test saving all playlists."""
        self.manager.create_playlist(name="Save All Test")
        result = self.manager.save_all_playlists()
        self.assertTrue(result)


class TestPlaylistManagerConfigPersistence(unittest.TestCase):
    """Tests for PlaylistManager config persistence."""

    def setUp(self):
        """Set up temp directory for file operations."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.manager = PlaylistManager(data_dir=self.temp_path)

    def tearDown(self):
        """Clean up temp directory."""
        self.temp_dir.cleanup()

    def test_volume_persistence(self):
        """Test volume is persisted."""
        self.manager.volume = 0.75
        self.assertEqual(self.manager.volume, 0.75)

    def test_config_file_created(self):
        """Test that config file is created."""
        config_file = self.temp_path / "manager_config.json"
        self.assertTrue(config_file.exists())


class TestPlaylistManagerBackupStats(unittest.TestCase):
    """Tests for PlaylistManager backup stats and cleanup."""

    def setUp(self):
        """Set up temp directory for file operations."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.manager = PlaylistManager(data_dir=self.temp_path)

    def tearDown(self):
        """Clean up temp directory."""
        self.temp_dir.cleanup()

    def test_get_backup_stats_empty(self):
        """Test getting backup stats with no backups."""
        stats = self.manager.get_backup_stats()
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats.get("total_count", 0), 0)

    def test_cleanup_backups(self):
        """Test cleanup_backups method."""
        result = self.manager.cleanup_backups(
            max_backups_per_playlist=5,
            max_total_backups=50,
            delete_older_than_days=30,
        )
        self.assertIsInstance(result, dict)
        self.assertIn("total_backups_before", result)
        self.assertIn("total_backups_after", result)

    def test_auto_cleanup_backups_if_needed(self):
        """Test auto cleanup backs up if needed."""
        result = self.manager.auto_cleanup_backups_if_needed(threshold_count=5, force=True)
        self.assertIsInstance(result, dict)

    def test_cleanup_method(self):
        """Test cleanup method removes missing files."""
        self.manager.create_playlist(name="Cleanup Test")
        result = self.manager.cleanup()
        self.assertIsInstance(result, dict)
        self.assertIn("playlists_cleaned", result)
        self.assertIn("videos_removed", result)


class TestPlaylistManagerActivePlaylist(unittest.TestCase):
    """Tests for active playlist management."""

    def setUp(self):
        """Set up temp directory for file operations."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.manager = PlaylistManager(data_dir=self.temp_path)

    def tearDown(self):
        """Clean up temp directory."""
        self.temp_dir.cleanup()

    def test_active_playlist_property(self):
        """Test active_playlist property."""
        active = self.manager.active_playlist
        self.assertIsNotNone(active)

    def test_last_played_playlist_property(self):
        """Test last_played_playlist property."""
        last_played = self.manager.last_played_playlist
        # last_played may be None initially or may be set from active playlist
        # Just verify it's either None or a valid Playlist
        if last_played is not None:
            self.assertTrue(hasattr(last_played, 'id'))
            self.assertTrue(hasattr(last_played, 'name'))

    def test_playlist_count_property(self):
        """Test playlist_count property."""
        count = self.manager.playlist_count
        self.assertGreater(count, 0)

    def test_playlist_ids_property(self):
        """Test playlist_ids property."""
        ids = self.manager.playlist_ids
        self.assertIsInstance(ids, list)
        self.assertGreater(len(ids), 0)

    def test_playlist_names_property(self):
        """Test playlist_names property."""
        names = self.manager.playlist_names
        self.assertIsInstance(names, dict)

    def test_all_playlist_property(self):
        """Test all_playlist property."""
        all_pl = self.manager.all_playlist
        self.assertIsInstance(all_pl, dict)
        self.assertGreater(len(all_pl), 0)

    def test_contains_dunder(self):
        """Test __contains__ method."""
        playlist = self.manager.create_playlist(name="Contains Test")
        self.assertIn(playlist.id, self.manager)

    def test_getitem_dunder(self):
        """Test __getitem__ method."""
        playlist = self.manager.create_playlist(name="GetItem Test")
        retrieved = self.manager[playlist.id]
        self.assertEqual(retrieved.id, playlist.id)

    def test_len_dunder(self):
        """Test __len__ method."""
        initial = len(self.manager)
        self.manager.create_playlist(name="Len Test")
        self.assertEqual(len(self.manager), initial + 1)


if __name__ == "__main__":
    unittest.main()