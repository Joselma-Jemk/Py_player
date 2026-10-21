"""Ligne de commande de PyPlayer : télécharger, gérer les outils, mettre à jour. Sans Qt : démarrage instantané.

    pyplayer download URL [URL…] [options]     télécharger (alias : dl)
    pyplayer tools status | install [ytdlp|ffmpeg|all]
    pyplayer update [--install]
    pyplayer self-install                      (Linux/macOS) place la commande « pyplayer » dans ~/.local/bin

Sans sous-commande, ``pyplayer`` ouvre l'application (voir ``__main__``).
Codes de sortie : 0 tout va bien · 1 au moins un échec · 2 usage invalide · 3 yt-dlp absent · 130 interrompu.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, TextIO

from pyplayer import __version__
from pyplayer.api import downloads as dl
from pyplayer.api import fetch, links, online, paths, tools, updater
from pyplayer.api.media import format_duration, format_size
from pyplayer.api.settings import Settings

SUBCOMMANDS = {"download": "download", "dl": "download", "tools": "tools", "update": "update",
               "self-install": "self-install"}
EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_NO_YTDLP, EXIT_INTERRUPTED = 0, 1, 2, 3, 130
QUALITY_CHOICES = ["best", "1080p", "720p", "480p", "audio-mp3", "audio-m4a", "audio-opus"]


def is_cli(arguments: list[str]) -> bool:
    """Vrai si le premier argument est exactement une sous-commande. Elle l'emporte toujours (même si un dossier porte ce
    nom) : pour ouvrir un fichier ou un dossier « download », écrire ``./download``."""
    return bool(arguments) and arguments[0] in SUBCOMMANDS


# ---------------------------------------------------------------------- analyse des arguments
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyplayer", description="PyPlayer en ligne de commande : télécharger, outils, mises à jour.",
        epilog="Sans sous-commande, « pyplayer » ouvre l'application. Aide d'une commande : pyplayer download --help")
    sub = parser.add_subparsers(dest="command", metavar="commande")

    down = sub.add_parser("download", aliases=["dl"], help="télécharger des vidéos, playlists ou audios (yt-dlp)",
                          description="Télécharge des liens (YouTube, Vimeo, SoundCloud… ou fichiers directs) avec reprise "
                                      "automatique. Mêmes réglages que l'application (dossier, qualité, options).")
    down.add_argument("urls", nargs="*", metavar="LIEN", help="adresses à télécharger (« - » : lire le texte sur l'entrée standard)")
    down.add_argument("-f", "--file", action="append", default=[], metavar="FICHIER",
                      help="fichier texte : tous les liens qu'il contient sont téléchargés (répétable)")
    down.add_argument("-o", "--output", metavar="DOSSIER", help="dossier de destination")
    down.add_argument("-q", "--quality", choices=QUALITY_CHOICES, help="qualité (défaut : celle de l'application)")
    down.add_argument("-a", "--audio", nargs="?", const="mp3", choices=["mp3", "m4a", "opus"],
                      help="audio seulement (mp3 par défaut)")
    down.add_argument("--format", dest="custom_format", metavar="SELECTEUR", help="sélecteur de format yt-dlp personnalisé")
    down.add_argument("--container", choices=["mp4", "mkv", "webm"], help="conteneur de la vidéo finale")
    down.add_argument("-p", "--playlist", action="store_true", help="télécharger toute la playlist")
    down.add_argument("--items", metavar="1-5,8", help="éléments de la playlist à télécharger")
    down.add_argument("--reverse", action="store_true", help="playlist dans l'ordre inverse")
    down.add_argument("--subs", nargs="?", const="fr,en", metavar="LANGUES", help="télécharger les sous-titres (fr,en par défaut)")
    down.add_argument("--sponsorblock", choices=["mark", "remove"], help="marquer ou retirer les segments sponsorisés")
    down.add_argument("--sections", metavar="*10:00-12:00", help="télécharger seulement un extrait")
    down.add_argument("--rate-limit", metavar="2M", help="limite de débit")
    down.add_argument("--fragments", type=int, metavar="N", help="fragments simultanés (vitesse, défaut 8)")
    down.add_argument("--proxy", metavar="URL", help="proxy (http://hote:3128, socks5://…)")
    down.add_argument("--cookies-from-browser", metavar="NAVIGATEUR", help="cookies d'un navigateur (firefox, chrome…)")
    down.add_argument("--template", metavar="MODELE", help="modèle de nom de fichier yt-dlp")
    down.add_argument("--no-archive", action="store_true", help="retélécharger même ce qui l'a déjà été")
    down.add_argument("--no-embed", action="store_true", help="ne rien intégrer au fichier (pochette, métadonnées, chapitres)")
    down.add_argument("--restrict-filenames", action="store_true", help="noms de fichiers ASCII simples")
    down.add_argument("--info-json", action="store_true", help="enregistrer aussi le fichier .info.json")
    down.add_argument("--aria2c", action="store_true", help="accélérer avec aria2c s'il est installé")
    down.add_argument("-j", "--parallel", type=int, default=3, metavar="N", help="téléchargements simultanés (défaut 3)")
    down.add_argument("--resume", action="store_true", help="reprendre les téléchargements interrompus du dernier lancement")
    down.add_argument("--play", action="store_true", help="ouvrir PyPlayer sur les fichiers téléchargés")
    down.add_argument("--json", action="store_true", help="sortie en lignes JSON (pour les scripts)")
    down.add_argument("--quiet", action="store_true", help="n'afficher que les erreurs")
    down.add_argument("-y", "--yes", action="store_true", help="installer yt-dlp sans demander s'il manque")

    tool = sub.add_parser("tools", help="yt-dlp et FFmpeg : état et installation")
    tool_sub = tool.add_subparsers(dest="tools_command", metavar="action")
    tool_sub.add_parser("status", help="affiche ce qui est installé")
    install = tool_sub.add_parser("install", help="installe ou met à jour un outil (vérifié par SHA-256)")
    install.add_argument("name", nargs="?", default="all", choices=["ytdlp", "yt-dlp", "ffmpeg", "all"])

    upd = sub.add_parser("update", help="cherche (et installe) une nouvelle version de PyPlayer")
    upd.add_argument("--install", action="store_true", help="télécharge et installe la mise à jour trouvée")

    sub.add_parser("self-install", help="Linux/macOS : installe la commande « pyplayer » dans ~/.local/bin")
    parser.download_parser = down                      # type: ignore[attr-defined]  -- voir parse_args
    return parser


def parse_args(arguments: list[str]) -> argparse.Namespace:
    """Analyse la ligne de commande. Pour « download », liens et options peuvent se mélanger librement
    (``dl URL1 -q 720p URL2 -o dossier``) : argparse l'exige explicitement."""
    parser = build_parser()
    if arguments and arguments[0] in ("download", "dl"):
        namespace = parser.download_parser.parse_intermixed_args(arguments[1:])   # type: ignore[attr-defined]
        namespace.command = arguments[0]
        return namespace
    return parser.parse_args(arguments)


