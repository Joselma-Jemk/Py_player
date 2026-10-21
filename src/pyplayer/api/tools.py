"""Installation et mise à jour des outils externes (yt-dlp, ffmpeg) dans le dossier de données de PyPlayer.

Tout vient des versions officielles publiées sur GitHub, par des adresses stables ``releases/latest/download/…`` ; chaque
fichier est vérifié par sa somme SHA-256 publiée à côté (téléchargement refusé sinon). Rien n'est installé dans le
système : les outils vivent dans ``<données>/tools`` et se suppriment avec la réinitialisation.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import fetch
from .fetch import FetchError, FetchPolicy

logger = logging.getLogger(__name__)

YTDLP_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
YTDLP_SUMS = "SHA2-256SUMS"
FFMPEG_BASE = "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/"
FFMPEG_SUMS = "checksums.sha256"
MAX_BINARY = 200 * 1024 * 1024
MAX_FFMPEG_ARCHIVE = 450 * 1024 * 1024
Progress = Callable[[int, int], None]


def tools_dir() -> Path:
    from . import paths
    return paths.data_dir() / "tools"


def _system() -> tuple[str, str]:
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(platform.system(), "")
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else ("x86" if machine in ("i386", "i686", "x86") else "x64")
    return system, arch


def ytdlp_asset(system: str | None = None, arch: str | None = None) -> str | None:
    """Nom du fichier yt-dlp officiel pour ce système (``None`` si non pris en charge)."""
    sys_name, sys_arch = _system()
    system, arch = system or sys_name, arch or sys_arch
    table = {("windows", "x64"): "yt-dlp.exe", ("windows", "x86"): "yt-dlp_x86.exe",
             ("windows", "arm64"): "yt-dlp_arm64.exe", ("linux", "x64"): "yt-dlp_linux",
             ("linux", "arm64"): "yt-dlp_linux_aarch64", ("macos", "x64"): "yt-dlp_macos",
             ("macos", "arm64"): "yt-dlp_macos"}
    return table.get((system, arch))


def ffmpeg_asset(system: str | None = None, arch: str | None = None) -> str | None:
    sys_name, sys_arch = _system()
    system, arch = system or sys_name, arch or sys_arch
    table = {("windows", "x64"): "ffmpeg-master-latest-win64-gpl.zip",
             ("windows", "arm64"): "ffmpeg-master-latest-winarm64-gpl.zip",
             ("linux", "x64"): "ffmpeg-master-latest-linux64-gpl.tar.xz",
             ("linux", "arm64"): "ffmpeg-master-latest-linuxarm64-gpl.tar.xz"}
    return table.get((system, arch))


def ytdlp_path() -> Path:
    return tools_dir() / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")


def ffmpeg_folder() -> Path:
    return tools_dir() / "ffmpeg"


def ffmpeg_installed() -> bool:
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    return (ffmpeg_folder() / name).is_file()


@dataclass(frozen=True)
class ToolStatus:
    asset: str
    installed: bool
    up_to_date: bool | None            # None : impossible à savoir (hors ligne)
    detail: str = ""


def ytdlp_status(*, policy: FetchPolicy | None = None, base: str = YTDLP_BASE,
                 get_text: Callable[..., str] = fetch.get_text, asset: str | None = None) -> ToolStatus:
    """yt-dlp installé par PyPlayer est-il la dernière version ? (empreinte du fichier vs somme publiée)."""
    asset = asset or ytdlp_asset()
    if asset is None:
        return ToolStatus("", False, None, "Système non pris en charge pour l'installation automatique.")
    path = ytdlp_path()
    installed = path.is_file()
    try:
        sums = fetch.parse_sums(get_text(base + YTDLP_SUMS, policy or FetchPolicy()))
    except FetchError as error:
        return ToolStatus(asset, installed, None, str(error))
    expected = sums.get(asset)
    if expected is None:
        return ToolStatus(asset, installed, None, "Version introuvable dans la liste officielle.")
    if not installed:
        return ToolStatus(asset, False, False, "yt-dlp n'est pas installé.")
    return ToolStatus(asset, True, fetch.sha256_of(path) == expected)


def install_ytdlp(*, progress: Progress | None = None, cancelled: Callable[[], bool] | None = None,
                  policy: FetchPolicy | None = None, base: str = YTDLP_BASE, asset: str | None = None,
                  get_text: Callable[..., str] = fetch.get_text,
                  download: Callable[..., Path] = fetch.download_verified) -> Path:
    """Installe ou met à jour yt-dlp (fichier unique) ; l'ancien fichier reste tant que le nouveau n'est pas validé."""
    asset = asset or ytdlp_asset()
    if asset is None:
        raise FetchError("Installation automatique de yt-dlp non prise en charge sur ce système.")
    policy = policy or FetchPolicy()
    sums = fetch.parse_sums(get_text(base + YTDLP_SUMS, policy))
    expected = sums.get(asset)
    if not expected:
        raise FetchError("Somme de contrôle introuvable dans la liste officielle : installation refusée.")
    target = ytdlp_path()
    staged = target.with_name(target.name + ".new")
    download(base + asset, staged, expected, policy=policy, max_bytes=MAX_BINARY, progress=progress,
             cancelled=cancelled)
    try:
        if os.name != "nt":
            staged.chmod(staged.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(staged, target)
    except PermissionError as error:
        staged.unlink(missing_ok=True)
        raise FetchError("yt-dlp est en cours d'utilisation : arrêtez les téléchargements puis réessayez.") from error
    except OSError as error:
        staged.unlink(missing_ok=True)
        raise FetchError(f"Installation impossible : {error}") from error
    logger.info("yt-dlp installé : %s", target)
    return target


# ---------------------------------------------------------------------- ffmpeg
_WANTED = {"ffmpeg", "ffprobe"}


def _wanted_name(member_name: str) -> str | None:
    """Nom de fichier à extraire (« ffmpeg » ou « ffprobe », avec .exe sous Windows), sinon ``None``.
    Seul le dernier élément du chemin compte : jamais de chemin de l'archive utilisé pour écrire."""
    base = member_name.replace("\\", "/").rsplit("/", 1)[-1]
    stem = base[:-4] if base.lower().endswith(".exe") else base
    return base if stem in _WANTED else None


