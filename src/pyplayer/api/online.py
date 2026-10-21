"""Lecture en ligne : transforme une adresse de page (YouTube, etc.) en adresse de flux lisible, via yt-dlp.

Sans Qt. Trois façons d'obtenir yt-dlp, par ordre de priorité :
  1. un exécutable placé dans le dossier de données de PyPlayer (mis à jour par l'application) ;
  2. un ``yt-dlp`` trouvé dans le ``PATH`` ;
  3. le module Python ``yt_dlp`` (embarqué dans les binaires, ou installé avec ``pip install pyplayer[online]``).

Le lecteur ne sait lire qu'UN flux : on demande donc des formats « combinés » (vidéo + audio dans le même flux),
en général jusqu'à 720p. Les sites n'offrant que des flux séparés ne sont pas lisibles ainsi.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from . import paths
from .media import MEDIA_EXTENSIONS

logger = logging.getLogger(__name__)

MAX_URL_LENGTH = 2048
RESOLVE_TIMEOUT_S = 45
# Un seul flux, avec image ET son ; HLS accepté ; repli sur le meilleur format unique.
FORMAT_SELECTOR = "best[protocol^=http][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/best"
STREAM_SUFFIXES = {".m3u8", ".mpd", ".pls", ".m3u"}
DIRECT_SCHEMES = {"rtsp", "rtmp", "rtp", "udp", "mms", "mmsh"}


class OnlineError(Exception):
    """Échec de résolution, avec un message lisible par l'utilisateur."""


@dataclass(frozen=True)
class OnlineMedia:
    page_url: str
    stream_url: str
    title: str
    duration_ms: int = 0
    uploader: str = ""
    is_live: bool = False
    has_video: bool = True
    extractor: str = ""
    headers: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------- adresses
def clean_url(text: str) -> str:
    """Adresse nettoyée et validée (http/https, pas d'option déguisée, pas de caractère de contrôle)."""
    url = (text or "").strip()
    if not url or len(url) > MAX_URL_LENGTH or any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise OnlineError("Adresse invalide.")
    if url.startswith("-"):
        raise OnlineError("Adresse invalide.")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise OnlineError("Seules les adresses http(s) sont prises en charge ici.")
    return url


def is_web_url(text: str) -> bool:
    try:
        clean_url(text)
        return True
    except OnlineError:
        return False


def is_direct_stream(text: str) -> bool:
    """Vrai si l'adresse est déjà un média/flux lisible tel quel (fichier, HLS, rtsp…) : pas besoin de yt-dlp."""
    parsed = urlparse((text or "").strip())
    if parsed.scheme.lower() in DIRECT_SCHEMES:
        return True
    suffix = Path(parsed.path).suffix.lower()
    return suffix in MEDIA_EXTENSIONS or suffix in STREAM_SUFFIXES


