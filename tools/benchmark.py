"""Mesures de performance reproductibles de PyPlayer (hors écran) : mémoire, CPU pendant la lecture, grandes playlists.

    python tools/benchmark.py            # affiche un rapport lisible
    python tools/benchmark.py --json     # même chose en JSON (pour comparer avant/après)

Les chiffres de mémoire sont le « RSS » du processus (mémoire réellement occupée), lu dans /proc sous Linux.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def rss_mb() -> float:
    try:
        with open("/proc/self/status", encoding="utf-8") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def pump(app, seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.002)


def make_video(folder: Path, seconds: int = 20) -> Path:
    path = folder / "bench.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"testsrc2=duration={seconds}:size=1280x720:rate=30", "-f", "lavfi", "-i", "sine=duration=" + str(seconds),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--items", type=int, default=20_000)
    args = parser.parse_args()
    report: dict[str, float] = {}
    workdir = Path(tempfile.mkdtemp(prefix="pyp-bench-"))
    os.environ["PYPLAYER_HOME"] = str(workdir / "home")
    try:
        report["rss_python_mb"] = round(rss_mb(), 1)
        started = time.perf_counter()
        from PySide6 import QtWidgets
        app = QtWidgets.QApplication([])
        from pyplayer.ui.main_window import MainWindow
        report["import_s"] = round(time.perf_counter() - started, 2)
        report["rss_after_import_mb"] = round(rss_mb(), 1)

        started = time.perf_counter()
        window = MainWindow()
        window.resize(1100, 700)
        window.show()
        pump(app, 0.5)
        report["window_build_s"] = round(time.perf_counter() - started - 0.5, 2)
        report["rss_idle_window_mb"] = round(rss_mb(), 1)

        # --- lecture : CPU du processus pendant 6 s d'une vidéo 720p30 (décodage logiciel inclus) -------------
        video = make_video(workdir)
        window.set_speed(1.0)
        ticks = []
        window.player.positionChanged.connect(lambda p: ticks.append(p))
        window.open_paths([str(video)])
        pump(app, 1.5)
        cpu_start, wall_start = time.process_time(), time.perf_counter()
        ticks.clear()
        pump(app, 6.0)
        cpu, wall = time.process_time() - cpu_start, time.perf_counter() - wall_start
        report["play_cpu_percent"] = round(100 * cpu / wall, 1)
        report["position_signals_per_s"] = round(len(ticks) / wall, 1)
        report["rss_playing_mb"] = round(rss_mb(), 1)

        # --- même chose, mais SANS décodage lourd : coût de l'interface seule (média audio) -----------------
        window.stop_playing()
        pump(app, 0.3)

        # --- grosse playlist --------------------------------------------------------------------------------
        folder = workdir / "lib"
        folder.mkdir()
        for index in range(args.items):
            (folder / f"Episode {index:05d} - un titre assez long pour être réaliste.mp4").write_bytes(b"x")
        before = rss_mb()
        started = time.perf_counter()
        window.open_paths([str(folder)], enqueue=True)
        pump(app, 0.2)
        report["playlist_add_s"] = round(time.perf_counter() - started, 2)
        report["playlist_items"] = args.items
        report["rss_per_1000_items_mb"] = round((rss_mb() - before) / (args.items / 1000), 2)
        started = time.perf_counter()
        window.refresh_playlist_view()
        pump(app, 0.2)
        report["playlist_refresh_s"] = round(time.perf_counter() - started, 2)
        report["rss_big_playlist_mb"] = round(rss_mb(), 1)

        window.close()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        width = max(len(k) for k in report)
        for key, value in report.items():
            print(f"{key:<{width}}  {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
