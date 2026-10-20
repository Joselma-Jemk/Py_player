"""Ligne de commande, lancement réel de l'application, instance unique et paquet installable."""

import os
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from pyplayer import __version__
from pyplayer.__main__ import _normalize, build_parser

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = shutil.which("ffmpeg")


def run_cli(*args, env=None, timeout=60):
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(ROOT / "src"), **(env or {})}
    return subprocess.run([sys.executable, "-m", "pyplayer", *args], capture_output=True, text=True,
                          timeout=timeout, env=environment)


# ----------------------------------------------------------------- analyse des arguments
def test_parser_accepts_files_flags_and_urls():
    args = build_parser().parse_args(["-a", "-n", "--fullscreen", "--debug", "a.mp4", "dir", "http://x/y.mp4"])
    assert args.enqueue and args.new_instance and args.fullscreen and args.debug
    assert args.files == ["a.mp4", "dir", "http://x/y.mp4"]
    assert build_parser().parse_args([]).files == []


def test_normalize_makes_paths_absolute_and_keeps_urls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = _normalize(["rel/video.mp4", "https://host/v.mp4", "rtsp://cam/1", "/abs/x.mkv"])
    assert out[0] == str(tmp_path / "rel" / "video.mp4")
    assert out[1:] == ["https://host/v.mp4", "rtsp://cam/1", os.path.abspath("/abs/x.mkv")]


def test_version_flag_prints_the_package_version():
    result = run_cli("--version")
    assert result.returncode == 0 and __version__ in result.stdout


def test_help_flag_documents_open_with_usage():
    result = run_cli("--help")
    assert result.returncode == 0
    for word in ("--enqueue", "--new-instance", "--fullscreen", "files"):
        assert word in result.stdout


def test_unknown_flag_is_rejected_cleanly():
    result = run_cli("--does-not-exist")
    assert result.returncode == 2 and "unrecognized arguments" in result.stderr


# ----------------------------------------------------------------- lancement réel
def start_app(home, *args, new_instance=False):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(ROOT / "src"),
           "PYPLAYER_HOME": str(home), "QT_LOGGING_RULES": "*=false"}
    command = [sys.executable, "-m", "pyplayer", "--debug", *(["-n"] if new_instance else []), *args]
    return subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def log_text(home):
    log = Path(home) / "pyplayer.log"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def wait_for(condition, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.1)
    return False


@pytest.mark.skipif(sys.platform.startswith("win"), reason="signaux POSIX")
def test_real_process_starts_opens_a_file_and_exits_cleanly(tmp_path):
    home = tmp_path / "home"
    media = tmp_path / "clip.mp4"
    if FFMPEG:
        subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x90:rate=10",
                        "-pix_fmt", "yuv420p", str(media)], check=True)
    else:
        media.write_bytes(b"x")
    process = start_app(home, str(media), new_instance=True)
    try:
        assert wait_for(lambda: "Ouverture demandée" in log_text(home)), (log_text(home), process.poll())
        assert process.poll() is None                                   # toujours en vie
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=20)
    finally:
        if process.poll() is None:
            process.kill()
    text = log_text(home)
    assert "Démarrage de PyPlayer" in text and "Traceback" not in text
    assert (home / "playlists").is_dir() and (home / "settings.json").exists() or process.returncode is not None


@pytest.mark.skipif(sys.platform.startswith("win"), reason="signaux POSIX")
def test_second_launch_hands_files_to_the_running_window_and_exits(tmp_path):
    """« Ouvrir avec… » ne doit jamais lancer une deuxième fenêtre."""
    home = tmp_path / "home"
    first = start_app(home)
    try:
        assert wait_for(lambda: "Démarrage de PyPlayer" in log_text(home))
        time.sleep(1.5)                                                  # laisse le serveur local démarrer
        target = tmp_path / "later.mp4"
        target.write_bytes(b"x")
        second = start_app(home, str(target))
        second.wait(timeout=30)
        assert second.returncode == 0                                    # la seconde instance s'est effacée
        assert wait_for(lambda: str(target) in log_text(home), 10), log_text(home)
        assert "Ouverture demandée" in log_text(home) and first.poll() is None
        assert "fichiers transmis" in log_text(home)
    finally:
        first.send_signal(signal.SIGTERM)
        try:
            first.wait(timeout=20)
        except subprocess.TimeoutExpired:
            first.kill()


# ----------------------------------------------------------------- paquet
def build_wheel(destination: Path) -> subprocess.CompletedProcess:
    """Construit la roue en environnement isolé (setuptools récent, comme en CI / chez l'utilisateur)."""
    result = subprocess.run([sys.executable, "-m", "pip", "wheel", str(ROOT), "--no-deps", "-w", str(destination), "-q"],
                            capture_output=True, text=True, timeout=600)
    if result.returncode != 0 and ("Could not find a version" in result.stderr or "Connection" in result.stderr
                                   or "No matching distribution" in result.stderr):
        pytest.skip("pas d'accès au réseau pour l'environnement de build isolé")
    return result


def test_wheel_contains_code_resources_and_entry_point(tmp_path):
    result = build_wheel(tmp_path)
    assert result.returncode == 0, result.stderr[-2000:]
    wheel = next(tmp_path.glob("pyplayer-*.whl"))
    assert __version__ in wheel.name
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert "pyplayer/__main__.py" in names and "pyplayer/api/playlist.py" in names and "pyplayer/ui/main_window.py" in names
        assert "pyplayer/resources/material-symbols-outlined.ttf" in names           # police d'icônes embarquée
        assert any(n.startswith("pyplayer/resources/icons/light/") and n.endswith("play.png") for n in names)
        assert "pyplayer/resources/icons/pyplayer_1.png" in names
        assert not any("test" in n.split("/")[0] for n in names)                      # pas de tests dans le paquet
        entry = archive.read(next(n for n in names if n.endswith("entry_points.txt"))).decode()
        assert "pyplayer = pyplayer.__main__:main" in entry


def test_installed_wheel_runs_from_a_clean_environment(tmp_path):
    wheels = tmp_path / "w"
    wheels.mkdir()
    build = build_wheel(wheels)
    assert build.returncode == 0, build.stderr[-1500:]
    target = tmp_path / "site"
    install = subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), "-q",
                              str(next(wheels.glob("*.whl")))], capture_output=True, text=True, timeout=300)
    assert install.returncode == 0, install.stderr[-1500:]
    env = {**os.environ, "PYTHONPATH": str(target), "QT_QPA_PLATFORM": "offscreen", "PYPLAYER_HOME": str(tmp_path / "h")}
    check = subprocess.run(
        [sys.executable, "-c",
         "import pyplayer, sys; from pyplayer.api import paths; "
         "assert str(paths.package_dir()).startswith(sys.argv[1]), paths.package_dir(); "
         "assert paths.font_path().is_file() and paths.app_icon_path().is_file() and paths.placeholder_icon_path().is_file(); "
         "print(pyplayer.__version__)", str(target)],
        capture_output=True, text=True, timeout=60, env=env, cwd=str(tmp_path))
    assert check.returncode == 0, check.stderr
    assert check.stdout.strip() == __version__