def settings_snapshot() -> Settings:
    return Settings(paths.data_dir() / "settings.json")


def options_from_args(args: argparse.Namespace, settings: Settings | None = None) -> dl.DownloadOptions:
    """Réglages de l'application, surchargés par les options de la ligne de commande."""
    settings = settings or settings_snapshot()
    options = dl.DownloadOptions.from_dict(settings.get("download_options"))
    preset = settings.get("download_preset")
    options.preset = preset if preset in dl.PRESETS else "best"
    if args.quality:
        options.preset = args.quality.replace("-", "_")
    if args.audio:
        options.preset = f"audio_{args.audio}"
    if args.custom_format:
        options.preset, options.custom_format = "custom", args.custom_format
    if args.container:
        options.container = args.container
    if args.playlist:
        options.playlist = True
    if args.items:
        options.playlist_items, options.playlist = args.items, True
    if args.reverse:
        options.playlist_reverse = True
    if args.subs:
        options.subtitles, options.sub_langs = True, args.subs
    if args.sponsorblock:
        options.sponsorblock = args.sponsorblock
    if args.sections:
        options.sections = args.sections
    if args.rate_limit:
        options.rate_limit = args.rate_limit
    if args.fragments is not None:
        options.concurrent_fragments = args.fragments
    if args.proxy:
        options.proxy = args.proxy
    if args.cookies_from_browser:
        options.cookies_from_browser = args.cookies_from_browser
    if args.template:
        options.output_template = args.template
    if args.no_archive:
        options.archive = False
    if args.no_embed:
        options.embed_thumbnail = options.embed_metadata = options.embed_chapters = False
    if args.restrict_filenames:
        options.restrict_filenames = True
    if args.info_json:
        options.write_info_json = True
    if args.aria2c:
        options.use_aria2c = True
    return options


