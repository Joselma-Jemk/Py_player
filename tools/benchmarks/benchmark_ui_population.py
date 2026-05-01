"""Benchmark for UI list population — playlist and video lists."""

import sys
import tempfile
import time
from pathlib import Path

from PySide6 import QtCore, QtWidgets

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.pyplayer.app.services.playlist_manager import PlaylistManager
from src.pyplayer.ui.widgets.dock_widget import DockWidget


def create_test_video_files(temp_dir: Path, count: int = 50) -> list[Path]:
    """Create dummy video files for testing."""
    files = []
    for i in range(count):
        video_file = temp_dir / f"video_{i:04d}.mp4"
        video_file.write_text(f"dummy video content {i}")
        files.append(video_file)
    return files


def benchmark_playlist_list_population():
    """Measure playlist list widget population."""
    print("=" * 60)
    print("BENCHMARK: Playlist List Population")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp())

    # Create PlaylistManager with some playlists
    start = time.perf_counter()
    manager = PlaylistManager(data_dir=temp_dir, synchronous=True)

    # Create multiple playlists
    for i in range(10):
        manager.create_playlist(name=f"Playlist {i+1}")
    manager_creation = (time.perf_counter() - start) * 1000
    print(f"PlaylistManager creation (10 playlists): {manager_creation:.1f} ms")

    # Create DockWidget
    start = time.perf_counter()
    dock = DockWidget(manager)
    dock_creation = (time.perf_counter() - start) * 1000
    print(f"DockWidget creation: {dock_creation:.1f} ms")

    # Show widget
    start = time.perf_counter()
    dock.show()
    dock_show = (time.perf_counter() - start) * 1000
    print(f"DockWidget show: {dock_show:.1f} ms")

    # Process events
    QtWidgets.QApplication.processEvents()

    # Measure refresh time
    start = time.perf_counter()
    dock.refresh_playlist_list()
    refresh_time = (time.perf_counter() - start) * 1000
    print(f"Playlist list refresh: {refresh_time:.1f} ms")

    # Measure switching active playlist
    start = time.perf_counter()
    manager.set_active_playlist_by_name("Playlist 5")
    QtWidgets.QApplication.processEvents()
    switch_time = (time.perf_counter() - start) * 1000
    print(f"Switch active playlist: {switch_time:.1f} ms")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = manager_creation + dock_creation + dock_show + refresh_time
    print(f"Total population cost: {total:.1f} ms")

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "manager_creation": manager_creation,
        "dock_creation": dock_creation,
        "dock_show": dock_show,
        "refresh_time": refresh_time,
        "switch_time": switch_time,
        "total": total,
    }


def benchmark_video_list_population():
    """Measure video list widget population."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Video List Population")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Create temp directory with video files
    temp_dir = Path(tempfile.mkdtemp())
    video_files = create_test_video_files(temp_dir, count=100)

    # Create PlaylistManager
    manager = PlaylistManager(data_dir=temp_dir, synchronous=True)
    playlist = manager.create_playlist(name="Test Playlist", source_path=temp_dir)

    # Create DockWidget
    dock = DockWidget(manager)
    dock.show()
    QtWidgets.QApplication.processEvents()

    # Measure video list refresh
    start = time.perf_counter()
    dock.refresh_video_list()
    QtWidgets.QApplication.processEvents()
    video_refresh = (time.perf_counter() - start) * 1000
    print(f"Video list refresh (100 videos): {video_refresh:.1f} ms")

    # Measure refresh again (should be cached/faster)
    start = time.perf_counter()
    dock.refresh_video_list()
    QtWidgets.QApplication.processEvents()
    video_refresh_cached = (time.perf_counter() - start) * 1000
    print(f"Video list refresh (cached): {video_refresh_cached:.1f} ms")

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "video_refresh": video_refresh,
        "video_refresh_cached": video_refresh_cached,
    }


if __name__ == "__main__":
    benchmark_playlist_list_population()
    benchmark_video_list_population()
