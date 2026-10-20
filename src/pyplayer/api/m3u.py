"""Import/export de playlists M3U/M3U8/PLS."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from .media import is_media


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _resolve(entry: str, base: Path) -> Path | None:
    entry = entry.strip().strip('"')
    if not entry or entry.startswith("#"):
        return None
    if entry.lower().startswith("file://"):
        parsed = urlparse(entry)
        if len(parsed.netloc) == 2 and parsed.netloc[1] == ":" and parsed.netloc[0].isalpha():
            entry = parsed.netloc + unquote(parsed.path)   # « file://C:/x » (mal formé mais courant)
        else:
            entry = unquote(parsed.path)
        if len(entry) > 2 and entry[0] == "/" and entry[2] == ":":  # file:///C:/...
            entry = entry[1:]
    elif "://" in entry:
        return None  # flux réseau : non géré par les playlists locales
    candidate = Path(entry.replace("\\", "/")) if "\\" in entry and not Path(entry).exists() else Path(entry)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate


def read_playlist_file(path: str | Path) -> tuple[str, list[Path]]:
    """Retourne ``(nom, chemins de médias existants)`` d'un fichier .m3u/.m3u8/.pls."""
    file_path = Path(path)
    text = _read_text(file_path)
    base = file_path.parent
    entries: list[str] = []

    if file_path.suffix.lower() == ".pls":
        for line in text.splitlines():
            key, _, value = line.partition("=")
            if key.strip().lower().startswith("file") and value:
                entries.append(value)
    else:
        entries = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]

    paths: list[Path] = []
    for entry in entries:
        resolved = _resolve(entry, base)
        if resolved and is_media(resolved) and resolved.is_file():
            paths.append(resolved)
    return file_path.stem, paths


def write_m3u(paths: Iterable[tuple[Path, str, int]], destination: str | Path) -> None:
    """Écrit un M3U8 (UTF-8) à partir de ``(chemin, titre, durée en ms)``."""
    lines = ["#EXTM3U"]
    for path, title, duration_ms in paths:
        seconds = int(duration_ms // 1000) if duration_ms > 0 else -1
        lines.append(f"#EXTINF:{seconds},{title}")
        lines.append(str(path))
    Path(destination).write_text("\n".join(lines) + "\n", encoding="utf-8")
