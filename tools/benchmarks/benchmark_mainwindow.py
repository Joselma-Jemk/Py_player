"""Detailed profiling of MainWindow creation to identify hotspots."""

import cProfile
import pstats
import sys
import tempfile
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PySide6 import QtCore, QtWidgets


def profile_mainwindow_creation():
    """Profile MainWindow creation in detail."""
    print("=" * 60)
    print("MAINWINDOW CREATION PROFILE")
    print("=" * 60)

    # Setup QApplication
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseOpenGLES)
    app = QtWidgets.QApplication([])

    # Create temp dir for playlist manager
    with tempfile.TemporaryDirectory() as tmpdir:
        # Configure CONFIG to use temp dir
        from src.pyplayer.infrastructure.config import settings
        original_runtime = settings.CONFIG.runtime_dir
        settings.CONFIG.runtime_dir = Path(tmpdir)

        # Profile MainWindow creation
        pr = cProfile.Profile()
        pr.enable()

        from src.pyplayer.ui.main_window import MainWindow
        window = MainWindow()

        pr.disable()

        # Clean up
        window.close()
        window.deleteLater()

        # Restore config
        settings.CONFIG.runtime_dir = original_runtime

    app.quit()

    # Print results
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(40)
    print(s.getvalue())

    # Also show top 20 by self time (actual time spent in function, not children)
    print("\n" + "=" * 60)
    print("TOP 20 BY SELF TIME (actual work)")
    print("=" * 60)
    s2 = StringIO()
    ps2 = pstats.Stats(pr, stream=s2).sort_stats('tottime')
    ps2.print_stats(20)
    print(s2.getvalue())


def profile_mainwindow_setup():
    """Profile individual phases of MainWindow setup."""
    print("\n" + "=" * 60)
    print("MAINWINDOW SETUP PHASES")
    print("=" * 60)

    import time

    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseOpenGLES)
    app = QtWidgets.QApplication([])

    with tempfile.TemporaryDirectory() as tmpdir:
        from src.pyplayer.infrastructure.config import settings
        original_runtime = settings.CONFIG.runtime_dir
        settings.CONFIG.runtime_dir = Path(tmpdir)

        phases = {}

        # Phase 1: Import MainWindow
        start = time.perf_counter()
        from src.pyplayer.ui.main_window import MainWindow
        phases['import'] = time.perf_counter() - start

        # Phase 2: Create instance (includes __init__)
        start = time.perf_counter()
        window = MainWindow()
        phases['__init__'] = time.perf_counter() - start

        # Phase 3: Call setup_ui
        start = time.perf_counter()
        window.setup_ui()
        phases['setup_ui'] = time.perf_counter() - start

        # Clean up
        window.close()
        window.deleteLater()

        settings.CONFIG.runtime_dir = original_runtime

    app.quit()

    # Print phase breakdown
    total = sum(phases.values())
    print(f"\n{'PHASE':<20} {'TIME (ms)':<15} {'%'}")
    print("-" * 40)
    for phase, t in sorted(phases.items(), key=lambda x: x[1], reverse=True):
        print(f"{phase:<20} {t * 1000:<15.2f} {t / total * 100:>5.1f}%")
    print("-" * 40)
    print(f"{'TOTAL':<20} {total * 1000:<15.2f} 100.0%")

    # Identify the slowest phase
    slowest = max(phases.items(), key=lambda x: x[1])
    print(f"\n⚠️  SLOWEST PHASE: {slowest[0]} ({slowest[1] * 1000:.2f} ms)")


def profile_playlist_manager_boot():
    """Profile PlaylistManager boot in detail."""
    print("\n" + "=" * 60)
    print("PLAYLIST MANAGER BOOT PROFILE")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)

        pr = cProfile.Profile()
        pr.enable()

        from src.pyplayer.app.services import PlaylistManager
        manager = PlaylistManager(data_dir=temp_dir)

        pr.disable()

    # Print results
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(30)
    print(s.getvalue())


def profile_playlist_manager_with_data():
    """Profile PlaylistManager boot with test data."""
    print("\n" + "=" * 60)
    print("PLAYLIST MANAGER BOOT WITH DATA")
    print("=" * 60)

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        playlists_dir = temp_dir / "playlists"
        playlists_dir.mkdir(parents=True, exist_ok=True)

        # Create test playlists
        from src.pyplayer.domain.playlist import Playlist
        for i in range(10):
            playlist = Playlist()
            playlist.name = f"Test Playlist {i}"

            # Add some fake videos
            for j in range(20):
                fake_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                fake_file.close()
                playlist.add_video(Path(fake_file.name))

            save_path = playlists_dir / f"playlist_{i}.json"
            playlist.save_to_file(save_path)

            # Clean up fake files
            for video in playlist.videos:
                if video.file_path and video.file_path.exists():
                    video.file_path.unlink()

        # Profile boot
        pr = cProfile.Profile()
        pr.enable()

        from src.pyplayer.app.services import PlaylistManager
        manager = PlaylistManager(data_dir=playlists_dir)

        pr.disable()

    # Print results
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(30)
    print(s.getvalue())


def main():
    """Run all profiling."""
    profile_mainwindow_creation()
    profile_mainwindow_setup()
    profile_playlist_manager_boot()
    profile_playlist_manager_with_data()


if __name__ == "__main__":
    main()
