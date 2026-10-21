"""Chasse aux liens (sans Qt) : extrait les adresses d'un texte et décide lesquelles valent une proposition.

Utilisé pour le presse-papiers (« lien détecté : télécharger ? ») et le texte glissé dans la fenêtre. La détection est
volontairement prudente : on ne propose que des liens de sites de vidéo/audio connus ou des fichiers média directs, pas
n'importe quelle adresse copiée.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from .media import MEDIA_EXTENSIONS
from .online import MAX_URL_LENGTH, is_direct_stream, is_web_url

_URL = re.compile(r"https?://[^\s<>\"'`\\^{}|\x00-\x1f]+", re.IGNORECASE)
_TRAILING = ".,;:!?)]}»›"
MAX_TEXT = 20_000                      # on n'analyse pas plus de ce volume de texte copié
MAX_LINKS = 50

# Sites dont les pages sont gérées par yt-dlp (liste de départ ; le reste passe par « Télécharger » à la main).
KNOWN_HOSTS = (
    "youtube.com", "youtu.be", "youtube-nocookie.com", "music.youtube.com", "vimeo.com", "dailymotion.com", "dai.ly",
    "twitch.tv", "tiktok.com", "instagram.com", "facebook.com", "fb.watch", "twitter.com", "x.com", "reddit.com",
    "redd.it", "soundcloud.com", "bandcamp.com", "bilibili.com", "nicovideo.jp", "ok.ru", "vk.com", "rumble.com",
    "odysee.com", "arte.tv", "france.tv", "ina.fr", "tf1.fr", "6play.fr", "bfmtv.com", "lemonde.fr", "mixcloud.com",
    "streamable.com", "imgur.com", "archive.org", "ted.com", "kick.com", "peertube.tv",
)


@dataclass(frozen=True)
class Link:
    url: str
    host: str
    kind: str                          # "page" (site de vidéo), "file" (fichier média direct), "playlist"
    label: str                         # texte court à afficher


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _known_host(host: str) -> bool:
    return any(host == known or host.endswith("." + known) for known in KNOWN_HOSTS)


def extract_urls(text: str) -> list[str]:
    """Toutes les adresses http(s) d'un texte, dans l'ordre, sans doublon ni ponctuation finale."""
    found: list[str] = []
    for match in _URL.finditer((text or "")[:MAX_TEXT]):
        url = match.group(0).rstrip(_TRAILING)
        # Parenthèse fermante finale : on la garde seulement si elle est appariée (ex. Wikipédia).
        if url.count("(") > url.count(")") and match.group(0).endswith(")"):
            url += ")"
        if len(url) <= MAX_URL_LENGTH and is_web_url(url) and url not in found:
            found.append(url)
            if len(found) >= MAX_LINKS:
                break
    return found


def classify(url: str) -> Link | None:
    """``None`` si le lien ne mérite pas d'être proposé."""
    if not is_web_url(url):
        return None
    host = _host(url)
    parsed = urlparse(url)
    if is_direct_stream(url) and parsed.path.lower().rsplit(".", 1)[-1] in {e.lstrip(".") for e in MEDIA_EXTENSIONS}:
        name = parsed.path.rsplit("/", 1)[-1] or host
        return Link(url, host, "file", name)
    if not _known_host(host):
        return None
    query = parse_qs(parsed.query)
    path = parsed.path.lower()
    is_playlist = "list" in query and "v" not in query or path.startswith(("/playlist", "/sets/", "/channel/", "/c/", "/@"))
    # Pages d'accueil ou de recherche : rien à télécharger.
    if path in ("", "/") or path.startswith(("/results", "/search", "/feed", "/explore", "/login", "/signin")):
        return None
    return Link(url, host, "playlist" if is_playlist else "page", host + parsed.path[:60])


def hunt(text: str, *, ignore: set[str] | frozenset[str] = frozenset()) -> list[Link]:
    """Liens à proposer dans un texte, sans ceux déjà vus (``ignore``)."""
    links = []
    for url in extract_urls(text):
        if url in ignore:
            continue
        link = classify(url)
        if link is not None:
            links.append(link)
    return links
