"""Benchmark QtMultimedia initialization costs."""

import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PySide6 import QtCore, QtWidgets, QtMultimedia, QtMultimediaWidgets


def benchmark_qtmultimedia_init():
    """Measure QtMultimedia object initialization costs."""
    print("=" * 60)
    print("QTMULTIMEDIA INITIALIZATION BENCHMARK")
    print("=" * 60)

    # Setup QApplication
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseOpenGLES)
    app = QtWidgets.QApplication([])

    # Benchmark 1: Import time (already done, but measure instantiation)
    print("\n=== QVIDEO WIDGET ===")
    start = time.perf_counter()
    video_widget = QtMultimediaWidgets.QVideoWidget()
    elapsed = time.perf_counter() - start
    print(f"  QVideoWidget creation: {elapsed * 1000:.2f} ms")

    print("\n=== QAUDIO OUTPUT ===")
    start = time.perf_counter()
    audio_output = QtMultimedia.QAudioOutput()
    elapsed = time.perf_counter() - start
    print(f"  QAudioOutput creation: {elapsed * 1000:.2f} ms")

    print("\n=== QMEDIA PLAYER ===")
    start = time.perf_counter()
    media_player = QtMultimedia.QMediaPlayer()
    elapsed = time.perf_counter() - start
    print(f"  QMediaPlayer creation: {elapsed * 1000:.2f} ms")

    print("\n=== CONNECTING VIDEO OUTPUT ===")
    start = time.perf_counter()
    media_player.setVideoOutput(video_widget)
    elapsed = time.perf_counter() - start
    print(f"  setVideoOutput: {elapsed * 1000:.2f} ms")

    print("\n=== CONNECTING AUDIO OUTPUT ===")
    start = time.perf_counter()
    media_player.setAudioOutput(audio_output)
    elapsed = time.perf_counter() - start
    print(f"  setAudioOutput: {elapsed * 1000:.2f} ms")

    # Test multiple instantiations
    print("\n=== MULTIPLE INSTANTIATIONS (3x) ===")
    times = []
    for i in range(3):
        start = time.perf_counter()
        vw = QtMultimediaWidgets.QVideoWidget()
        ao = QtMultimedia.QAudioOutput()
        mp = QtMultimedia.QMediaPlayer()
        mp.setVideoOutput(vw)
        mp.setAudioOutput(ao)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  Iteration {i+1}: {elapsed * 1000:.2f} ms")

    avg_time = sum(times) / len(times)
    print(f"  Average: {avg_time * 1000:.2f} ms")

    # Cleanup
    app.quit()


def benchmark_qtmultimedia_with_media():
    """Test QtMultimedia with actual media loading."""
    print("\n" + "=" * 60)
    print("QTMULTIMEDIA MEDIA LOADING BENCHMARK")
    print("=" * 60)

    import tempfile

    # Create a fake video file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        fake_file = Path(f.name)
        f.write(b"FAKE VIDEO CONTENT")

    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseOpenGLES)
    app = QtWidgets.QApplication([])

    video_widget = QtMultimediaWidgets.QVideoWidget()
    audio_output = QtMultimedia.QAudioOutput()
    media_player = QtMultimedia.QMediaPlayer()
    media_player.setVideoOutput(video_widget)
    media_player.setAudioOutput(audio_output)

    print("\n=== SETSOURCE WITH FAKE VIDEO ===")
    start = time.perf_counter()
    media_player.setSource(QtCore.QUrl.fromLocalFile(str(fake_file)))
    elapsed = time.perf_counter() - start
    print(f"  setSource (fake video): {elapsed * 1000:.2f} ms")

    print("\n=== PLAY (EXPECTED TO FAIL) ===")
    start = time.perf_counter()
    media_player.play()
    elapsed = time.perf_counter() - start
    print(f"  play() call: {elapsed * 1000:.2f} ms")

    # Cleanup
    fake_file.unlink()
    app.quit()


def main():
    """Run all QtMultimedia benchmarks."""
    benchmark_qtmultimedia_init()
    benchmark_qtmultimedia_with_media()


if __name__ == "__main__":
    main()
