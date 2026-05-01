"""Benchmark for fonts and icons loading/caching."""

import sys
import time
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.pyplayer.ui.theme import fonts, icons


def benchmark_font_loading():
    """Measure font loading and usage."""
    print("=" * 60)
    print("BENCHMARK: Font Loading")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Measure first font path access
    start = time.perf_counter()
    font_path1 = fonts.get_font_path()
    font1_time = (time.perf_counter() - start) * 1000
    print(f"First font path access: {font1_time:.1f} ms")
    print(f"  Font path: {font_path1 if font_path1 else 'Not found'}")

    # Measure second font path access (should be cached)
    start = time.perf_counter()
    font_path2 = fonts.get_font_path()
    font2_time = (time.perf_counter() - start) * 1000
    print(f"Second font path access (cached): {font2_time:.1f} ms")

    # Measure find_font (direct check)
    start = time.perf_counter()
    found = fonts.find_font()
    find_time = (time.perf_counter() - start) * 1000
    print(f"find_font() check: {find_time:.1f} ms")
    print(f"  Found: {found is not None}")

    # Test loading font into QFont
    if font_path1:
        start = time.perf_counter()
        font = QtGui.QFont(font_path1, 12)
        load_time = (time.perf_counter() - start) * 1000
        print(f"Load QFont from path: {load_time:.1f} ms")

    return {
        "first_font_access": font1_time,
        "second_font_access": font2_time,
        "find_font": find_time,
        "qfont_load": locals().get('load_time', 0),
    }


def benchmark_icon_loading():
    """Measure icon loading and caching."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Icon Loading")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Test icon IDs that are commonly used
    icon_ids = [1, 2, 3, 4, 5]  # Some icon IDs from the theme

    icon_times = []
    for icon_id in icon_ids:
        start = time.perf_counter()
        icon = icons.py_player_icone(icon_id)
        icon_time = (time.perf_counter() - start) * 1000
        icon_times.append(icon_time)
        if icon:
            print(f"Icon {icon_id}: {icon_time:.1f} ms")
        else:
            print(f"Icon {icon_id}: None (fallback)")

    # Test accessing same icon again (cache)
    if icon_ids:
        start = time.perf_counter()
        icon_cached = icons.py_player_icone(icon_ids[0])
        cached_time = (time.perf_counter() - start) * 1000
        print(f"Icon {icon_ids[0]} (cached): {cached_time:.1f} ms")

    return {
        "icon_times": icon_times,
        "cached_time": cached_time if icon_ids else 0,
    }


def benchmark_stylesheet_application():
    """Measure stylesheet application cost."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Stylesheet Application")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Create a simple widget
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    label = QtWidgets.QLabel("Test Label")
    button = QtWidgets.QPushButton("Test Button")
    layout.addWidget(label)
    layout.addWidget(button)

    # Apply simple stylesheet
    stylesheet = """
        QWidget { background: #f0f0f0; }
        QLabel { color: #333; font-size: 12px; }
        QPushButton { background: #2196F3; color: white; }
    """

    start = time.perf_counter()
    widget.setStyleSheet(stylesheet)
    stylesheet_time = (time.perf_counter() - start) * 1000
    print(f"Apply stylesheet: {stylesheet_time:.1f} ms")

    # Apply again (potential cache)
    start = time.perf_counter()
    widget.setStyleSheet(stylesheet)
    stylesheet_cached_time = (time.perf_counter() - start) * 1000
    print(f"Apply stylesheet (again): {stylesheet_cached_time:.1f} ms")

    return {
        "stylesheet_first": stylesheet_time,
        "stylesheet_cached": stylesheet_cached_time,
    }


if __name__ == "__main__":
    benchmark_font_loading()
    benchmark_icon_loading()
    benchmark_stylesheet_application()
