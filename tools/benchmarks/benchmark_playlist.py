"""Benchmark: Playlist domain operations performance."""

import tempfile
import time
from pathlib import Path
from typing import List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pyplayer.domain.playlist import Playlist, PlayMode


class BenchmarkResults:
    """Store benchmark results for analysis."""
    def __init__(self):
        self.results = {}

    def add(self, name: str, value: float, unit: str = "ms"):
        self.results[name] = (value, unit)

    def print_summary(self):
        print("\n" + "=" * 60)
        print("PLAYLIST BENCHMARK SUMMARY")
        print("=" * 60)
        for name, (value, unit) in sorted(self.results.items()):
            print(f"{name:40} {value:10.2f} {unit}")


def create_fake_video_files(count: int, temp_dir: Path) -> List[Path]:
    """Create fake .mp4 files for testing."""
    files = []
    for i in range(count):
        fake_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False, dir=temp_dir)
        fake_file.close()
        files.append(Path(fake_file.name))
    return files


def benchmark_playlist_creation(num_videos: int, temp_dir: Path) -> float:
    """Measure Playlist creation with videos."""
    start = time.perf_counter()
    playlist = Playlist()
    files = create_fake_video_files(num_videos, temp_dir)
    for f in files:
        playlist.add_video(f)
    elapsed = time.perf_counter() - start

    # Cleanup
    for f in files:
        if f.exists():
            f.unlink()

    return elapsed


def benchmark_playlist_save_load(num_videos: int, temp_dir: Path) -> tuple[float, float]:
    """Measure Playlist save and load operations."""
    playlist = Playlist()
    playlist.name = "Benchmark Playlist"
    files = create_fake_video_files(num_videos, temp_dir)
    for f in files:
        playlist.add_video(f)

    save_path = temp_dir / "test_playlist.json"

    # Benchmark save
    start = time.perf_counter()
    playlist.save_to_file(save_path)
    save_time = time.perf_counter() - start

    # Benchmark load
    start = time.perf_counter()
    loaded = Playlist.load_from_file(save_path, validate_files=False)
    load_time = time.perf_counter() - start

    # Cleanup
    for f in files:
        if f.exists():
            f.unlink()

    return save_time, load_time


def benchmark_navigation(num_iterations: int, play_mode: PlayMode, temp_dir: Path) -> float:
    """Measure navigation performance for a given play mode."""
    playlist = Playlist()
    files = create_fake_video_files(100, temp_dir)  # 100 videos for navigation
    for f in files:
        playlist.add_video(f)

    playlist.set_play_mode(play_mode)
    playlist.ensure_active()

    # Benchmark: next then previous repeatedly
    start = time.perf_counter()
    for _ in range(num_iterations):
        playlist.get_next_video()
        playlist.get_previous_video()
    elapsed = time.perf_counter() - start

    # Cleanup
    for f in files:
        if f.exists():
            f.unlink()

    return elapsed


def benchmark_add_video_batch(num_videos: int, batch_size: int, temp_dir: Path) -> float:
    """Measure batch video addition performance."""
    playlist = Playlist()
    files = create_fake_video_files(num_videos, temp_dir)

    # Benchmark: add videos in batches
    start = time.perf_counter()
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        for f in batch:
            playlist.add_video(f)
    elapsed = time.perf_counter() - start

    # Cleanup
    for f in files:
        if f.exists():
            f.unlink()

    return elapsed


def benchmark_shuffle_generation(num_videos: int, temp_dir: Path) -> float:
    """Measure shuffle order generation performance."""
    playlist = Playlist()
    files = create_fake_video_files(num_videos, temp_dir)
    for f in files:
        playlist.add_video(f)

    playlist.set_play_mode(PlayMode.SHUFFLE)

    start = time.perf_counter()
    playlist._generate_shuffle_order()
    elapsed = time.perf_counter() - start

    # Cleanup
    for f in files:
        if f.exists():
            f.unlink()

    return elapsed


def main():
    """Run all playlist benchmarks."""
    print("=" * 60)
    print("PLAYLIST DOMAIN BENCHMARK")
    print("=" * 60)

    results = BenchmarkResults()

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)

        # Benchmark 1: Playlist creation with varying sizes
        print("\n=== PLAYLIST CREATION ===")
        for num_videos in [10, 100, 500, 1000]:
            elapsed = benchmark_playlist_creation(num_videos, temp_dir)
            per_video = (elapsed / num_videos) * 1000 if num_videos > 0 else 0
            print(f"  {num_videos:4} videos: {elapsed * 1000:8.2f} ms ({per_video:.3f} ms/video)")
            results.add(f"Creation ({num_videos} videos)", elapsed * 1000)

        # Benchmark 2: Save/Load operations
        print("\n=== SAVE/LOAD OPERATIONS ===")
        for num_videos in [10, 100, 500]:
            save_time, load_time = benchmark_playlist_save_load(num_videos, temp_dir)
            print(f"  {num_videos:4} videos:")
            print(f"    Save: {save_time * 1000:8.2f} ms")
            print(f"    Load: {load_time * 1000:8.2f} ms")
            results.add(f"Save ({num_videos} videos)", save_time * 1000)
            results.add(f"Load ({num_videos} videos)", load_time * 1000)

        # Benchmark 3: Navigation performance
        print("\n=== NAVIGATION PERFORMANCE (100 iterations) ===")
        iterations = 100
        for mode_name, mode in [("NORMAL", PlayMode.NORMAL),
                                ("LOOP_ALL", PlayMode.LOOP_ALL),
                                ("SHUFFLE", PlayMode.SHUFFLE)]:
            elapsed = benchmark_navigation(iterations, mode, temp_dir)
            per_op = (elapsed / iterations) * 1000
            print(f"  {mode_name:10}: {elapsed * 1000:8.2f} ms ({per_op:.4f} ms/op)")
            results.add(f"Nav {mode_name} ({iterations} iters)", elapsed * 1000)

        # Benchmark 4: Batch video addition
        print("\n=== BATCH VIDEO ADDITION ===")
        num_videos = 500
        for batch_size in [1, 10, 50, 100]:
            elapsed = benchmark_add_video_batch(num_videos, batch_size, temp_dir)
            per_video = (elapsed / num_videos) * 1000
            print(f"  Batch size {batch_size:3}: {elapsed * 1000:8.2f} ms ({per_video:.3f} ms/video)")
            results.add(f"Add batch (size={batch_size})", elapsed * 1000)

        # Benchmark 5: Shuffle generation
        print("\n=== SHUFFLE GENERATION ===")
        for num_videos in [100, 500, 1000, 5000]:
            elapsed = benchmark_shuffle_generation(num_videos, temp_dir)
            print(f"  {num_videos:4} videos: {elapsed * 1000:8.2f} ms")
            results.add(f"Shuffle gen ({num_videos} videos)", elapsed * 1000)

    results.print_summary()


if __name__ == "__main__":
    main()
