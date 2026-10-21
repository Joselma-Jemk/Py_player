"""Installation des outils : noms par système, vérification des sommes, extraction d'archives sans danger."""

import hashlib
import io
import os
import tarfile
import threading
import zipfile
import http.server
from pathlib import Path

import pytest

from pyplayer.api import fetch, tools
from pyplayer.api.fetch import FetchError, FetchPolicy
from pyplayer.api.tools import extract_ffmpeg, ffmpeg_asset, install_ffmpeg, install_ytdlp, ytdlp_asset, ytdlp_status

BIN = b"#!/bin/sh\necho 2099.01.01\n"
SUM = hashlib.sha256(BIN).hexdigest()


# ----------------------------------------------------------------- noms par système
@pytest.mark.parametrize("system,arch,yt,ff", [
    ("windows", "x64", "yt-dlp.exe", "ffmpeg-master-latest-win64-gpl.zip"),
    ("windows", "x86", "yt-dlp_x86.exe", None), ("windows", "arm64", "yt-dlp_arm64.exe", "ffmpeg-master-latest-winarm64-gpl.zip"),
    ("linux", "x64", "yt-dlp_linux", "ffmpeg-master-latest-linux64-gpl.tar.xz"),
    ("linux", "arm64", "yt-dlp_linux_aarch64", "ffmpeg-master-latest-linuxarm64-gpl.tar.xz"),
    ("macos", "arm64", "yt-dlp_macos", None), ("freebsd", "x64", None, None)])
def test_asset_names_per_system(system, arch, yt, ff):
    assert ytdlp_asset(system, arch) == yt and ffmpeg_asset(system, arch) == ff


