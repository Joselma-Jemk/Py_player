"""Types de médias, tri naturel, parcours de dossiers et formatage."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Iterator

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".m4v", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv", ".mpeg", ".mpg", ".mpe",
    ".ts", ".m2ts", ".mts", ".3gp", ".ogv", ".vob", ".asf", ".divx",
})
AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".oga", ".opus", ".m4a", ".wma",
})
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
PLAYLIST_FILE_EXTENSIONS = frozenset({".m3u", ".m3u8", ".pls"})

_DIGITS = re.compile(r"(\d+)")


def is_media(path: str | os.PathLike[str]) -> bool:
    return Path(path).suffix.lower() in MEDIA_EXTENSIONS


def is_audio(path: str | os.PathLike[str]) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTENSIONS


def is_playlist_file(path: str | os.PathLike[str]) -> bool:
    return Path(path).suffix.lower() in PLAYLIST_FILE_EXTENSIONS


def path_key(path: str | os.PathLike[str]) -> str:
    """Clé d'identité d'un fichier (absolue, normalisée, insensible à la casse sous Windows)."""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def natural_key(text: str) -> list[object]:
    """Clé de tri naturel : « ep2 » avant « ep10 ». Alterne toujours str (indices pairs) / int (indices impairs).

    ``re.split`` avec un groupe capturant alterne strictement texte et chiffres : on s'appuie sur
    cette position plutôt que sur ``str.isdigit()``, qui est vrai pour « ² » alors que ``int("²")`` échoue.
    """
    parts = _DIGITS.split(text)
    return [int(part) if i % 2 else part.casefold() for i, part in enumerate(parts)]


def natural_path_key(path: Path, root: Path | None = None) -> tuple[list[object], ...]:
    """Tri naturel composant par composant (dossiers puis fichiers dans l'ordre alphabétique)."""
    relative = path
    if root is not None:
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = path
    return tuple(natural_key(part) for part in relative.parts)


def iter_media(root: str | os.PathLike[str], *, recursive: bool = True,
               include_hidden: bool = False) -> Iterator[Path]:
    """Parcourt un dossier et produit les médias trouvés (ordre non garanti). Tolère erreurs d'accès et boucles de liens."""
    visited: set[str] = set()
    stack: list[Path] = [Path(root)]

    while stack:
        current = stack.pop()
        try:
            real = os.path.realpath(current)
            if real in visited:
                continue
            visited.add(real)
            with os.scandir(current) as entries:
                for entry in entries:
                    if not include_hidden and entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=True):
                            if recursive:
                                stack.append(Path(entry.path))
                        elif entry.is_file() and is_media(entry.name):
                            yield Path(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue


def scan_folder(root: str | os.PathLike[str], *, recursive: bool = True,
                include_hidden: bool = False) -> list[Path]:
    """Liste les médias d'un dossier, triés naturellement."""
    root_path = Path(root)
    found = list(iter_media(root_path, recursive=recursive, include_hidden=include_hidden))
    found.sort(key=lambda p: natural_path_key(p, root_path))
    return found


def count_media(root: str | os.PathLike[str], *, limit: int = 5000) -> tuple[int, bool]:
    """Compte les médias d'un dossier (arrêt à ``limit``). Retourne ``(nombre, tronqué)``."""
    count = 0
    for _ in iter_media(root):
        count += 1
        if count >= limit:
            return count, True
    return count, False


def sibling_media(path: str | os.PathLike[str]) -> list[Path]:
    """Médias du même dossier que ``path`` (non récursif), triés naturellement."""
    return scan_folder(Path(path).parent, recursive=False)


def format_duration(milliseconds: int) -> str:
    """``65000`` → ``1:05`` ; ``3_725_000`` → ``1:02:05``."""
    total = max(0, int(milliseconds)) // 1000
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if value < 1024 or unit == "To":
            return f"{int(value)} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} To"


def unique_paths(paths: Iterable[Path]) -> Iterator[Path]:
    seen: set[str] = set()
    for path in paths:
        key = path_key(path)
        if key not in seen:
            seen.add(key)
            yield path
