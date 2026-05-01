"""Benchmark for first video play — measures the deferred QtMultimedia init cost."""

import sys
import time
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.pyplayer.ui.widgets.player import PlayerWidget


def benchmark_first_play():
    """Measure the cost of first video play (including lazy init)."""
    print("=" * 60)
    print("BENCHMARK: First Video Play (Lazy QtMultimedia Init)")
    print("=" * 60)

    # Create QApplication
    start = time.perf_counter()
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    app_creation = (time.perf_counter() - start) * 1000
    print(f"QApplication: {app_creation:.1f} ms")

    # Create PlayerWidget (should be fast now)
    start = time.perf_counter()
    player_widget = PlayerWidget()
    widget_creation = (time.perf_counter() - start) * 1000
    print(f"PlayerWidget creation: {widget_creation:.1f} ms")

    # Show widget
    start = time.perf_counter()
    player_widget.show()
    widget_show = (time.perf_counter() - start) * 1000
    print(f"PlayerWidget show: {widget_show:.1f} ms")

    # Process events
    QtWidgets.QApplication.processEvents()

    # Now simulate first play — this should trigger lazy init
    print("\n--- First Play (triggers lazy init) ---")

    # Step 1: Access video_player property (triggers init)
    start = time.perf_counter()
    video_player = player_widget.video_player
    property_access = (time.perf_counter() - start) * 1000
    print(f"Access video_player property: {property_access:.1f} ms")

    # Step 2: Access audio_output property
    start = time.perf_counter()
    audio_output = player_widget.audio_output
    audio_access = (time.perf_counter() - start) * 1000
    print(f"Access audio_output property: {audio_access:.1f} ms")

    # Step 3: Access video_output property
    start = time.perf_counter()
    video_output = player_widget.video_output
    video_output_access = (time.perf_counter() - start) * 1000
    print(f"Access video_output property: {video_output_access:.1f} ms")

    # Total first play cost
    total_first_play = property_access + audio_access + video_output_access
    print(f"\nTotal first play cost: {total_first_play:.1f} ms")

    # Second access (should be cached)
    print("\n--- Second Access (should be cached) ---")
    start = time.perf_counter()
    video_player2 = player_widget.video_player
    second_access = (time.perf_counter() - start) * 1000
    print(f"Access video_player property again: {second_access:.1f} ms")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total boot cost (QApp + Widget): {app_creation + widget_creation + widget_show:.1f} ms")
    print(f"First play cost (lazy init): {total_first_play:.1f} ms")
    print(f"Second access cost: {second_access:.1f} ms")

    return {
        "app_creation": app_creation,
        "widget_creation": widget_creation,
        "widget_show": widget_show,
        "first_play_total": total_first_play,
        "second_access": second_access,
    }


if __name__ == "__main__":
    benchmark_first_play()