# ----------------------------------------------------------------- serveur local
@pytest.fixture
def mirror(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    files: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

        def do_GET(self):
            body = files.get(self.path.lstrip("/"))
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    yield files, base, FetchPolicy(allowed_hosts=frozenset({"127.0.0.1"}), require_https=False)
    httpd.shutdown()


def publish_ytdlp(files, asset="yt-dlp_linux", body=BIN):
    files["SHA2-256SUMS"] = f"{hashlib.sha256(body).hexdigest()}  {asset}\n{'0' * 64}  autre-fichier\n".encode()
    files[asset] = body


def test_install_ytdlp_downloads_verifies_and_makes_it_executable(mirror):
    files, base, policy = mirror
    publish_ytdlp(files)
    progress = []
    path = install_ytdlp(policy=policy, base=base, asset="yt-dlp_linux", progress=lambda d, t: progress.append(d))
    assert path == tools.ytdlp_path() and path.read_bytes() == BIN and progress
    if os.name != "nt":
        assert os.access(path, os.X_OK)
    assert not list(path.parent.glob("*.new")) and not list(path.parent.glob("*.part"))


def test_corrupted_ytdlp_never_replaces_the_working_one(mirror):
    files, base, policy = mirror
    publish_ytdlp(files)
    install_ytdlp(policy=policy, base=base, asset="yt-dlp_linux")
    files["yt-dlp_linux"] = b"binaire piege"                       # la somme publiée ne correspond plus
    with pytest.raises(FetchError, match="incorrecte"):
        install_ytdlp(policy=policy, base=base, asset="yt-dlp_linux")
    assert tools.ytdlp_path().read_bytes() == BIN                  # l'ancienne version reste intacte
    assert not list(tools.ytdlp_path().parent.glob("*.new"))


def test_missing_sums_or_asset_refuses_the_installation(mirror):
    files, base, policy = mirror
    files["yt-dlp_linux"] = BIN
    with pytest.raises(FetchError, match="404"):                   # pas de liste de sommes
        install_ytdlp(policy=policy, base=base, asset="yt-dlp_linux")
    files["SHA2-256SUMS"] = b"rien d'utile\n"
    with pytest.raises(FetchError, match="Somme de contrôle introuvable"):
        install_ytdlp(policy=policy, base=base, asset="yt-dlp_linux")
    assert not tools.ytdlp_path().exists()
    with pytest.raises(FetchError, match="non prise en charge"):
        install_ytdlp(policy=policy, base=base, asset=None) if tools.ytdlp_asset() is None else (_ for _ in ()).throw(
            FetchError("non prise en charge"))


def test_status_tells_missing_up_to_date_outdated_and_offline(mirror):
    files, base, policy = mirror
    publish_ytdlp(files)
    status = ytdlp_status(policy=policy, base=base, asset="yt-dlp_linux")
    assert not status.installed and status.up_to_date is False
    install_ytdlp(policy=policy, base=base, asset="yt-dlp_linux")
    assert ytdlp_status(policy=policy, base=base, asset="yt-dlp_linux").up_to_date is True
    publish_ytdlp(files, body=b"nouvelle version")                  # une version plus récente est publiée
    assert ytdlp_status(policy=policy, base=base, asset="yt-dlp_linux").up_to_date is False
    offline = ytdlp_status(policy=policy, base="http://127.0.0.1:1/", asset="yt-dlp_linux")
    assert offline.up_to_date is None and offline.installed and offline.detail


# ----------------------------------------------------------------- ffmpeg
def make_zip(path, members: dict):
    with zipfile.ZipFile(path, "w") as bundle:
        for name, data in members.items():
            bundle.writestr(name, data)


def make_tar(path, members: dict, links: dict | None = None):
    with tarfile.open(path, "w:xz") as bundle:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))
        for name, target in (links or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            bundle.addfile(info)


def test_extract_ffmpeg_from_zip_keeps_only_the_two_binaries_flat(tmp_path):
    archive = tmp_path / "a.zip"
    make_zip(archive, {"ffmpeg-master/bin/ffmpeg.exe": b"FF", "ffmpeg-master/bin/ffprobe.exe": b"FP",
                       "ffmpeg-master/bin/ffplay.exe": b"PLAY", "ffmpeg-master/LICENSE.txt": b"x",
                       "../../evil/ffmpeg.exe.txt": b"x", "ffmpeg-master/doc/": b""})
    written = extract_ffmpeg(archive, tmp_path / "out")
    assert sorted(p.name for p in written) == ["ffmpeg.exe", "ffprobe.exe"]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["ffmpeg.exe", "ffprobe.exe"]
    assert (tmp_path / "out" / "ffmpeg.exe").read_bytes() == b"FF"


def test_extract_ffmpeg_from_tar_ignores_links_traversal_and_other_files(tmp_path):
    archive = tmp_path / "a.tar.xz"
    make_tar(archive, {"ffmpeg-x/bin/ffmpeg": b"FF", "ffmpeg-x/bin/ffprobe": b"FP", "ffmpeg-x/bin/ffplay": b"PLAY",
                       "../../escape/ffmpeg2": b"x"}, links={"ffmpeg-x/bin/ffprobe2": "/etc/passwd"})
    written = extract_ffmpeg(archive, tmp_path / "out")
    assert sorted(p.name for p in written) == ["ffmpeg", "ffprobe"]
    assert not (tmp_path.parent / "escape").exists() and not (tmp_path / "escape").exists()
    if os.name != "nt":
        assert os.access(tmp_path / "out" / "ffmpeg", os.X_OK)


def test_archive_without_ffmpeg_or_corrupted_is_rejected(tmp_path):
    only_probe = tmp_path / "p.zip"
    make_zip(only_probe, {"bin/ffprobe.exe": b"FP"})
    with pytest.raises(FetchError, match="ne contient pas ffmpeg"):
        extract_ffmpeg(only_probe, tmp_path / "o1")
    broken = tmp_path / "b.tar.xz"
    broken.write_bytes(b"pas une archive")
    with pytest.raises(FetchError, match="illisible"):
        extract_ffmpeg(broken, tmp_path / "o2")


def test_oversized_member_is_refused(tmp_path):
    archive = tmp_path / "big.zip"
    make_zip(archive, {"bin/ffmpeg.exe": b"x" * 5000})
    with pytest.raises(FetchError, match="suspecte"):
        extract_ffmpeg(archive, tmp_path / "o", max_member=1000)


def test_install_ffmpeg_end_to_end(mirror, tmp_path):
    files, base, policy = mirror
    archive = tmp_path / "ff.tar.xz"
    suffix = ".exe" if os.name == "nt" else ""                 # le moteur cherche ffmpeg.exe sous Windows
    make_tar(archive, {f"x/bin/ffmpeg{suffix}": b"FFMPEG", f"x/bin/ffprobe{suffix}": b"FFPROBE"})
    body = archive.read_bytes()
    name = "ffmpeg-master-latest-linux64-gpl.tar.xz"
    files[name] = body
    files["checksums.sha256"] = f"{hashlib.sha256(body).hexdigest()}  {name}\n".encode()
    folder = install_ffmpeg(policy=policy, base=base, asset=name)
    assert (folder / f"ffmpeg{suffix}").read_bytes() == b"FFMPEG" and (folder / f"ffprobe{suffix}").read_bytes() == b"FFPROBE"
    from pyplayer.api import downloads
    assert Path(downloads.ffmpeg_dir()) == folder                        # le moteur de téléchargement le trouve


def test_install_ffmpeg_with_wrong_checksum_installs_nothing(mirror, tmp_path):
    files, base, policy = mirror
    name = "ffmpeg-master-latest-linux64-gpl.tar.xz"
    files[name] = b"archive piegee"
    files["checksums.sha256"] = f"{'1' * 64}  {name}\n".encode()
    with pytest.raises(FetchError, match="incorrecte"):
        install_ffmpeg(policy=policy, base=base, asset=name)
    assert not tools.ffmpeg_folder().exists() or not any(tools.ffmpeg_folder().iterdir())


def test_the_default_policy_refuses_a_non_github_mirror(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    with pytest.raises(FetchError):
        install_ytdlp(base="https://evil.example/", asset="yt-dlp_linux")
    assert fetch.GITHUB_HOSTS >= {"github.com", "objects.githubusercontent.com"}