def extract_ffmpeg(archive: Path, destination: Path, max_member: int = 600 * 1024 * 1024) -> list[Path]:
    """Extrait uniquement ``ffmpeg`` et ``ffprobe`` d'une archive .zip ou .tar.xz, à plat dans ``destination``."""
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save(name: str, reader, size: int) -> None:
        if size > max_member:
            raise FetchError("Archive FFmpeg suspecte (fichier trop gros).")
        target = destination / name
        temp = target.with_name(target.name + ".new")
        with open(temp, "wb") as out:
            shutil.copyfileobj(reader, out, 1024 * 1024)
        if os.name != "nt":
            temp.chmod(0o755)
        os.replace(temp, target)
        written.append(target)

    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as bundle:
                for info in bundle.infolist():
                    name = _wanted_name(info.filename)
                    if name and not info.is_dir():
                        with bundle.open(info) as reader:
                            save(name, reader, info.file_size)
        else:
            with tarfile.open(archive, "r:*") as bundle:
                for member in bundle:
                    name = _wanted_name(member.name)
                    if name and member.isfile():                   # jamais de lien symbolique ni de périphérique
                        reader = bundle.extractfile(member)
                        if reader is not None:
                            save(name, reader, member.size)
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError) as error:
        raise FetchError(f"Archive FFmpeg illisible : {error}") from error
    if not any(p.stem == "ffmpeg" for p in written):
        raise FetchError("L'archive ne contient pas ffmpeg.")
    return written


def install_ffmpeg(*, progress: Progress | None = None, cancelled: Callable[[], bool] | None = None,
                   policy: FetchPolicy | None = None, base: str = FFMPEG_BASE, asset: str | None = None,
                   get_text: Callable[..., str] = fetch.get_text,
                   download: Callable[..., Path] = fetch.download_verified) -> Path:
    """Télécharge FFmpeg (≈ 100 Mo), vérifie la somme, extrait ``ffmpeg`` et ``ffprobe`` dans ``tools/ffmpeg``."""
    asset = asset or ffmpeg_asset()
    if asset is None:
        raise FetchError("Installation automatique de FFmpeg non prise en charge sur ce système.")
    policy = policy or FetchPolicy()
    expected = fetch.parse_sums(get_text(base + FFMPEG_SUMS, policy)).get(asset)
    if not expected:
        raise FetchError("Somme de contrôle introuvable dans la liste officielle : installation refusée.")
    with tempfile.TemporaryDirectory(prefix="pyplayer-ffmpeg-") as scratch:
        archive = Path(scratch) / asset
        download(base + asset, archive, expected, policy=policy, max_bytes=MAX_FFMPEG_ARCHIVE, progress=progress,
                 cancelled=cancelled)
        written = extract_ffmpeg(archive, ffmpeg_folder())
    logger.info("FFmpeg installé : %s", [p.name for p in written])
    return ffmpeg_folder()