# ---------------------------------------------------------------------- lecture du résultat de yt-dlp
def _pick_format(info: dict[str, Any]) -> dict[str, Any]:
    """Format unique à lire : celui choisi par yt-dlp si c'est un seul flux, sinon le meilleur format combiné."""
    requested = info.get("requested_formats")
    if requested and len(requested) > 1:
        # yt-dlp a choisi deux flux séparés (vidéo + audio) : le lecteur n'en lit qu'un, on revient aux formats combinés.
        info = {**info, "requested_formats": None}
    if info.get("url") and not info.get("requested_formats"):
        return info
    combined = [f for f in info.get("formats") or []
                if f.get("url") and f.get("vcodec") not in (None, "none") and f.get("acodec") not in (None, "none")]
    if combined:
        return max(combined, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
    audio = [f for f in info.get("formats") or [] if f.get("url") and f.get("acodec") not in (None, "none")]
    if audio:
        return max(audio, key=lambda f: f.get("abr") or f.get("tbr") or 0)
    raise OnlineError("Aucun flux lisible directement (ce site ne propose que des flux séparés).")


def parse_info(info: dict[str, Any], page_url: str = "") -> OnlineMedia:
    """Transforme le JSON de yt-dlp (``extract_info`` / ``-J``) en :class:`OnlineMedia`."""
    if not isinstance(info, dict):
        raise OnlineError("Réponse inattendue de yt-dlp.")
    if info.get("_type") == "playlist" or (info.get("entries") and not info.get("url")):
        entries = [e for e in info.get("entries") or [] if isinstance(e, dict)]
        if not entries:
            raise OnlineError("Cette adresse ne contient aucune vidéo.")
        info = entries[0]
    chosen = _pick_format(info)
    stream = chosen.get("url")
    if not isinstance(stream, str) or not stream.startswith(("http://", "https://")):
        raise OnlineError("yt-dlp n'a pas fourni d'adresse de flux utilisable.")
    duration = info.get("duration")
    vcodec = chosen.get("vcodec")
    return OnlineMedia(
        page_url=page_url or str(info.get("webpage_url") or ""),
        stream_url=stream,
        title=str(info.get("title") or info.get("fulltitle") or urlparse(page_url).netloc or "Flux en ligne"),
        duration_ms=int(float(duration) * 1000) if isinstance(duration, (int, float)) and duration > 0 else 0,
        uploader=str(info.get("uploader") or info.get("channel") or ""),
        is_live=bool(info.get("is_live")),
        has_video=vcodec not in ("none",),
        extractor=str(info.get("extractor_key") or info.get("extractor") or ""),
        headers={str(k): str(v) for k, v in (chosen.get("http_headers") or {}).items()},
    )


# ---------------------------------------------------------------------- sources de yt-dlp
def user_binary_path() -> Path:
    name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
    return paths.data_dir() / "tools" / name


def find_binary() -> Path | None:
    """Exécutable yt-dlp à utiliser (celui mis à jour par PyPlayer d'abord, puis celui du système)."""
    own = user_binary_path()
    if own.is_file():
        return own
    found = shutil.which("yt-dlp")
    return Path(found) if found else None


def module_available() -> bool:
    return importlib.util.find_spec("yt_dlp") is not None


def available() -> bool:
    return find_binary() is not None or module_available()


def _extract_with_module(url: str) -> dict[str, Any]:
    import yt_dlp
    options = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True,
               "format": FORMAT_SELECTOR, "socket_timeout": 20, "retries": 1, "extractor_retries": 1,
               "check_formats": False, "cachedir": False}
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.sanitize_info(ydl.extract_info(url, download=False))


def _extract_with_binary(binary: Path, url: str, timeout: int) -> dict[str, Any]:
    command = [str(binary), "-J", "--no-playlist", "--no-warnings", "--no-cache-dir", "--socket-timeout", "20",
               "-f", FORMAT_SELECTOR, "--", url]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)                # pas de fenêtre de console sous Windows
    try:
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, creationflags=flags, check=False)
    except subprocess.TimeoutExpired as error:
        raise OnlineError("Délai dépassé en cherchant le flux.") from error
    except OSError as error:
        raise OnlineError(f"yt-dlp ne peut pas être lancé : {error}") from error
    if done.returncode != 0:
        raise OnlineError(_friendly_error(done.stderr))
    try:
        return json.loads(done.stdout)
    except ValueError as error:
        raise OnlineError("Réponse illisible de yt-dlp.") from error


def _friendly_error(message: str) -> str:
    """Dernière ligne utile de l'erreur de yt-dlp, sans préfixe technique."""
    lines = [line.strip() for line in (message or "").splitlines() if line.strip()]
    text = next((line for line in reversed(lines) if line.startswith("ERROR")), lines[-1] if lines else "")
    text = text.removeprefix("ERROR:").strip()
    return text[:300] or "yt-dlp n'a pas pu lire cette adresse."


Extractor = Callable[[str], dict[str, Any]]


def resolve(url: str, *, extractor: Extractor | None = None, timeout: int = RESOLVE_TIMEOUT_S) -> OnlineMedia:
    """Adresse de page → flux lisible. ``extractor`` (tests) remplace yt-dlp."""
    page = clean_url(url)
    if extractor is not None:
        return parse_info(extractor(page), page)
    binary = find_binary()
    try:
        if binary is not None:
            info = _extract_with_binary(binary, page, timeout)
        elif module_available():
            info = _extract_with_module(page)
        else:
            raise OnlineError("yt-dlp n'est pas installé : Support → Mettre à jour yt-dlp, "
                              "ou installez-le (pip install yt-dlp).")
    except OnlineError:
        raise
    except Exception as error:  # noqa: BLE001 -- yt_dlp lève des types variés (DownloadError, ExtractorError…)
        raise OnlineError(_friendly_error(str(error))) from error
    return parse_info(info, page)


def version() -> str:
    """Version de yt-dlp réellement utilisée (vide si indisponible)."""
    binary = find_binary()
    if binary is not None:
        try:
            done = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=15,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
            return done.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return ""
    try:
        from yt_dlp.version import __version__
        return str(__version__)
    except ImportError:
        return ""


__all__ = ["OnlineError", "OnlineMedia", "clean_url", "is_web_url", "is_direct_stream", "parse_info", "resolve",
           "available", "find_binary", "module_available", "user_binary_path", "version"]
