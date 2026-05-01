"""Benchmark for layout operations — addWidget, layouts, widget creation."""

import sys
import time
from pathlib import Path

from PySide6 import QtCore, QtWidgets

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def benchmark_addwidget_cost():
    """Measure the cost of multiple addWidget calls."""
    print("=" * 60)
    print("BENCHMARK: addWidget Cost")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Test 1: Single addWidget
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)

    start = time.perf_counter()
    label = QtWidgets.QLabel("Test")
    layout.addWidget(label)
    single_add = (time.perf_counter() - start) * 1000
    print(f"Single addWidget: {single_add:.1f} ms")

    # Test 2: Multiple addWidget calls (simulate UI construction)
    widget2 = QtWidgets.QWidget()
    layout2 = QtWidgets.QVBoxLayout(widget2)

    widgets_to_add = 50  # Number of widgets like in a typical list
    widgets = []

    start = time.perf_counter()
    for i in range(widgets_to_add):
        w = QtWidgets.QLabel(f"Item {i}")
        widgets.append(w)
        layout2.addWidget(w)
    multiple_adds = (time.perf_counter() - start) * 1000
    print(f"Multiple addWidget ({widgets_to_add} widgets): {multiple_adds:.1f} ms")
    print(f"Average per addWidget: {multiple_adds / widgets_to_add:.2f} ms")

    # Test 3: addWidget with show() after
    widget3 = QtWidgets.QWidget()
    layout3 = QtWidgets.QVBoxLayout(widget3)

    widgets2 = []
    start = time.perf_counter()
    for i in range(widgets_to_add):
        w = QtWidgets.QLabel(f"Item {i}")
        widgets2.append(w)
        layout3.addWidget(w)
        w.show()
    adds_with_show = (time.perf_counter() - start) * 1000
    print(f"Multiple addWidget + show ({widgets_to_add}): {adds_with_show:.1f} ms")

    # Test 4: addWidget then show parent once
    widget4 = QtWidgets.QWidget()
    layout4 = QtWidgets.QVBoxLayout(widget4)

    widgets3 = []
    start = time.perf_counter()
    for i in range(widgets_to_add):
        w = QtWidgets.QLabel(f"Item {i}")
        widgets3.append(w)
        layout4.addWidget(w)
    # Show parent once after all adds
    widget4.show()
    adds_then_show = (time.perf_counter() - start) * 1000
    print(f"Multiple addWidget then show parent: {adds_then_show:.1f} ms")

    return {
        "single_add": single_add,
        "multiple_adds": multiple_adds,
        "average_per_add": multiple_adds / widgets_to_add,
        "adds_with_show": adds_with_show,
        "adds_then_show": adds_then_show,
    }


def benchmark_widget_creation_variety():
    """Measure creation cost of different widget types."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Widget Creation by Type")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    widget_types = [
        ("QLabel", lambda: QtWidgets.QLabel("Test")),
        ("QPushButton", lambda: QtWidgets.QPushButton("Test")),
        ("QSlider", lambda: QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)),
        ("QCheckBox", lambda: QtWidgets.QCheckBox("Test")),
        ("QComboBox", lambda: QtWidgets.QComboBox()),
        ("QLineEdit", lambda: QtWidgets.QLineEdit()),
        ("QTextEdit", lambda: QtWidgets.QTextEdit()),
        ("QListWidget", lambda: QtWidgets.QListWidget()),
        ("QTreeWidget", lambda: QtWidgets.QTreeWidget()),
        ("QTableWidget", lambda: QtWidgets.QTableWidget()),
    ]

    results = {}
    for name, creator in widget_types:
        start = time.perf_counter()
        widget = creator()
        creation_time = (time.perf_counter() - start) * 1000
        results[name] = creation_time
        print(f"{name:20s}: {creation_time:.2f} ms")

    return results


def benchmark_complex_layout():
    """Measure cost of building a complex nested layout."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Complex Nested Layout")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    start = time.perf_counter()

    # Main widget
    main_widget = QtWidgets.QWidget()
    main_layout = QtWidgets.QHBoxLayout(main_widget)

    # Left panel with vertical layout
    left_panel = QtWidgets.QWidget()
    left_layout = QtWidgets.QVBoxLayout(left_panel)
    for i in range(10):
        left_layout.addWidget(QtWidgets.QLabel(f"Left {i}"))

    # Right panel with more nesting
    right_panel = QtWidgets.QWidget()
    right_layout = QtWidgets.QVBoxLayout(right_panel)

    # Add a toolbar-like row
    toolbar = QtWidgets.QWidget()
    toolbar_layout = QtWidgets.QHBoxLayout(toolbar)
    for i in range(5):
        toolbar_layout.addWidget(QtWidgets.QPushButton(f"Btn {i}"))
    right_layout.addWidget(toolbar)

    # Add a central area with grid
    grid_widget = QtWidgets.QWidget()
    grid_layout = QtWidgets.QGridLayout(grid_widget)
    for row in range(5):
        for col in range(5):
            grid_layout.addWidget(QtWidgets.QLabel(f"{row},{col}"), row, col)
    right_layout.addWidget(grid_widget)

    # Add panels to main layout
    main_layout.addWidget(left_panel)
    main_layout.addWidget(right_panel)

    total_time = (time.perf_counter() - start) * 1000
    print(f"Complex nested layout creation: {total_time:.1f} ms")

    # Show widget
    start = time.perf_counter()
    main_widget.show()
    show_time = (time.perf_counter() - start) * 1000
    print(f"Show complex layout: {show_time:.1f} ms")

    return {
        "layout_creation": total_time,
        "show_time": show_time,
    }


if __name__ == "__main__":
    benchmark_addwidget_cost()
    benchmark_widget_creation_variety()
    benchmark_complex_layout()
