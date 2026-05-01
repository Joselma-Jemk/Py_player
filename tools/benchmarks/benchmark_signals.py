"""Benchmark for signal connections and emissions."""

import sys
import time
from pathlib import Path

from PySide6 import QtCore, QtWidgets

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def benchmark_signal_connections():
    """Measure cost of signal connections."""
    print("=" * 60)
    print("BENCHMARK: Signal Connections")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Test 1: Single connection
    button = QtWidgets.QPushButton("Test")
    counter = [0]

    start = time.perf_counter()
    button.clicked.connect(lambda: counter.__setitem__(0, counter[0] + 1))
    single_connect = (time.perf_counter() - start) * 1000
    print(f"Single signal connection: {single_connect:.2f} ms")

    # Test 2: Multiple connections to same signal
    button2 = QtWidgets.QPushButton("Test")
    counters = [0] * 10

    start = time.perf_counter()
    for i in range(10):
        button2.clicked.connect(lambda idx=i: counters.__setitem__(idx, counters[idx] + 1))
    multiple_connects = (time.perf_counter() - start) * 1000
    print(f"Multiple connections (10): {multiple_connects:.2f} ms")

    # Test 3: Disconnect (disconnect requires signal)
    start = time.perf_counter()
    button2.clicked.disconnect()
    disconnect_time = (time.perf_counter() - start) * 1000
    print(f"Disconnect all: {disconnect_time:.2f} ms")

    return {
        "single_connect": single_connect,
        "multiple_connects": multiple_connects,
        "disconnect": disconnect_time,
    }


def benchmark_signal_emissions():
    """Measure cost of signal emissions."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Signal Emissions")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Custom signal class
    class Emitter(QtCore.QObject):
        test_signal = QtCore.Signal(int)
        value_changed = QtCore.Signal(int)

    emitter = Emitter()
    call_count = [0]

    def slot(value):
        call_count[0] += 1

    # Test 1: Emission with no connections
    start = time.perf_counter()
    for i in range(10000):
        emitter.test_signal.emit(i)
    emit_no_conn = (time.perf_counter() - start) * 1000
    print(f"Emit 10000x (no connections): {emit_no_conn:.1f} ms")

    # Test 2: Emission with one connection
    emitter.test_signal.connect(slot)
    call_count[0] = 0

    start = time.perf_counter()
    for i in range(10000):
        emitter.test_signal.emit(i)
    emit_one_conn = (time.perf_counter() - start) * 1000
    print(f"Emit 10000x (1 connection): {emit_one_conn:.1f} ms")
    print(f"  Callbacks executed: {call_count[0]}")

    # Test 3: Emission with multiple connections
    emitter2 = Emitter()
    call_counts = [[0] for _ in range(10)]

    def make_slot(idx):
        return lambda: call_counts[idx].__setitem__(0, call_counts[idx][0] + 1)

    for i in range(10):
        emitter2.test_signal.connect(make_slot(i))

    start = time.perf_counter()
    for i in range(10000):
        emitter2.test_signal.emit(i)
    emit_multi_conn = (time.perf_counter() - start) * 1000
    print(f"Emit 10000x (10 connections): {emit_multi_conn:.1f} ms")

    return {
        "emit_no_connection": emit_no_conn,
        "emit_one_connection": emit_one_conn,
        "emit_multi_connection": emit_multi_conn,
    }


def benchmark_signal_block():
    """Measure benefit of blocking signals during bulk updates."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Signal Blocking Benefit")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    # Test 1: Slider with connected signal (unblocked)
    slider1 = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    call_count1 = [0]
    slider1.valueChanged.connect(lambda: call_count1.__setitem__(0, call_count1[0] + 1))

    start = time.perf_counter()
    for i in range(100):
        slider1.setValue(i)
    unblocked_time = (time.perf_counter() - start) * 1000
    print(f"SetValue 100x (unblocked): {unblocked_time:.1f} ms")
    print(f"  Signals emitted: {call_count1[0]}")

    # Test 2: Slider with blocked signals
    slider2 = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    call_count2 = [0]
    slider2.valueChanged.connect(lambda: call_count2.__setitem__(0, call_count2[0] + 1))

    start = time.perf_counter()
    slider2.blockSignals(True)
    for i in range(100):
        slider2.setValue(i)
    slider2.blockSignals(False)
    blocked_time = (time.perf_counter() - start) * 1000
    print(f"SetValue 100x (blocked): {blocked_time:.1f} ms")
    print(f"  Signals emitted: {call_count2[0]}")
    print(f"  Speedup: {unblocked_time / blocked_time:.1f}x")

    return {
        "unblocked_time": unblocked_time,
        "blocked_time": blocked_time,
        "speedup": unblocked_time / blocked_time,
    }


def benchmark_qtimer_overhead():
    """Measure QTimer overhead for deferred operations."""
    print("\n" + "=" * 60)
    print("BENCHMARK: QTimer Overhead")
    print("=" * 60)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    execution_times = []

    def timed_callback():
        start = time.perf_counter()
        # Simulate some work
        total = sum(range(1000))
        execution_times.append((time.perf_counter() - start) * 1000)

    # Test: Schedule multiple deferred calls
    start = time.perf_counter()
    for i in range(5):
        QtCore.QTimer.singleShot(0, timed_callback)
    schedule_time = (time.perf_counter() - start) * 1000
    print(f"Schedule 5 QTimer.singleShot(0): {schedule_time:.2f} ms")

    # Execute them
    QtWidgets.QApplication.processEvents()

    if execution_times:
        avg_execution = sum(execution_times) / len(execution_times)
        print(f"Average callback execution: {avg_execution:.2f} ms")

    return {
        "schedule_time": schedule_time,
        "avg_execution": avg_execution if execution_times else 0,
    }


if __name__ == "__main__":
    benchmark_signal_connections()
    benchmark_signal_emissions()
    benchmark_signal_block()
    benchmark_qtimer_overhead()
