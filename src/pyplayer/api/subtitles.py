"""Sous-titres externes (.srt / .vtt) : Qt Multimedia ne charge que les pistes intégrées."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from pathlib import Path

_TIME = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_TAGS = re.compile(r"<[^>]+>|\{\\[^}]*\}")


@dataclass(frozen=True)
class Cue:
    start: int  # ms
    end: int
    text: str


def _ms(hours: str | None, minutes: str, seconds: str, millis: str) -> int:
    return ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis.ljust(3, "0"))


def parse_subtitles(text: str) -> list[Cue]:
    """Analyse du contenu SRT ou WebVTT. Les blocs invalides sont ignorés."""
    cues: list[Cue] = []
    for block in re.split(r"\r?\n\s*\r?\n", text.replace("﻿", "").strip()):
        lines = [line for line in block.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            match = _TIME.search(line)
            if match:
                g = match.groups()
                body = _TAGS.sub("", "\n".join(lines[i + 1:])).strip()
                if body:
                    cues.append(Cue(_ms(g[0], g[1], g[2], g[3]), _ms(g[4], g[5], g[6], g[7]), body))
                break
    cues.sort(key=lambda c: c.start)
    return cues


def load_subtitle_file(path: str | Path) -> list[Cue]:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return parse_subtitles(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    return []


class SubtitleTrack:
    """Accès rapide au sous-titre affiché à un instant donné."""

    def __init__(self, cues: list[Cue], source: str = "") -> None:
        self.cues = sorted(cues, key=lambda c: c.start)
        self.source = source
        self._starts = [c.start for c in self.cues]
        # Fin maximale des cues 0..i : permet de savoir quand arrêter de remonter, même si les sous-titres se chevauchent.
        self._max_end: list[int] = []
        running = -1
        for cue in self.cues:
            running = max(running, cue.end)
            self._max_end.append(running)
        self.delay = 0  # ms ; positif = sous-titres plus tard

    def text_at(self, position_ms: int) -> str:
        """Texte affiché à l'instant donné (exact, même avec des sous-titres qui se chevauchent).

        Parmi plusieurs sous-titres actifs, le dernier démarré l'emporte.
        """
        t = position_ms - self.delay
        i = bisect.bisect_right(self._starts, t) - 1
        while i >= 0 and self._max_end[i] > t:
            cue = self.cues[i]
            if cue.start <= t < cue.end:
                return cue.text
            i -= 1
        return ""


def find_sidecar(media_path: str | Path) -> Path | None:
    """Fichier de sous-titres du même nom que la vidéo (``film.mkv`` → ``film.srt``, ``film.fr.srt``…)."""
    media = Path(media_path)
    try:
        candidates = sorted(media.parent.iterdir())
    except OSError:
        return None
    for suffix in (".srt", ".vtt"):
        for candidate in candidates:
            if candidate.suffix.lower() == suffix and candidate.name.startswith(media.stem):
                return candidate
    return None
