import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.main.python.api.playlist import Playlist
from src.main.python.api.pyplayer_manager import PlaylistManager


class AtomicSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir_obj = tempfile.TemporaryDirectory(prefix='pyplayer_atomic_')
        self.temp_dir = Path(self.temp_dir_obj.name)

    def tearDown(self) -> None:
        self.temp_dir_obj.cleanup()

    def test_playlist_save_preserves_existing_file_if_dump_fails(self) -> None:
        playlist = Playlist()
        video_file = self.temp_dir / 'sample.mp4'
        video_file.touch()
        self.assertTrue(playlist.add_video(video_file))

        target = self.temp_dir / 'playlist.json'
        baseline = '{"stable": true}\n'
        target.write_text(baseline, encoding='utf-8')

        def failing_dump(data: object, stream: object, **kwargs: object) -> None:
            stream.write('{"corrupted":')
            raise RuntimeError('forced dump failure')

        with patch('src.main.python.api.playlist.json.dump', side_effect=failing_dump):
            result = playlist.save_to_file(target, create_backup=False)

        self.assertFalse(result)
        self.assertEqual(target.read_text(encoding='utf-8'), baseline)

    def test_manager_save_config_preserves_existing_file_if_dump_fails(self) -> None:
        manager = PlaylistManager(data_dir=self.temp_dir)
        manager.volume = 0.33

        config_path = self.temp_dir / 'manager_config.json'
        baseline = config_path.read_text(encoding='utf-8')

        def failing_dump(data: object, stream: object, **kwargs: object) -> None:
            stream.write('{"broken":')
            raise RuntimeError('forced dump failure')

        with patch('src.main.python.api.pyplayer_manager.json.dump', side_effect=failing_dump):
            manager._save_config()

        self.assertEqual(config_path.read_text(encoding='utf-8'), baseline)

    def test_manager_save_last_played_preserves_existing_file_if_dump_fails(self) -> None:
        manager = PlaylistManager(data_dir=self.temp_dir)
        created = manager.create_playlist(name='Atomic Last Played')
        self.assertTrue(manager.set_active_playlist(created.id))

        last_played_path = self.temp_dir / 'last_played.json'
        baseline = last_played_path.read_text(encoding='utf-8')

        def failing_dump(data: object, stream: object, **kwargs: object) -> None:
            stream.write('{"broken":')
            raise RuntimeError('forced dump failure')

        with patch('src.main.python.api.pyplayer_manager.json.dump', side_effect=failing_dump):
            manager._save_last_played()

        self.assertEqual(last_played_path.read_text(encoding='utf-8'), baseline)


if __name__ == '__main__':
    unittest.main()
