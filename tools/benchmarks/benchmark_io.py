"""Benchmark: I/O and filesystem operations performance."""

import os
import tempfile
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pyplayer.infrastructure.filesystem import find_path, reset_find_path_cache
from src.pyplayer.infrastructure.persistence.io_utils import write_json_atomic
import json


class BenchmarkResults:
    """Store benchmark results for analysis."""
    def __init__(self):
        self.results = {}

    def add(self, name: str, value: float, unit: str = "ms"):
        self.results[name] = (value, unit)

    def print_summary(self):
        print("\n" + "=" * 60)
        print("I/O BENCHMARK SUMMARY")
        print("=" * 60)
        for name, (value, unit) in sorted(self.results.items()):
            print(f"{name:40} {value:10.2f} {unit}")


def benchmark_find_path(temp_dir: Path, num_searches: int = 100) -> float:
    """Measure find_path performance with cached and uncached searches."""
    # Create test files
    test_file = temp_dir / "test_file.txt"
    test_file.write_text("test content")

    # Warm up with cached search
    find_path("test_file.txt", parent_dir=temp_dir)

    # Benchmark cached searches
    start = time.perf_counter()
    for _ in range(num_searches):
        find_path("test_file.txt", parent_dir=temp_dir)
    cached_time = time.perf_counter() - start

    # Reset cache
    reset_find_path_cache()

    # Benchmark uncached searches
    start = time.perf_counter()
    for _ in range(num_searches):
        find_path("test_file.txt", parent_dir=temp_dir)
    uncached_time = time.perf_counter() - start

    print(f"  Cached:   {cached_time * 1000:8.2f} ms ({(cached_time / num_searches) * 1000:.4f} ms/search)")
    print(f"  Uncached: {uncached_time * 1000:8.2f} ms ({(uncached_time / num_searches) * 1000:.4f} ms/search)")

    return uncached_time  # Return worst case


def benchmark_json_write_atomic(file_size_kb: int, temp_dir: Path) -> float:
    """Measure atomic JSON write performance."""
    test_file = temp_dir / "test.json"

    # Create test data
    test_data = {"data": "x" * (file_size_kb * 1024)}

    # Warm up
    write_json_atomic(test_file, test_data)
    if test_file.exists():
        test_file.unlink()

    # Benchmark
    start = time.perf_counter()
    write_json_atomic(test_file, test_data)
    elapsed = time.perf_counter() - start

    # Cleanup
    if test_file.exists():
        test_file.unlink()

    return elapsed


def benchmark_json_read(file_size_kb: int, temp_dir: Path) -> float:
    """Measure JSON read performance."""
    test_file = temp_dir / "test.json"

    # Create test file
    test_data = {"data": "x" * (file_size_kb * 1024)}
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)

    # Benchmark
    start = time.perf_counter()
    with open(test_file, 'r', encoding='utf-8') as f:
        _ = json.load(f)
    elapsed = time.perf_counter() - start

    # Cleanup
    if test_file.exists():
        test_file.unlink()

    return elapsed


def benchmark_directory_scan(num_files: int, temp_dir: Path) -> float:
    """Measure directory scanning performance."""
    # Create test files
    for i in range(num_files):
        (temp_dir / f"file_{i}.txt").write_text(f"content {i}")

    # Benchmark glob pattern
    start = time.perf_counter()
    files = list(temp_dir.glob("*.txt"))
    elapsed = time.perf_counter() - start

    # Cleanup
    for f in files:
        if f.exists():
            f.unlink()

    return elapsed


def benchmark_file_exists_check(num_files: int, temp_dir: Path) -> float:
    """Measure file existence check performance."""
    # Create test files
    files = []
    for i in range(num_files):
        f = temp_dir / f"file_{i}.txt"
        f.write_text(f"content {i}")
        files.append(f)

    # Benchmark exists() calls
    start = time.perf_counter()
    for f in files:
        _ = f.exists()
    elapsed = time.perf_counter() - start

    # Cleanup
    for f in files:
        if f.exists():
            f.unlink()

    return elapsed


def benchmark_recursive_find_path(depth: int, temp_dir: Path) -> float:
    """Measure recursive find_path performance."""
    # Create nested directory structure
    current = temp_dir
    for i in range(depth):
        current = current / f"level_{i}"
        current.mkdir(parents=True, exist_ok=True)

    # Create target file at deepest level
    target_file = current / "target.txt"
    target_file.write_text("target")

    # Reset cache
    reset_find_path_cache()

    # Benchmark
    start = time.perf_counter()
    result = find_path("target.txt", parent_dir=temp_dir, max_depth=-1)
    elapsed = time.perf_counter() - start

    print(f"  Found: {result is not None}")

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    return elapsed


def main():
    """Run all I/O benchmarks."""
    print("=" * 60)
    print("I/O BENCHMARK")
    print("=" * 60)

    results = BenchmarkResults()

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)

        # Benchmark 1: find_path performance
        print("\n=== FIND_PATH PERFORMANCE ===")
        find_time = benchmark_find_path(temp_dir, num_searches=100)
        results.add("find_path (100 searches)", find_time)

        # Benchmark 2: JSON write atomic
        print("\n=== JSON WRITE ATOMIC ===")
        for size_kb in [10, 100, 500, 1000]:
            elapsed = benchmark_json_write_atomic(size_kb, temp_dir)
            print(f"  {size_kb:4} KB: {elapsed * 1000:8.2f} ms")
            results.add(f"JSON write ({size_kb} KB)", elapsed * 1000)

        # Benchmark 3: JSON read
        print("\n=== JSON READ ===")
        for size_kb in [10, 100, 500, 1000]:
            elapsed = benchmark_json_read(size_kb, temp_dir)
            print(f"  {size_kb:4} KB: {elapsed * 1000:8.2f} ms")
            results.add(f"JSON read ({size_kb} KB)", elapsed * 1000)

        # Benchmark 4: Directory scan
        print("\n=== DIRECTORY SCAN ===")
        for num_files in [10, 100, 500, 1000]:
            elapsed = benchmark_directory_scan(num_files, temp_dir)
            per_file = (elapsed / num_files) * 1000 if num_files > 0 else 0
            print(f"  {num_files:4} files: {elapsed * 1000:8.2f} ms ({per_file:.4f} ms/file)")
            results.add(f"Dir scan ({num_files} files)", elapsed * 1000)

        # Benchmark 5: File exists check
        print("\n=== FILE EXISTS CHECK ===")
        for num_files in [100, 500, 1000]:
            elapsed = benchmark_file_exists_check(num_files, temp_dir)
            per_check = (elapsed / num_files) * 1000
            print(f"  {num_files:4} checks: {elapsed * 1000:8.2f} ms ({per_check:.4f} ms/check)")
            results.add(f"Exists check ({num_files})", elapsed * 1000)

        # Benchmark 6: Recursive find_path
        print("\n=== RECURSIVE FIND_PATH ===")
        for depth in [3, 5, 10]:
            elapsed = benchmark_recursive_find_path(depth, Path(tmpdir) / f"depth_{depth}")
            print(f"  Depth {depth:2}: {elapsed * 1000:8.2f} ms")
            results.add(f"Find path (depth={depth})", elapsed * 1000)

    results.print_summary()


if __name__ == "__main__":
    main()
