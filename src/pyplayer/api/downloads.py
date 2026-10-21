"""Moteur de téléchargement (yt-dlp), sans Qt.

Chaque téléchargement est un **sous-processus** yt-dlp : l'application reste légère en mémoire (yt-dlp et ses
extracteurs n'existent que pendant le téléchargement), une pause ou une annulation se résume à arrêter le processus, et
la reprise s'appuie sur ``--continue`` (le fichier ``.part`` repart où il en était).

  * ``DownloadOptions`` + ``build_args`` : toutes les options utiles de yt-dlp, validées, passées en ``--option=valeur``
    (jamais via un shell, jamais une valeur prise pour une option) ;
  * ``expand_playlist`` : une playlist devient autant d'éléments que de vidéos (sélection ``1-5,8``, ordre inversé) ;
  * ``DownloadManager`` : file d'attente, téléchargements en parallèle, pause/reprise/annulation, nouvelles tentatives
    espacées, reprise automatique au redémarrage, état enregistré de façon atomique.
"""

from __future__ import annotations

import enum
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Callable

from . import online, paths
from .io_utils import read_json, write_json_atomic

logger = logging.getLogger(__name__)

RUN_FLAG = "--ytdlp-run"              # l'exécutable de PyPlayer peut servir de yt-dlp (voir __main__)
STATE_FILE = "downloads.json"
MAX_ATTEMPTS = 3
RETRY_BASE_S = 4.0
PROGRESS_MIN_INTERVAL_S = 0.25        # au plus ~4 mises à jour de progression par seconde et par téléchargement
SAVE_MIN_INTERVAL_S = 1.0
MAX_ITEMS = 2000

PRESETS = {
    "best": "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
    "audio_mp3": "", "audio_m4a": "", "audio_opus": "", "custom": "",
}
SINGLE_FILE_PRESETS = {                # sans ffmpeg : un seul fichier déjà complet (image + son)
    "best": "b", "1080p": "b[height<=1080]/b", "720p": "b[height<=720]/b", "480p": "b[height<=480]/b",
    "custom": "b",
}
AUDIO_FORMATS = {"audio_mp3": "mp3", "audio_m4a": "m4a", "audio_opus": "opus"}
SPONSORBLOCK_CATEGORIES = "sponsor,selfpromo,interaction,intro,outro,preview,music_offtopic"
RETRYABLE = re.compile(r"HTTP Error (5\d\d|429)|timed? ?out|Connection (reset|aborted|refused)|"
                       r"Temporary failure|Network is unreachable|Read timed out|IncompleteRead|"
                       r"Remote end closed|SSL|Unable to download", re.I)
FATAL_HINTS = re.compile(r"Video unavailable|Private video|Sign in|members-only|not available in your country|"
                         r"has been removed|Unsupported URL|HTTP Error 40[134]", re.I)