# ---------------------------------------------------------------------- affichage
class Printer:
    """Affiche la progression : une ligne qui se met à jour dans un terminal, des lignes régulières sinon, ou du JSON."""

    def __init__(self, out: TextIO, err: TextIO, *, json_mode: bool = False, quiet: bool = False,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.out, self.err, self.json_mode, self.quiet, self.clock = out, err, json_mode, quiet, clock
        self.tty = bool(getattr(out, "isatty", lambda: False)()) and not json_mode
        self._lock = threading.Lock()
        self._last_status = 0.0
        self._status_len = 0

    def _write(self, text: str, stream: TextIO | None = None) -> None:
        stream = stream or self.out
        try:
            stream.write(text)
            stream.flush()
        except (OSError, ValueError, UnicodeEncodeError):
            pass

    def _clear_status(self) -> None:
        if self.tty and self._status_len:
            self._write("\r" + " " * self._status_len + "\r")
            self._status_len = 0

    def line(self, text: str, *, error: bool = False, event: dict[str, Any] | None = None) -> None:
        with self._lock:
            if self.json_mode:
                if event is not None:
                    self._write(json.dumps(event, ensure_ascii=False) + "\n")
                return
            if self.quiet and not error:
                return
            self._clear_status()
            self._write(text + "\n", self.err if error else self.out)

    def status(self, items: list[dl.DownloadItem], *, force: bool = False) -> None:
        """Ligne d'état de l'ensemble (une fois par seconde dans un terminal, toutes les 5 s sinon)."""
        if self.quiet or self.json_mode:
            return
        now = self.clock()
        if not force and now - self._last_status < (1.0 if self.tty else 5.0):
            return
        self._last_status = now
        running = [i for i in items if i.state == dl.State.RUNNING]
        done = sum(1 for i in items if i.state in dl.FINISHED_STATES)
        if not running:
            return
        speed = sum(i.speed or 0.0 for i in running)
        lead = running[0]
        text = f"[{done}/{len(items)}] {lead.progress * 100:3.0f}% "
        if speed:
            text += f"{format_size(int(speed))}/s "
        if lead.eta >= 0:
            text += f"reste {format_duration(lead.eta * 1000)} "
        text += "- " + (lead.title or lead.url)
        with self._lock:
            if self.tty:
                width = shutil.get_terminal_size((100, 20)).columns - 1
                text = text[:width]
                self._write("\r" + text.ljust(self._status_len))
                self._status_len = len(text)
            else:
                self._write(text + "\n")

    def progress_event(self, item: dl.DownloadItem) -> None:
        if self.json_mode:
            self.line("", event={"event": "progress", "id": item.id, "title": item.title, "percent": round(item.progress * 100, 1),
                                 "speed": item.speed, "eta": item.eta, "downloaded": item.downloaded, "total": item.total})


def describe(item: dl.DownloadItem) -> str:
    return item.title or item.url


# ---------------------------------------------------------------------- yt-dlp manquant
def ensure_ytdlp(manager: dl.DownloadManager, *, assume_yes: bool, out: TextIO, err: TextIO,
                 stdin: TextIO | None = None, install: Callable[..., Path] | None = None) -> bool:
    """Vrai si yt-dlp est utilisable. Sinon propose (ou, avec ``--yes``, fait) l'installation officielle vérifiée."""
    if manager.command_available():
        return True
    err.write("yt-dlp n'est pas installé.\n")
    answer = "o" if assume_yes else ""
    interactive = bool(getattr(stdin or sys.stdin, "isatty", lambda: False)())
    if not assume_yes and interactive:
        err.write("L'installer maintenant depuis github.com/yt-dlp/yt-dlp (≈ 35 Mo, vérifié par SHA-256) ? [O/n] ")
        err.flush()
        answer = ((stdin or sys.stdin).readline() or "o").strip().lower() or "o"
    if answer not in ("o", "oui", "y", "yes"):
        err.write("Installation : pyplayer tools install ytdlp\n")
        return False
    try:
        (install or tools.install_ytdlp)(progress=_download_bar(out, "yt-dlp"))
        out.write("\n")
    except fetch.FetchError as error:
        err.write(f"\nInstallation impossible : {error}\n")
        return False
    return manager.command_available()


def _download_bar(out: TextIO, label: str) -> Callable[[int, int], None]:
    state = {"last": 0.0}

    def progress(done: int, total: int) -> None:
        now = time.monotonic()
        if now - state["last"] < 0.2 and done != total:
            return
        state["last"] = now
        text = f"  {label} : {format_size(done)}" + (f" / {format_size(total)} ({100 * done // total} %)" if total else "")
        try:
            out.write("\r" + text)
            out.flush()
        except (OSError, ValueError):
            pass
    return progress


# ---------------------------------------------------------------------- télécharger
def collect_urls(args: argparse.Namespace, stdin: TextIO) -> tuple[list[str], list[str]]:
    """(adresses valides, entrées ignorées) : liens des arguments, des fichiers (-f) et de l'entrée standard (« - »)."""
    texts: list[str] = []
    ignored: list[str] = []
    for item in args.urls:
        if item == "-":
            texts.append(stdin.read())
        elif online.is_web_url(item):
            texts.append(item)
        else:
            ignored.append(item)
    for name in args.file:
        try:
            texts.append(Path(name).read_text(encoding="utf-8", errors="replace"))
        except OSError as error:
            ignored.append(f"{name} ({error.strerror or error})")
    found: list[str] = []
    for text in texts:
        for url in links.extract_urls(text):
            if url not in found:
                found.append(url)
    return found, ignored


def cmd_download(args: argparse.Namespace, *, out: TextIO, err: TextIO, stdin: TextIO,
                 manager_factory: Callable[..., dl.DownloadManager] | None = None,
                 sleep: Callable[[float], None] = time.sleep, settings: Settings | None = None) -> int:
    settings = settings or settings_snapshot()
    urls, ignored = collect_urls(args, stdin)
    for bad in ignored:
        err.write(f"Ignoré (pas un lien valide) : {bad}\n")
    if not urls and not args.resume:
        err.write("Aucun lien à télécharger. Exemple : pyplayer download https://youtu.be/XXXX\n")
        return EXIT_USAGE
    try:
        options = options_from_args(args, settings)
        dl.validate(options)
    except ValueError as error:
        err.write(f"Option invalide : {error}\n")
        return EXIT_USAGE
    if not 1 <= args.parallel <= 8:
        err.write("Option invalide : -j doit être entre 1 et 8.\n")
        return EXIT_USAGE
    folder = Path(args.output).expanduser() if args.output else (
        Path(settings.get("download_dir")).expanduser() if settings.get("download_dir") else dl.default_download_dir())

    make = manager_factory or dl.DownloadManager
    manager = make(paths.data_dir() / "downloads-cli.json", max_parallel=args.parallel, restore=args.resume)
    printer = Printer(out, err, json_mode=args.json, quiet=args.quiet)
    if not ensure_ytdlp(manager, assume_yes=args.yes, out=out, err=err, stdin=stdin):
        return EXIT_NO_YTDLP
    if dl.ffmpeg_dir() is None and not args.quiet and not args.json:
        err.write("Astuce : FFmpeg est absent (qualité limitée). Installation : pyplayer tools install ffmpeg\n")

    printed: set[tuple[str, str]] = set()

    def on_event(kind: str, item: dl.DownloadItem) -> None:
        if kind == "info" and (item.id, "info") not in printed:
            printed.add((item.id, "info"))
            printer.line(f"> {describe(item)}", event={"event": "start", "id": item.id, "title": item.title, "url": item.url})
        elif kind == "progress":
            printer.progress_event(item)
        elif kind == "state" and item.state in dl.FINISHED_STATES and (item.id, "end") not in printed:
            printed.add((item.id, "end"))
            if item.state == dl.State.DONE:
                where = item.filepath or "(déjà téléchargé ou écarté par un filtre)"
                printer.line(f"[OK] {describe(item)} -> {where}",
                             event={"event": "done", "id": item.id, "title": item.title, "path": item.filepath,
                                    "skipped": bool(item.archived)})
            elif item.state == dl.State.ERROR:
                printer.line(f"[ERREUR] {describe(item)} : {item.error}", error=True,
                             event={"event": "error", "id": item.id, "title": item.title, "message": item.error, "url": item.url})

    manager.subscribe(on_event)
    expansion_errors: list[str] = []
    try:
        pending_playlists = threading.Event()
        pending_playlists.set()
        for url in urls:
            kind = links.classify(url)
            as_playlist = options.playlist or (kind is not None and kind.kind == "playlist")
            if as_playlist:
                pending_playlists.clear()
                wanted = dl.DownloadOptions.from_dict({**options.to_dict(), "playlist": True})

                def done(items, error, _event=pending_playlists):
                    if items is None:
                        expansion_errors.append(error)
                    _event.set()
                manager.add_playlist(url, wanted, folder, on_done=done)
                if not pending_playlists.wait(120):
                    expansion_errors.append("délai dépassé en lisant la playlist")
            else:
                manager.add(url, options, folder)
        for message in expansion_errors:
            printer.line(f"[ERREUR] playlist : {message}", error=True, event={"event": "error", "message": message})
        manager.start()
        while True:
            items = manager.items()
            if items and all(i.state in dl.FINISHED_STATES for i in items):
                break
            if not items and expansion_errors:
                break
            printer.status(items)
            sleep(0.2)
    except KeyboardInterrupt:
        manager.shutdown()
        printer.line("\nInterrompu : relancez avec --resume pour reprendre là où vous en étiez.", error=True)
        return EXIT_INTERRUPTED

    items = manager.items()
    ok = [i for i in items if i.state == dl.State.DONE]
    failed = [i for i in items if i.state == dl.State.ERROR]
    for item in ok:
        manager.remove(item.id)                        # la file mémorisée ne garde que ce qui reste à faire
    manager.shutdown(save=True)
    summary = f"{len(ok)} terminé(s), {len(failed)} en erreur."
    printer.line(summary, event={"event": "summary", "done": len(ok), "failed": len(failed) + len(expansion_errors)})
    if args.play and ok:
        _play([i.filepath for i in ok if i.filepath])
    return EXIT_FAILED if failed or expansion_errors else EXIT_OK


def _play(files: list[str]) -> None:
    """Ouvre PyPlayer sur les fichiers téléchargés (fenêtre indépendante : la commande se termine)."""
    existing = [f for f in files if os.path.isfile(f)]
    if not existing:
        return
    command = [sys.argv[0]] if dl.is_frozen() else [sys.executable, "-m", "pyplayer"]
    try:
        subprocess.Popen([*command, *existing], close_fds=True)
    except OSError:
        pass


# ---------------------------------------------------------------------- outils, mise à jour, auto-installation
def cmd_tools(args: argparse.Namespace, *, out: TextIO, err: TextIO,
              install_ytdlp: Callable[..., Path] | None = None, install_ffmpeg: Callable[..., Path] | None = None) -> int:
    action = args.tools_command or "status"
    if action == "status":
        binary = online.find_binary()
        version = online.version()
        out.write(f"yt-dlp  : {'installé' if binary or online.module_available() else 'absent'}"
                  f"{f' ({binary})' if binary else ''}{f' - version {version}' if version else ''}\n")
        folder = dl.ffmpeg_dir()
        out.write(f"FFmpeg  : {f'installé ({folder})' if folder else 'absent'}\n")
        out.write(f"Données : {paths.data_dir()}\n")
        return EXIT_OK
    wanted = ["ytdlp", "ffmpeg"] if args.name == "all" else ["ytdlp" if args.name in ("ytdlp", "yt-dlp") else "ffmpeg"]
    status = EXIT_OK
    for name in wanted:
        try:
            if name == "ytdlp":
                path = (install_ytdlp or tools.install_ytdlp)(progress=_download_bar(out, "yt-dlp"))
                out.write(f"\nyt-dlp installé : {path}\n")
            else:
                path = (install_ffmpeg or tools.install_ffmpeg)(progress=_download_bar(out, "FFmpeg"))
                out.write(f"\nFFmpeg installé : {path}\n")
        except fetch.FetchError as error:
            err.write(f"\nInstallation de {name} impossible : {error}\n")
            status = EXIT_FAILED
    return status


def cmd_update(args: argparse.Namespace, *, out: TextIO, err: TextIO, check: Callable[..., Any] | None = None,
               apply: Callable[..., Any] | None = None) -> int:
    try:
        info = (check or updater.check)(__version__)
    except fetch.FetchError as error:
        err.write(f"Impossible de vérifier les mises à jour : {error}\n")
        return EXIT_FAILED
    if info is None:
        out.write(f"PyPlayer {__version__} est à jour.\n")
        return EXIT_OK
    out.write(f"PyPlayer {info.version} est disponible (vous avez {__version__}).\n{info.page_url}\n")
    if not args.install:
        out.write("Pour l'installer : pyplayer update --install\n")
        return EXIT_OK
    if not info.can_install:
        err.write("Cette version ne s'installe pas automatiquement ici : téléchargez-la depuis la page ci-dessus.\n")
        return EXIT_FAILED
    try:
        result = (apply or updater.apply)(info, progress=_download_bar(out, "PyPlayer"))
    except fetch.FetchError as error:
        err.write(f"\nMise à jour impossible : {error}\n")
        return EXIT_FAILED
    out.write("\n")
    if result.action == "run-installer":
        out.write("Lancement de l'installateur (PyPlayer va se mettre à jour en silence)…\n")
        updater.run_installer(result.path)
    elif result.action == "restart":
        out.write("Mise à jour installée : relancez PyPlayer.\n")
    else:
        out.write(f"Nouvelle version (vérifiée) : {result.path}\n")
    return EXIT_OK


def cmd_self_install(*, out: TextIO, err: TextIO, home: Path | None = None, executable: str | None = None,
                     frozen: bool | None = None, env_path: str | None = None) -> int:
    """Linux/macOS : place la commande ``pyplayer`` dans ``~/.local/bin`` (copie du binaire, ou petit script)."""
    if os.name == "nt":
        err.write("Sous Windows, l'installateur ajoute « pyplayer » au PATH (cases à cocher à l'installation).\n")
        return EXIT_USAGE
    home = home or Path.home()
    frozen = dl.is_frozen() if frozen is None else frozen
    executable = executable or sys.argv[0]
    target_dir = home / ".local" / "bin"
    target = target_dir / "pyplayer"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        if frozen:
            if Path(executable).resolve() != target.resolve():
                temp = target.with_name("pyplayer.new")
                shutil.copy2(executable, temp)
                os.replace(temp, target)
        else:
            target.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m pyplayer "$@"\n', encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as error:
        err.write(f"Installation impossible : {error}\n")
        return EXIT_FAILED
    out.write(f"Commande installée : {target}\n")
    path_dirs = [Path(p).expanduser() for p in (env_path if env_path is not None else os.environ.get("PATH", "")).split(os.pathsep) if p]
    if target_dir not in path_dirs:
        out.write('Ajoutez ce dossier à votre PATH, par exemple dans ~/.bashrc :\n  export PATH="$HOME/.local/bin:$PATH"\n')
    return EXIT_OK


# ---------------------------------------------------------------------- point d'entrée
def main(arguments: list[str], *, out: TextIO | None = None, err: TextIO | None = None, stdin: TextIO | None = None) -> int:
    out, err, stdin = out or sys.stdout, err or sys.stderr, stdin or sys.stdin
    for stream in (out, err):                          # console Windows (cp1252) : jamais d'erreur d'encodage
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    parser = build_parser()
    try:
        args = parse_args(arguments)
    except SystemExit as stop:
        return int(stop.code) if isinstance(stop.code, int) else EXIT_USAGE
    command = SUBCOMMANDS.get(args.command or "", "")
    if command == "download":
        return cmd_download(args, out=out, err=err, stdin=stdin)
    if command == "tools":
        return cmd_tools(args, out=out, err=err)
    if command == "update":
        return cmd_update(args, out=out, err=err)
    if command == "self-install":
        return cmd_self_install(out=out, err=err)
    parser.print_help(out)
    return EXIT_USAGE
