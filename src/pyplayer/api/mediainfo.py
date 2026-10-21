"""Informations détaillées sur un média (sans Qt) : fichier, conteneur, pistes vidéo/audio/sous-titres, chapitres, tags.

Source principale : ``ffprobe`` s'il est installé (le plus complet) ; les métadonnées lues par Qt sont fusionnées par
l'interface (``qt_section``). Tout est présenté en sections ``(titre, [(libellé, valeur)])`` prêtes à afficher.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .media import format_duration, format_size

PROBE_TIMEOUT_S = 12       # l'interface attend ce délai au plus (disque réseau lent)
HASH_CHUNK = 4 * 1024 * 1024

Rows = list[tuple[str, str]]


@dataclass
class InfoSection:
    title: str
    rows: Rows = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.rows)


# ---------------------------------------------------------------------- formats
def bitrate_text(value: Any) -> str:
    try:
        number = float(value)
        if not math.isfinite(number) or number > 1e15:
            return ""
        bits = int(number)
    except (TypeError, ValueError, OverflowError):
        return ""
    if bits <= 0:
        return ""
    return f"{bits / 1_000_000:.2f} Mb/s" if bits >= 1_000_000 else f"{bits // 1000} kb/s"


def fraction(value: Any) -> float:
    """« 30000/1001 » → 29.97 ; « 25 » → 25.0 ; invalide ou « 0/0 » → 0.0."""
    try:
        text = str(value)
        if "/" in text:
            num, den = text.split("/", 1)
            result = float(num) / float(den) if float(den) else 0.0
        else:
            result = float(text)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def seconds_text(value: Any) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError, OverflowError):
        return ""
    if not math.isfinite(seconds) or not 0 < seconds < 10 ** 9:       # au-delà de 30 ans : valeur absurde
        return ""
    return format_duration(int(seconds * 1000))


def date_text(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return ""


def _row(rows: Rows, label: str, value: Any) -> None:
    text = "" if value is None else str(value).strip()
    if text and text.lower() not in {"unknown", "n/a", "und"}:
        rows.append((label, text))


# ---------------------------------------------------------------------- fichier
def file_section(path: str | Path) -> InfoSection:
    path = Path(path)
    rows: Rows = []
    _row(rows, "Nom", path.name)
    _row(rows, "Dossier", path.parent)
    _row(rows, "Extension", path.suffix.lower().lstrip("."))
    try:
        stat = path.stat()
    except OSError:
        _row(rows, "État", "fichier introuvable")
        return InfoSection("Fichier", rows)
    _row(rows, "Taille", f"{format_size(stat.st_size)} ({stat.st_size:,} octets)".replace(",", " "))
    _row(rows, "Modifié le", date_text(stat.st_mtime))
    created = getattr(stat, "st_birthtime", None) or (stat.st_ctime if os.name == "nt" else None)
    _row(rows, "Créé le", date_text(created) if created else "")
    return InfoSection("Fichier", rows)


# ---------------------------------------------------------------------- ffprobe
def find_ffprobe() -> str | None:
    found = shutil.which("ffprobe")
    if found:
        return found
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if sibling.is_file():
            return str(sibling)
    return None


def probe(path: str | Path, *, runner: Callable[[list[str]], str] | None = None) -> dict[str, Any] | None:
    """Sortie JSON de ffprobe (format, flux, chapitres) ou ``None`` si ffprobe est absent ou échoue."""
    binary = find_ffprobe() if runner is None else "ffprobe"
    if binary is None:
        return None
    command = [binary, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", "-show_chapters",
               "--", str(path)]
    try:
        if runner is not None:
            output = runner(command)
        else:
            done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=PROBE_TIMEOUT_S, check=False,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if done.returncode != 0:
                return None
            output = done.stdout
        data = json.loads(output)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _tags(info: dict[str, Any]) -> dict[str, str]:
    tags = info.get("tags") or {}
    return {str(k).lower(): str(v) for k, v in tags.items()} if isinstance(tags, dict) else {}


def _video_rows(stream: dict[str, Any]) -> Rows:
    rows: Rows = []
    tags = _tags(stream)
    codec = stream.get("codec_long_name") or stream.get("codec_name")
    _row(rows, "Codec", f"{codec} ({stream.get('codec_name')})" if stream.get("codec_long_name") else codec)
    _row(rows, "Profil", stream.get("profile"))
    _row(rows, "Niveau", stream.get("level"))
    if stream.get("width") and stream.get("height"):
        _row(rows, "Résolution", f"{stream['width']}×{stream['height']}")
    _row(rows, "Format d'image", stream.get("display_aspect_ratio"))
    fps = fraction(stream.get("avg_frame_rate")) or fraction(stream.get("r_frame_rate"))
    _row(rows, "Images par seconde", f"{fps:.3f}".rstrip("0").rstrip(".") if fps else "")
    _row(rows, "Débit", bitrate_text(stream.get("bit_rate")) or bitrate_text(tags.get("bps")))
    _row(rows, "Format de pixel", stream.get("pix_fmt"))
    _row(rows, "Profondeur", f"{stream['bits_per_raw_sample']} bits" if stream.get("bits_per_raw_sample") else "")
    _row(rows, "Espace colorimétrique", stream.get("color_space"))
    _row(rows, "Plage de couleurs", stream.get("color_range"))
    _row(rows, "Transfert (HDR)", stream.get("color_transfer"))
    _row(rows, "Primaires", stream.get("color_primaries"))
    _row(rows, "Entrelacement", stream.get("field_order"))
    _row(rows, "Images", stream.get("nb_frames"))
    _row(rows, "Durée", seconds_text(stream.get("duration")))
    _row(rows, "Langue", tags.get("language"))
    _row(rows, "Titre de la piste", tags.get("title"))
    rotation = next((s.get("rotation") for s in stream.get("side_data_list") or [] if "rotation" in s), None)
    _row(rows, "Rotation", f"{rotation}°" if rotation else "")
    return rows


def _audio_rows(stream: dict[str, Any]) -> Rows:
    rows: Rows = []
    tags = _tags(stream)
    codec = stream.get("codec_long_name") or stream.get("codec_name")
    _row(rows, "Codec", f"{codec} ({stream.get('codec_name')})" if stream.get("codec_long_name") else codec)
    _row(rows, "Profil", stream.get("profile"))
    _row(rows, "Canaux", f"{stream['channels']} ({stream.get('channel_layout')})" if stream.get("channel_layout")
         else stream.get("channels"))
    _row(rows, "Fréquence", f"{stream['sample_rate']} Hz" if stream.get("sample_rate") else "")
    _row(rows, "Débit", bitrate_text(stream.get("bit_rate")) or bitrate_text(tags.get("bps")))
    _row(rows, "Profondeur", f"{stream['bits_per_sample']} bits" if stream.get("bits_per_sample") else "")
    _row(rows, "Durée", seconds_text(stream.get("duration")))
    _row(rows, "Langue", tags.get("language"))
    _row(rows, "Titre de la piste", tags.get("title"))
    disposition = stream.get("disposition") or {}
    _row(rows, "Par défaut", "oui" if disposition.get("default") else "")
    return rows


def _subtitle_rows(stream: dict[str, Any]) -> Rows:
    rows: Rows = []
    tags = _tags(stream)
    _row(rows, "Format", stream.get("codec_long_name") or stream.get("codec_name"))
    _row(rows, "Langue", tags.get("language"))
    _row(rows, "Titre de la piste", tags.get("title"))
    disposition = stream.get("disposition") or {}
    _row(rows, "Forcés", "oui" if disposition.get("forced") else "")
    _row(rows, "Malentendants", "oui" if disposition.get("hearing_impaired") else "")
    return rows


def sections_from_probe(data: dict[str, Any]) -> list[InfoSection]:
    """Sections détaillées à partir du JSON de ffprobe."""
    sections: list[InfoSection] = []
    fmt = data.get("format") if isinstance(data.get("format"), dict) else {}
    rows: Rows = []
    _row(rows, "Conteneur", fmt.get("format_long_name") or fmt.get("format_name"))
    _row(rows, "Durée", seconds_text(fmt.get("duration")))
    _row(rows, "Débit total", bitrate_text(fmt.get("bit_rate")))
    _row(rows, "Nombre de pistes", fmt.get("nb_streams"))
    sections.append(InfoSection("Conteneur", rows))

    raw_streams = data.get("streams")
    streams = [s for s in (raw_streams if isinstance(raw_streams, list) else []) if isinstance(s, dict)]
    for kind, title, builder in (("video", "Vidéo", _video_rows), ("audio", "Audio", _audio_rows),
                                 ("subtitle", "Sous-titres", _subtitle_rows)):
        found = [s for s in streams if s.get("codec_type") == kind
                 and not (kind == "video" and (s.get("disposition") or {}).get("attached_pic"))]
        for number, stream in enumerate(found, 1):
            label = title if len(found) == 1 else f"{title} {number}"
            sections.append(InfoSection(label, builder(stream)))

    raw_chapters = data.get("chapters")
    chapters = [c for c in (raw_chapters if isinstance(raw_chapters, list) else []) if isinstance(c, dict)]
    chapter_rows: Rows = []
    for number, chapter in enumerate(chapters, 1):
        start = seconds_text(chapter.get("start_time")) or "0:00"
        chapter_rows.append((start, _tags(chapter).get("title") or f"Chapitre {number}"))
    sections.append(InfoSection("Chapitres", chapter_rows))

    tag_rows = [(key.capitalize(), value) for key, value in sorted(_tags(fmt).items()) if value.strip()]
    sections.append(InfoSection("Métadonnées", tag_rows))
    return [s for s in sections if s]


def has_cover(data: dict[str, Any] | None) -> bool:
    streams = (data or {}).get("streams")
    return isinstance(streams, list) and any(
        isinstance(s, dict) and isinstance(s.get("disposition"), dict) and s["disposition"].get("attached_pic")
        for s in streams)


def qt_section(metadata: dict[str, str]) -> InfoSection:
    """Métadonnées lues par Qt (libellé → texte), sans doublons vides."""
    return InfoSection("Métadonnées Qt", [(k, v) for k, v in metadata.items() if v and str(v).strip()])


def merge(sections: list[InfoSection], extra: InfoSection) -> list[InfoSection]:
    """Ajoute ``extra`` en retirant les lignes déjà connues (même valeur) pour ne rien afficher deux fois."""
    known = {value for section in sections for _, value in section.rows}
    rows = [(k, v) for k, v in extra.rows if v not in known]
    return sections + ([InfoSection(extra.title, rows)] if rows else [])


# ---------------------------------------------------------------------- empreinte
def sha256_file(path: str | Path, *, progress: Callable[[int, int], None] | None = None,
                cancelled: Callable[[], bool] | None = None) -> str | None:
    """SHA-256 du fichier (par blocs ; ``None`` si annulé ou illisible)."""
    path = Path(path)
    try:
        total = path.stat().st_size
        digest = hashlib.sha256()
        done = 0
        with path.open("rb") as handle:
            while chunk := handle.read(HASH_CHUNK):
                if cancelled is not None and cancelled():
                    return None
                digest.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
        return digest.hexdigest()
    except OSError:
        return None


def to_text(title: str, sections: list[InfoSection]) -> str:
    """Rapport en texte brut (bouton « Copier »)."""
    lines = [title, "=" * len(title), ""]
    for section in sections:
        lines.append(f"[{section.title}]")
        lines.extend(f"{label}: {value}" for label, value in section.rows)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