class State(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


ACTIVE_STATES = (State.QUEUED, State.RUNNING)
FINISHED_STATES = (State.DONE, State.ERROR, State.CANCELLED)


# ---------------------------------------------------------------------- options
@dataclass
class DownloadOptions:
    preset: str = "best"                   # best | 1080p | 720p | 480p | audio_mp3 | audio_m4a | audio_opus | custom
    custom_format: str = ""                # sélecteur yt-dlp si preset == "custom"
    container: str = "mp4"                 # format de fusion vidéo+audio : mp4 | mkv | webm
    subtitles: bool = False
    sub_langs: str = "fr,en"
    auto_subs: bool = True
    embed_subs: bool = True
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    embed_chapters: bool = True
    sponsorblock: str = ""                 # "" | "mark" | "remove"
    sponsorblock_categories: str = SPONSORBLOCK_CATEGORIES
    playlist: bool = False                 # télécharger toute la playlist de l'adresse
    playlist_items: str = ""               # « 1-5,8 » (vide = tout)
    playlist_reverse: bool = False
    rate_limit: str = ""                   # « 2M », « 500K »
    concurrent_fragments: int = 8          # téléchargement rapide : fragments en parallèle (HLS/DASH)
    retries: int = 10
    cookies_from_browser: str = ""         # « firefox », « chrome:Profil 1 »
    proxy: str = ""
    archive: bool = True                   # ne retélécharge pas ce qui l'a déjà été (fichier d'archive par dossier)
    output_template: str = ""              # vide = modèle par défaut
    restrict_filenames: bool = False
    write_info_json: bool = False
    write_description: bool = False
    min_filesize: str = ""
    max_filesize: str = ""
    date_after: str = ""                   # AAAAMMJJ ou « today-1week »
    sections: str = ""                     # « *10:00-12:00 » : seulement un extrait
    use_aria2c: bool = False               # accélérateur externe s'il est installé

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DownloadOptions":
        known = {f.name: f for f in fields(cls)}
        clean: dict[str, Any] = {}
        for key, value in (data or {}).items():
            if key in known and isinstance(value, type(getattr(cls(), key))):
                clean[key] = value
        return cls(**clean)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_RATE = re.compile(r"^\d+(\.\d+)?[KkMmGg]?$")
_ITEMS = re.compile(r"^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$")
_LANGS = re.compile(r"^[A-Za-z0-9*_.\-]+(,[A-Za-z0-9*_.\-]+)*$")
_BROWSER = re.compile(r"^(brave|chrome|chromium|edge|firefox|opera|safari|vivaldi|whale)(:[^\x00-\x1f]{1,120})?$")
_PROXY = re.compile(r"^(https?|socks4a?|socks5h?)://[^\s\x00-\x1f]{1,200}$")
_DATE = re.compile(r"^(\d{8}|(now|today)(-\d+(day|week|month|year)s?)?)$")
_SECTION = re.compile(r"^\*?[0-9:.\-]+(,\*?[0-9:.\-]+)*$|^\*[0-9:.\-]+-(inf|[0-9:.]+)$")
_FORMAT = re.compile(r"^[A-Za-z0-9_\[\]<>=!+/,.*()^~\-]{1,200}$")      # syntaxe des sélecteurs : ni espace ni « $ » ni « | »


def validate(options: DownloadOptions) -> None:
    """Lève ``ValueError`` (message lisible) si une option est invalide ou dangereuse."""
    if options.preset not in PRESETS:
        raise ValueError(f"Qualité inconnue : {options.preset}")
    if options.preset == "custom" and not _FORMAT.match(options.custom_format or ""):
        raise ValueError("Format personnalisé invalide.")
    if options.container not in ("mp4", "mkv", "webm"):
        raise ValueError("Conteneur inconnu (mp4, mkv ou webm).")
    if options.sponsorblock not in ("", "mark", "remove"):
        raise ValueError("Option SponsorBlock invalide.")
    checks = [
        (options.rate_limit, _RATE, "Limite de débit invalide (ex. 2M, 500K)."),
        (options.min_filesize, _RATE, "Taille minimale invalide (ex. 50M)."),
        (options.max_filesize, _RATE, "Taille maximale invalide (ex. 2G)."),
        (options.playlist_items, _ITEMS, "Sélection de playlist invalide (ex. 1-5,8)."),
        (options.sub_langs, _LANGS, "Langues de sous-titres invalides (ex. fr,en)."),
        (options.cookies_from_browser, _BROWSER, "Navigateur de cookies invalide (ex. firefox)."),
        (options.proxy, _PROXY, "Proxy invalide (ex. http://hote:3128)."),
        (options.date_after, _DATE, "Date invalide (AAAAMMJJ ou today-1week)."),
        (options.sections, _SECTION, "Extrait invalide (ex. *10:00-12:00)."),
        (options.sponsorblock_categories, _LANGS, "Catégories SponsorBlock invalides."),
    ]
    for value, pattern, message in checks:
        if value and not pattern.match(value):
            raise ValueError(message)
    if not 1 <= options.concurrent_fragments <= 32:
        raise ValueError("Fragments simultanés : entre 1 et 32.")
    if not 0 <= options.retries <= 100:
        raise ValueError("Nombre de tentatives : entre 0 et 100.")
    template = options.output_template
    if template and (len(template) > 300 or ".." in template or template.startswith(("/", "\\")) or ":" in template[:3]
                     or "\x00" in template):
        raise ValueError("Modèle de nom de fichier invalide (pas de chemin absolu ni de « .. »).")


def default_template(playlist_group: bool = False) -> str:
    if playlist_group:
        return "%(playlist_title|)s/%(playlist_index|)s - %(title).150B [%(id)s].%(ext)s"
    return "%(title).150B [%(id)s].%(ext)s"


def build_args(url: str, out_dir: Path | str, options: DownloadOptions, *, ffmpeg_dir: str | None = None,
               aria2c: str | None = None, group: bool = False) -> list[str]:
    """Arguments de yt-dlp (sans l'exécutable) pour télécharger ``url`` : un élément, jamais une playlist entière."""
    validate(options)
    url = online.clean_url(url)
    out_dir = Path(out_dir)
    with_ffmpeg = bool(ffmpeg_dir)
    args = ["--ignore-config", "--newline", "--no-colors", "--no-warnings", "--no-playlist", "--progress",
            "--progress-template=download:PYPPROG:%(progress)j",
            "--print=before_dl:PYPINFO:%(.{id,title,uploader,duration,playlist_index,n_entries,extractor_key,webpage_url})j",
            "--print=after_move:PYPDONE:%(filepath)j", "--no-simulate",
            "--continue", "--part", f"--retries={options.retries}", f"--fragment-retries={options.retries}",
            f"--concurrent-fragments={options.concurrent_fragments}",
            f"--paths=home:{out_dir}", f"--output={options.output_template or default_template(group)}"]
    # Sans ffmpeg : pas de fusion vidéo+audio, de conversion ni d'intégration -> on prend un fichier unique, tel quel.
    if options.preset in AUDIO_FORMATS and with_ffmpeg:
        args += ["--extract-audio", f"--audio-format={AUDIO_FORMATS[options.preset]}", "--audio-quality=0"]
    elif options.preset in AUDIO_FORMATS:
        args.append("--format=ba/b")
    else:
        selector = options.custom_format if options.preset == "custom" else (
            PRESETS[options.preset] if with_ffmpeg else SINGLE_FILE_PRESETS[options.preset])
        args.append(f"--format={selector}")
        if with_ffmpeg:
            args.append(f"--merge-output-format={options.container}")
    if with_ffmpeg:
        if options.embed_metadata:
            args.append("--embed-metadata")
        if options.embed_thumbnail:
            args += ["--embed-thumbnail", "--convert-thumbnails=jpg"]
        if options.embed_chapters:
            args.append("--embed-chapters")
    if options.subtitles:
        args += ["--write-subs", f"--sub-langs={options.sub_langs}"]
        if options.auto_subs:
            args.append("--write-auto-subs")
        if with_ffmpeg and options.embed_subs and options.container != "webm" and options.preset not in AUDIO_FORMATS:
            args.append("--embed-subs")
    if with_ffmpeg and options.sponsorblock == "mark":
        args.append(f"--sponsorblock-mark={options.sponsorblock_categories}")
    elif with_ffmpeg and options.sponsorblock == "remove":
        args.append(f"--sponsorblock-remove={options.sponsorblock_categories}")
    if options.rate_limit:
        args.append(f"--limit-rate={options.rate_limit}")
    if options.cookies_from_browser:
        args.append(f"--cookies-from-browser={options.cookies_from_browser}")
    if options.proxy:
        args.append(f"--proxy={options.proxy}")
    if options.archive:
        args.append(f"--download-archive={out_dir / '.pyplayer-archive.txt'}")
    if options.restrict_filenames:
        args.append("--restrict-filenames")
    elif os.name == "nt":
        args.append("--windows-filenames")
    if options.write_info_json:
        args.append("--write-info-json")
    if options.write_description:
        args.append("--write-description")
    if options.min_filesize:
        args.append(f"--min-filesize={options.min_filesize}")
    if options.max_filesize:
        args.append(f"--max-filesize={options.max_filesize}")
    if options.date_after:
        args.append(f"--dateafter={options.date_after}")
    if options.sections:
        args.append(f"--download-sections={options.sections}")
    if options.use_aria2c and aria2c:
        args += [f"--downloader={aria2c}", "--downloader-args=aria2c:-x 16 -s 16 -k 1M"]
    if ffmpeg_dir:
        args.append(f"--ffmpeg-location={ffmpeg_dir}")
    return [*args, "--", url]


# ---------------------------------------------------------------------- commande yt-dlp
def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals() or hasattr(sys.modules.get("__main__"), "__compiled__")


def ytdlp_command() -> list[str] | None:
    """Commande qui lance yt-dlp : exécutable mis à jour > exécutable du système > module Python (via Python, ou via
    l'exécutable de PyPlayer lui-même dans un binaire autonome)."""
    binary = online.find_binary()
    if binary is not None:
        return [str(binary)]
    if online.module_available():
        if is_frozen():
            return [sys.argv[0] if os.path.isfile(sys.argv[0]) else sys.executable, RUN_FLAG]
        return [sys.executable, "-m", "yt_dlp"]
    return None


def tools_dir() -> Path:
    """Outils téléchargés par l'application (yt-dlp, ffmpeg) : dans le dossier de données, jamais dans le système."""
    return paths.data_dir() / "tools"


def ffmpeg_dir() -> str | None:
    """Dossier de ffmpeg : celui installé par PyPlayer d'abord, puis celui du système ; ``None`` si absent."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    own = tools_dir() / "ffmpeg" / name
    if own.is_file():
        return str(own.parent)
    found = shutil.which("ffmpeg")
    return str(Path(found).parent) if found else None


# ---------------------------------------------------------------------- lecture de la sortie
@dataclass
class Event:
    kind: str                              # "info" | "progress" | "done" | "error" | "text"
    data: dict[str, Any] = field(default_factory=dict)
    text: str = ""


def parse_line(line: str) -> Event | None:
    """Une ligne de la sortie de yt-dlp -> événement (``None`` si sans intérêt)."""
    line = line.rstrip("\r\n")
    if line.startswith("PYPPROG:"):
        try:
            data = json.loads(line[8:])
        except ValueError:
            return None
        return Event("progress", data) if isinstance(data, dict) else None
    if line.startswith("PYPINFO:"):
        try:
            data = json.loads(line[8:])
        except ValueError:
            return None
        return Event("info", data) if isinstance(data, dict) else None
    if line.startswith("PYPDONE:"):
        try:
            value = json.loads(line[8:])
        except ValueError:
            return None
        return Event("done", {"filepath": value}) if isinstance(value, str) and value else None
    if line.startswith("ERROR:"):
        return Event("error", text=line[6:].strip())
    if "has already been recorded in the archive" in line:
        return Event("text", {"archived": True}, line)
    return Event("text", text=line) if line.strip() else None


def friendly_error(text: str) -> str:
    return online._friendly_error(text)


def is_retryable(message: str) -> bool:
    return bool(RETRYABLE.search(message or "")) and not FATAL_HINTS.search(message or "")


# ---------------------------------------------------------------------- playlists
def parse_selection(spec: str, total: int) -> list[int]:
    """« 1-5,8 » -> indices (base 1) dans l'ordre demandé, bornés à ``total``, sans doublon."""
    if not spec:
        return list(range(1, total + 1))
    chosen: list[int] = []
    for part in spec.split(","):
        low, _, high = part.partition("-")
        try:
            start, end = int(low), int(high) if high else int(low)
        except ValueError:
            continue
        # Bornes avant de parcourir : « 1-99999999999 » ne doit jamais boucler des milliards de fois.
        if end >= start:
            numbers = range(max(start, 1), min(end, total) + 1)
        else:
            numbers = range(min(start, total), max(end, 1) - 1, -1)
        for number in numbers:
            if number not in chosen:
                chosen.append(number)
    return chosen


@dataclass
class PlaylistEntry:
    url: str
    title: str
    index: int


def entries_from_flat(info: dict[str, Any], page_url: str) -> tuple[str, list[PlaylistEntry]]:
    """JSON ``--flat-playlist -J`` -> (titre de la playlist, entrées). Une vidéo seule donne une liste d'un élément."""
    raw = info.get("entries")
    if info.get("_type") != "playlist" or not isinstance(raw, list):
        return "", [PlaylistEntry(page_url, str(info.get("title") or ""), 1)]
    entries = []
    for number, entry in enumerate(raw, 1):
        if not isinstance(entry, dict):
            continue
        link = entry.get("url") or entry.get("webpage_url")
        if not isinstance(link, str) or not link.startswith(("http://", "https://")):
            ident = entry.get("id")
            link = f"https://www.youtube.com/watch?v={ident}" if isinstance(ident, str) and info.get(
                "extractor_key") == "YoutubeTab" else ""
        if link:
            entries.append(PlaylistEntry(link, str(entry.get("title") or ""), number))
    return str(info.get("title") or ""), entries


def select_entries(entries: list[PlaylistEntry], spec: str, reverse: bool) -> list[PlaylistEntry]:
    picked = [entries[i - 1] for i in parse_selection(spec, len(entries))]
    return list(reversed(picked)) if reverse else picked


def expand_playlist(url: str, options: DownloadOptions, command: list[str] | None = None,
                    timeout: int = 90) -> tuple[str, list[PlaylistEntry]]:
    """Liste les vidéos d'une playlist sans rien télécharger (``--flat-playlist``)."""
    command = command or ytdlp_command()
    if command is None:
        raise online.OnlineError("yt-dlp n'est pas installé.")
    extra = []
    if options.cookies_from_browser:
        extra.append(f"--cookies-from-browser={options.cookies_from_browser}")
    if options.proxy:
        extra.append(f"--proxy={options.proxy}")
    args = [*command, "--ignore-config", "--no-warnings", "--flat-playlist", "-J", "--yes-playlist", *extra, "--",
            online.clean_url(url)]
    try:
        done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as error:
        raise online.OnlineError("Délai dépassé en lisant la playlist.") from error
    except OSError as error:
        raise online.OnlineError(f"yt-dlp ne peut pas être lancé : {error}") from error
    if done.returncode != 0:
        raise online.OnlineError(friendly_error(done.stderr))
    try:
        info = json.loads(done.stdout)
    except ValueError as error:
        raise online.OnlineError("Réponse illisible de yt-dlp.") from error
    title, entries = entries_from_flat(info, url)
    return title, select_entries(entries, options.playlist_items, options.playlist_reverse)


# ---------------------------------------------------------------------- éléments et gestionnaire
@dataclass
class DownloadItem:
    id: str
    url: str
    out_dir: str
    options: dict[str, Any]
    title: str = ""
    state: State = State.QUEUED
    progress: float = 0.0
    downloaded: int = 0
    total: int = 0
    speed: float = 0.0
    eta: int = -1
    filepath: str = ""
    error: str = ""
    attempts: int = 0
    group: str = ""                        # titre de la playlist d'origine
    index: int = 0                         # position dans la playlist
    added_at: float = field(default_factory=time.time)
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadItem | None":
        try:
            state = State(data.get("state", "queued"))
            return cls(id=str(data["id"]), url=online.clean_url(str(data["url"])), out_dir=str(data["out_dir"]),
                       options=dict(data.get("options") or {}), title=str(data.get("title") or ""), state=state,
                       progress=float(data.get("progress") or 0), downloaded=int(data.get("downloaded") or 0),
                       total=int(data.get("total") or 0), filepath=str(data.get("filepath") or ""),
                       error=str(data.get("error") or ""), attempts=int(data.get("attempts") or 0),
                       group=str(data.get("group") or ""), index=int(data.get("index") or 0),
                       added_at=float(data.get("added_at") or time.time()), archived=bool(data.get("archived")))
        except (KeyError, TypeError, ValueError, online.OnlineError):
            return None


Listener = Callable[[str, DownloadItem], None]
ProcessFactory = Callable[[list[str]], Any]


def default_download_dir() -> Path:
    for name in ("Videos", "Movies", "Downloads"):
        candidate = Path.home() / name
        if candidate.is_dir():
            return candidate / "PyPlayer"
    return Path.home() / "PyPlayer"


class DownloadManager:
    """File de téléchargements. Les écouteurs sont appelés depuis des fils de travail : l'interface doit remettre les
    événements dans son propre fil (signal Qt)."""

    def __init__(self, state_file: Path | str | None = None, *, max_parallel: int = 2,
                 command_provider: Callable[[], list[str] | None] | None = None,
                 process_factory: ProcessFactory | None = None, retry_base_s: float = RETRY_BASE_S,
                 playlist_expander: Callable[[str, DownloadOptions], tuple[str, list[PlaylistEntry]]] | None = None,
                 restore: bool = True) -> None:
        self.state_file = Path(state_file) if state_file else None
        self.max_parallel = max(1, int(max_parallel))
        self._command_provider = command_provider or ytdlp_command
        self._process_factory = process_factory or self._spawn
        self._expander = playlist_expander or (lambda url, opts: expand_playlist(url, opts, self._command_provider()))
        self.retry_base_s = retry_base_s
        self._items: dict[str, DownloadItem] = {}
        self._procs: dict[str, Any] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._last_emit: dict[str, float] = {}
        self._listeners: list[Listener] = []
        self._lock = threading.RLock()
        self._closed = False
        self._dirty = False
        self._last_save = 0.0
        if restore:                                  # la ligne de commande peut repartir d'une file vide
            self.load()

    def command_available(self) -> bool:
        """Vrai si yt-dlp peut être lancé (sinon l'interface propose de l'installer)."""
        return self._command_provider() is not None

    # ------------------------------------------------------------------ écouteurs
    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def _emit(self, kind: str, item: DownloadItem) -> None:
        for listener in list(self._listeners):
            try:
                listener(kind, item)
            except Exception:  # noqa: BLE001 -- un écouteur défaillant ne casse jamais un téléchargement
                logger.exception("Écouteur de téléchargement en échec")

    # ------------------------------------------------------------------ lecture
    def items(self) -> list[DownloadItem]:
        with self._lock:
            return sorted(self._items.values(), key=lambda i: (i.added_at, i.index))

    def get(self, item_id: str) -> DownloadItem | None:
        return self._items.get(item_id)

    def counts(self) -> dict[str, int]:
        with self._lock:
            result = {state.value: 0 for state in State}
            for item in self._items.values():
                result[item.state.value] += 1
            return result

    # ------------------------------------------------------------------ ajout
    def add(self, url: str, options: DownloadOptions | None = None, out_dir: Path | str | None = None,
            *, title: str = "", group: str = "", index: int = 0) -> DownloadItem:
        """Ajoute UN élément (une vidéo). Pour une playlist, voir :meth:`add_playlist`."""
        options = options or DownloadOptions()
        validate(options)
        url = online.clean_url(url)
        folder = Path(out_dir) if out_dir else default_download_dir()
        with self._lock:
            if self._closed:
                raise RuntimeError("gestionnaire fermé")
            duplicate = next((i for i in self._items.values() if i.url == url and i.out_dir == str(folder)
                              and i.state in ACTIVE_STATES + (State.PAUSED,)), None)
            if duplicate is not None:
                return duplicate                                  # même adresse déjà en cours : pas de doublon
            if len(self._items) >= MAX_ITEMS:
                self._prune_finished(keep=MAX_ITEMS // 2)
            item = DownloadItem(id=uuid.uuid4().hex[:12], url=url, out_dir=str(folder), options=options.to_dict(),
                                title=title, group=group, index=index)
            self._items[item.id] = item
            self._dirty = True
        self._emit("added", item)
        self._schedule()
        self._save()
        return item

    def add_playlist(self, url: str, options: DownloadOptions | None = None, out_dir: Path | str | None = None,
                     on_done: Callable[[list[DownloadItem] | None, str], None] | None = None) -> None:
        """Déplie la playlist dans un fil, puis ajoute une entrée par vidéo. ``on_done(items, erreur)`` à la fin."""
        options = options or DownloadOptions()
        validate(options)
        url = online.clean_url(url)

        def work() -> None:
            try:
                group, entries = self._expander(url, options)
            except Exception as error:  # noqa: BLE001
                message = str(error) or "lecture de la playlist impossible"
                if on_done:
                    on_done(None, message)
                return
            single = DownloadOptions.from_dict({**options.to_dict(), "playlist": False, "playlist_items": ""})
            folder = Path(out_dir) if out_dir else default_download_dir()
            added = [self.add(e.url, single, folder, title=e.title, group=group, index=e.index)
                     for e in entries]
            for entry_item in added:                                  # le sous-dossier de la playlist
                self._items[entry_item.id].options["output_template"] = options.output_template or default_template(True)
            self._dirty = True
            self._save()
            if on_done:
                on_done(added, "")

        threading.Thread(target=work, name="pyp-playlist", daemon=True).start()

    # ------------------------------------------------------------------ contrôle
    def pause(self, item_id: str) -> bool:
        with self._lock:
            item = self._items.get(item_id)
            if item is None or item.state not in ACTIVE_STATES:
                return False
            item.state = State.PAUSED
            item.speed, item.eta = 0.0, -1
            self._cancel_timer(item_id)
            self._stop_process(item_id)
            self._dirty = True
        self._emit("state", item)
        self._schedule()
        self._save()
        return True

    def resume(self, item_id: str) -> bool:
        with self._lock:
            item = self._items.get(item_id)
            if item is None or item.state not in (State.PAUSED, State.ERROR, State.CANCELLED):
                return False
            item.state, item.error, item.attempts = State.QUEUED, "", 0
            self._dirty = True
        self._emit("state", item)
        self._schedule()
        self._save()
        return True

    def cancel(self, item_id: str, *, delete_partial: bool = False) -> bool:
        with self._lock:
            item = self._items.get(item_id)
            if item is None or item.state in (State.DONE, State.CANCELLED):
                return False
            item.state = State.CANCELLED
            item.speed, item.eta = 0.0, -1
            self._cancel_timer(item_id)
            self._stop_process(item_id)
            self._dirty = True
        if delete_partial:
            self._delete_partial(item)
        self._emit("state", item)
        self._schedule()
        self._save()
        return True

    def remove(self, item_id: str, *, delete_file: bool = False) -> bool:
        with self._lock:
            item = self._items.pop(item_id, None)
            if item is None:
                return False
            self._cancel_timer(item_id)
            self._stop_process(item_id)
            self._dirty = True
        if delete_file and item.filepath:
            try:
                Path(item.filepath).unlink(missing_ok=True)
            except OSError as error:
                logger.warning("Suppression de %s impossible : %s", item.filepath, error)
        self._emit("removed", item)
        self._schedule()
        self._save()
        return True

    def clear_finished(self) -> int:
        with self._lock:
            ids = [i.id for i in self._items.values() if i.state in FINISHED_STATES]
        for item_id in ids:
            self.remove(item_id)
        return len(ids)

    def pause_all(self) -> None:
        for item in self.items():
            self.pause(item.id)

    def resume_all(self) -> None:
        for item in self.items():
            if item.state == State.PAUSED:
                self.resume(item.id)

    def set_max_parallel(self, value: int) -> None:
        self.max_parallel = max(1, min(8, int(value)))
        self._schedule()

    def shutdown(self, save: bool = True) -> None:
        """Arrête les processus (les ``.part`` restent : la reprise est automatique) et enregistre l'état.
        Idempotent : un second appel ne fait rien (important après une réinitialisation des données)."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for item_id in list(self._timers):
                self._cancel_timer(item_id)
            for item_id in list(self._procs):
                self._stop_process(item_id)
            for item in self._items.values():
                if item.state == State.RUNNING:
                    item.state = State.QUEUED                       # reprendra au prochain démarrage
                item.speed, item.eta = 0.0, -1
            self._dirty = save
        if save:
            self._save(force=True)
        for thread in list(self._threads.values()):
            thread.join(timeout=3)

    # ------------------------------------------------------------------ ordonnancement
    def _schedule(self) -> None:
        with self._lock:
            if self._closed:
                return
            running = sum(1 for i in self._items.values() if i.state == State.RUNNING)
            for item in sorted(self._items.values(), key=lambda i: (i.added_at, i.index)):
                if running >= self.max_parallel:
                    break
                if item.state == State.QUEUED and item.id not in self._threads and item.id not in self._timers:
                    command = self._command_provider()
                    if command is None:
                        item.state, item.error = State.ERROR, "yt-dlp n'est pas installé."
                        self._dirty = True
                        threading.Thread(target=self._emit, args=("state", item), daemon=True).start()
                        continue
                    item.state = State.RUNNING
                    item.error = ""
                    thread = threading.Thread(target=self._run, args=(item, command), name=f"pyp-dl-{item.id}",
                                              daemon=True)
                    self._threads[item.id] = thread
                    running += 1
                    thread.start()

    def _spawn(self, args: list[str]) -> Any:
        return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace", bufsize=1,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def _run(self, item: DownloadItem, command: list[str]) -> None:
        last_error = ""
        archived = False
        try:
            options = DownloadOptions.from_dict(item.options)
            Path(item.out_dir).mkdir(parents=True, exist_ok=True)
            args = [*command, *build_args(item.url, item.out_dir, options, ffmpeg_dir=ffmpeg_dir(),
                                          aria2c=shutil.which("aria2c"), group=bool(item.group))]
            self._emit("state", item)
            process = self._process_factory(args)
            with self._lock:
                self._procs[item.id] = process
                closed = self._closed
            if closed:                                      # arrêt demandé entre l'état « en cours » et la création du processus
                self._stop_process(item.id)
            for line in process.stdout:
                event = parse_line(line)
                if event is None:
                    continue
                if event.kind == "info":
                    self._on_info(item, event.data)
                elif event.kind == "progress":
                    self._on_progress(item, event.data)
                elif event.kind == "done":
                    item.filepath = event.data["filepath"]
                elif event.kind == "error":
                    last_error = event.text
                elif event.data.get("archived"):
                    archived = True
            code = process.wait()
        except Exception as error:  # noqa: BLE001
            logger.exception("Téléchargement %s : erreur inattendue", item.id)
            code, last_error = -1, str(error)
        finally:
            with self._lock:
                self._procs.pop(item.id, None)
                self._threads.pop(item.id, None)
        self._finish(item, code, last_error, archived)

    def _on_info(self, item: DownloadItem, data: dict[str, Any]) -> None:
        title = data.get("title")
        if isinstance(title, str) and title:
            item.title = title
        self._dirty = True
        self._emit("info", item)

    def _on_progress(self, item: DownloadItem, data: dict[str, Any]) -> None:
        done = data.get("downloaded_bytes")
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        item.downloaded = int(done) if isinstance(done, (int, float)) else item.downloaded
        item.total = int(total) if isinstance(total, (int, float)) and total > 0 else item.total
        item.progress = min(1.0, item.downloaded / item.total) if item.total else item.progress
        speed, eta = data.get("speed"), data.get("eta")
        item.speed = float(speed) if isinstance(speed, (int, float)) else 0.0
        item.eta = int(eta) if isinstance(eta, (int, float)) else -1
        now = time.monotonic()
        if data.get("status") == "finished" or now - self._last_emit.get(item.id, 0.0) >= PROGRESS_MIN_INTERVAL_S:
            self._last_emit[item.id] = now
            self._emit("progress", item)

    def _finish(self, item: DownloadItem, code: int, error_text: str, archived: bool) -> None:
        retry_in = None
        with self._lock:
            removed = self._items.get(item.id) is not item        # retiré de la liste pendant l'exécution
            if removed:
                self._last_emit.pop(item.id, None)
            elif item.state != State.RUNNING:                     # mis en pause / annulé pendant l'exécution
                self._last_emit.pop(item.id, None)
                self._dirty = True
            elif code == 0:
                item.state, item.progress, item.speed, item.eta = State.DONE, 1.0, 0.0, -1
                # Succès sans aucun fichier produit : déjà dans l'archive, ou écarté par un filtre (taille, date).
                item.archived = not item.filepath
                item.error = ""
            else:
                message = friendly_error(error_text) if error_text else "Échec du téléchargement."
                item.attempts += 1
                if is_retryable(error_text) and item.attempts < MAX_ATTEMPTS and not self._closed:
                    item.state = State.QUEUED
                    item.error = f"Nouvelle tentative ({item.attempts}/{MAX_ATTEMPTS})…"
                    retry_in = self.retry_base_s * (2 ** (item.attempts - 1))
                    self._timers[item.id] = timer = threading.Timer(retry_in, self._retry_due, args=(item.id,))
                    timer.daemon = True
                    timer.start()
                else:
                    item.state, item.error = State.ERROR, message
                item.speed, item.eta = 0.0, -1
            self._dirty = True
        if not removed:                                           # un élément retiré ne doit jamais « réapparaître »
            self._emit("state", item)
        self._schedule()
        self._save()

    def _retry_due(self, item_id: str) -> None:
        with self._lock:
            self._timers.pop(item_id, None)
        self._schedule()

    # ------------------------------------------------------------------ processus
    def _stop_process(self, item_id: str) -> None:
        process = self._procs.get(item_id)
        if process is None:
            return
        try:
            process.terminate()
        except OSError:
            pass
        threading.Thread(target=self._kill_later, args=(process,), daemon=True).start()

    @staticmethod
    def _kill_later(process: Any) -> None:
        try:
            process.wait(timeout=5)
        except Exception:  # noqa: BLE001 -- ne répond pas à terminate : on force
            try:
                process.kill()
            except OSError:
                pass

    def _cancel_timer(self, item_id: str) -> None:
        timer = self._timers.pop(item_id, None)
        if timer is not None:
            timer.cancel()

    @staticmethod
    def _delete_partial(item: DownloadItem) -> None:
        folder = Path(item.out_dir)
        stem = Path(item.filepath).stem if item.filepath else ""
        if not stem or not folder.is_dir():
            return
        for leftover in folder.rglob(f"{stem}*"):
            if leftover.suffix in (".part", ".ytdl", ".temp") or leftover.name.endswith((".part-Frag", ".part.ytdl")):
                try:
                    leftover.unlink()
                except OSError:
                    pass

    def _prune_finished(self, keep: int) -> None:
        finished = sorted((i for i in self._items.values() if i.state in FINISHED_STATES), key=lambda i: i.added_at)
        for old in finished[: max(0, len(self._items) - keep)]:
            self._items.pop(old.id, None)

    # ------------------------------------------------------------------ persistance
    def load(self) -> None:
        """Recharge l'état ; ce qui tournait (arrêt brutal compris) est remis en file : reprise automatique."""
        if self.state_file is None or not self.state_file.exists():
            return
        try:
            data = read_json(self.state_file)
        except (OSError, ValueError) as error:
            logger.warning("%s illisible (%s) : file vide", self.state_file.name, error)
            return
        raw = data.get("items") if isinstance(data, dict) else None
        for entry in (raw if isinstance(raw, list) else [])[:MAX_ITEMS]:
            item = DownloadItem.from_dict(entry) if isinstance(entry, dict) else None
            if item is None:
                continue
            if item.state == State.RUNNING:
                item.state = State.QUEUED
            self._items[item.id] = item

    def start(self) -> None:
        """À appeler une fois l'interface prête : démarre ce qui attend (dont la reprise après redémarrage)."""
        self._schedule()

    def _save(self, force: bool = False) -> None:
        if self.state_file is None or not self._dirty:
            return
        now = time.monotonic()
        if not force and now - self._last_save < SAVE_MIN_INTERVAL_S:
            return
        with self._lock:
            payload = {"version": 1, "items": [i.to_dict() for i in self._items.values()]}
            self._dirty = False
            self._last_save = now
        try:
            write_json_atomic(self.state_file, payload, indent=None)
        except OSError as error:
            logger.error("Enregistrement de %s impossible : %s", self.state_file, error)
            self._dirty = True

    def flush(self) -> None:
        self._save(force=True)


def default_state_file() -> Path:
    return paths.data_dir() / STATE_FILE
