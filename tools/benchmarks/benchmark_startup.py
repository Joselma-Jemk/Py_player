"""Benchmark: Application startup costs (imports, MainWindow, PlaylistManager)."""

import cProfile
import pstats
import sys
import tempfile
import time
from io import StringIO
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def benchmark_imports():
    """Measure import costs."""
    print("\n=== IMPORT COSTS ===")
    start = time.perf_counter()
    from src.pyplayer.bootstrap import run  # type: ignore
    import_time = time.perf_counter() - start
    print(f"Time to import bootstrap: {import_time * 1000:.2f} ms")
    return import_time

def benchmark_qapp_creation():
    """Measure QApplication creation cost."""
    print("\n=== QAPPLICATION CREATION ===")
    from PySide6 import QtCore, QtWidgets

    start = time.perf_counter()
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseOpenGLES)
    app = QtWidgets.QApplication([])
    creation_time = time.perf_counter() - start
    print(f"QApplication creation: {creation_time * 1000:.2f} ms")
    # Don't quit - we'll reuse the app
    return app, creation_time

def benchmark_playlist_manager_boot(temp_dir: Path):
    """Measure PlaylistManager boot cost with empty state."""
    print("\n=== PLAYLIST MANAGER BOOT (EMPTY) ===")
    start = time.perf_counter()
    from src.pyplayer.app.services import PlaylistManager
    manager = PlaylistManager(data_dir=temp_dir)
    boot_time = time.perf_counter() - start
    print(f"PlaylistManager boot (empty): {boot_time * 1000:.2f} ms")
    return boot_time

def benchmark_playlist_manager_with_playlists(temp_dir: Path, num_playlists: int):
    """Measure PlaylistManager boot cost with playlists."""
    print(f"\n=== PLAYLIST MANAGER BOOT ({num_playlists} PLAYLISTS) ===")
    from src.pyplayer.app.services import PlaylistManager
    from src.pyplayer.domain.playlist import Playlist
    import tempfile

    # Create test playlists
    playlists_dir = temp_dir / "playlists"
    playlists_dir.mkdir(parents=True, exist_ok=True)

    for i in range(num_playlists):
        playlist = Playlist()
        playlist.name = f"Test Playlist {i}"

        # Add some fake videos
        for j in range(10):
            fake_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            fake_file.close()
            playlist.add_video(Path(fake_file.name))

        save_path = playlists_dir / f"playlist_{i}.json"
        playlist.save_to_file(save_path)

        # Clean up fake files
        for video in playlist.videos:
            if video.file_path and video.file_path.exists():
                video.file_path.unlink()

    # Now measure boot time
    start = time.perf_counter()
    manager = PlaylistManager(data_dir=playlists_dir)
    boot_time = time.perf_counter() - start
    print(f"PlaylistManager boot ({num_playlists} playlists): {boot_time * 1000:.2f} ms")
    print(f"  -> Time per playlist: {(boot_time / num_playlists) * 1000:.2f} ms")
    return boot_time

def benchmark_main_window_offscreen(app):
    """Measure MainWindow creation cost (offscreen, no show)."""
    print("\n=== MAIN WINDOW CREATION (OFFSCREEN) ===")

    start = time.perf_counter()
    from src.pyplayer.ui.main_window import MainWindow
    window = MainWindow()  # Don't call show()
    creation_time = time.perf_counter() - start
    print(f"MainWindow creation (offscreen): {creation_time * 1000:.2f} ms")

    # Clean up window
    window.close()
    window.deleteLater()

    return creation_time

def run_full_profile():
    """Run cProfile on full startup."""
    print("\n=== CPROFILE: FULL STARTUP ===")
    pr = cProfile.Profile()
    pr.enable()

    from PySide6 import QtCore, QtWidgets
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseOpenGLES)
    app = QtWidgets.QApplication([])

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)

        # Run all benchmarks
        benchmark_imports()
        benchmark_playlist_manager_boot(temp_dir)
        benchmark_main_window_offscreen(app)

    app.quit()

    pr.disable()

    # Print top 20 functions
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(30)
    print(s.getvalue())

def main():
    """Run all benchmarks."""
    print("=" * 60)
    print("PYPLAYER STARTUP BENCHMARK")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)

        # Basic measurements
        import_time = benchmark_imports()
        qapp, qapp_time = benchmark_qapp_creation()
        empty_boot_time = benchmark_playlist_manager_boot(temp_dir)

        # Boot with playlists
        playlist_10_time = benchmark_playlist_manager_with_playlists(temp_dir, 10)
        playlist_50_time = benchmark_playlist_manager_with_playlists(temp_dir, 50)

        # MainWindow creation (reuse existing QApplication)
        window_time = benchmark_main_window_offscreen(qapp)

        # Clean up QApplication
        qapp.quit()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Imports:               {import_time * 1000:.2f} ms")
    print(f"QApplication creation: {qapp_time * 1000:.2f} ms")
    print(f"PlaylistManager boot (empty):  {empty_boot_time * 1000:.2f} ms")
    print(f"PlaylistManager boot (10):    {playlist_10_time * 1000:.2f} ms")
    print(f"PlaylistManager boot (50):    {playlist_50_time * 1000:.2f} ms")
    print(f"MainWindow creation:   {window_time * 1000:.2f} ms")

    total_estimated = import_time + qapp_time + empty_boot_time + window_time
    print(f"\nEstimated cold startup: ~{total_estimated * 1000:.0f} ms")

    # Ask if user wants full profile
    print("\nRun full cProfile? (y/n): ", end='')
    # Auto-run for batch mode
    print("y")
    run_full_profile()

if __name__ == "__main__":
    main()
