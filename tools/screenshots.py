"""Génère les captures d'écran du README (``docs/assets/*.png``) avec de vrais médias de démonstration.

Usage : ``QT_QPA_PLATFORM=offscreen python tools/screenshots.py [dossier_de_sortie]``
Nécessite ``ffmpeg`` ; n'écrit jamais dans le vrai ``~/.pyplayer`` (dossier de données temporaire).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def make_video(path: Path, seconds: int = 20) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=25:duration={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(path)], check=True)


def pump(app, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


def grab_with_video(window, target: Path) -> None:
    """Capture la fenêtre ; hors écran Qt ne rend pas le flux vidéo dans ``grab()``, on y incruste la vraie image courante."""
    from PySide6 import QtCore, QtGui

    shot = window.grab().toImage()
    frame = window.player_widget.video_output.videoSink().videoFrame().toImage()
    if not frame.isNull():
        area = window.player_widget.video_output
        top_left = area.mapTo(window, QtCore.QPoint(0, 0))
        rect = QtCore.QRect(top_left, area.size())
        scaled = frame.scaled(rect.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                              QtCore.Qt.TransformationMode.SmoothTransformation)
        painter = QtGui.QPainter(shot)
        painter.fillRect(rect, QtGui.QColor("#000000"))
        painter.drawImage(rect.x() + (rect.width() - scaled.width()) // 2,
                          rect.y() + (rect.height() - scaled.height()) // 2, scaled)
        painter.end()
    shot.save(str(target))


def main() -> int:
    if shutil.which("ffmpeg") is None:
        print("ffmpeg est nécessaire pour générer les captures", file=sys.stderr)
        return 1
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="pp-shots-"))
    os.environ["PYPLAYER_HOME"] = str(work / "home")
    os.environ["PYPLAYER_NO_UPDATE_CHECK"] = "1"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from pyplayer.api import downloads as dl
    from pyplayer.ui.main_window import MainWindow

    app = QtWidgets.QApplication([])
    media = work / "media"
    media.mkdir()
    names = ["Documentaire - Épisode 1", "Documentaire - Épisode 2", "Documentaire - Épisode 3", "Concert en direct",
             "Voyage au Japon", "Tutoriel Python"]
    for name in names:
        make_video(media / f"{name}.mp4")

    window = MainWindow()
    window.resize(1180, 700)
    window.show()
    window.open_paths([str(media / f"{names[1]}.mp4")])
    window.open_paths([str(media / f"{n}.mp4") for n in names if n != names[1]], enqueue=True)
    pump(app, 2.5)
    window.player.setPosition(7000)
    pump(app, 1.5)
    grab_with_video(window, out_dir / "player.png")

    window.dock_widget.tab_widget.setCurrentWidget(window.downloads_panel)
    now = time.time()
    samples = [
        ("Conférence — Qt pour Python", dl.State.RUNNING, 0.62, 4_200_000, 38),
        ("Playlist « Musique » (3/12)", dl.State.RUNNING, 0.25, 1_800_000, 95),
        ("Documentaire nature 4K", dl.State.PAUSED, 0.41, 0, -1),
        ("Tutoriel Python", dl.State.DONE, 1.0, 0, -1),
        ("Concert en direct", dl.State.QUEUED, 0.0, 0, -1),
    ]
    for number, (title, state, fraction, speed, eta) in enumerate(samples):
        item = dl.DownloadItem(id=f"demo{number}", url=f"https://exemple.org/video{number}", out_dir=str(work),
                               options={}, title=title)
        item.state, item.progress, item.speed, item.eta = state, fraction, float(speed), eta
        item.total = 800_000_000
        item.downloaded = int(item.total * fraction)
        item.added_at = now + number
        window.downloads_panel.model.upsert(item)
    window.downloads_panel._refresh_summary()
    pump(app, 0.5)
    grab_with_video(window, out_dir / "downloads.png")

    window.dock_widget.tab_widget.setCurrentIndex(0)
    pump(app, 0.3)
    QtCore.QTimer.singleShot(400, lambda: [w.grab().save(str(out_dir / "media-info.png"))
                                           for w in app.topLevelWidgets()
                                           if w.isVisible() and w.__class__.__name__ == "MediaInfoDialog"]
                             + [w.close() for w in app.topLevelWidgets() if w.__class__.__name__ == "MediaInfoDialog"])
    window.show_media_info()

    window.close()
    shutil.rmtree(work, ignore_errors=True)
    print("captures écrites dans", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
