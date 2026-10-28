"""Point d'entrée : ``python -m pyplayer [fichiers…]`` ou la commande ``pyplayer``."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from pyplayer import APP_NAME, APP_ORGANIZATION, __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyplayer", description=f"{APP_NAME} — lecteur vidéo/audio local.")
    parser.add_argument("files", nargs="*", help="fichiers, dossiers, playlists (.m3u/.pls) ou URL à ouvrir")
    parser.add_argument("-a", "--enqueue", action="store_true",
                        help="ajouter à la playlist active au lieu de lire immédiatement")
    parser.add_argument("-n", "--new-instance", action="store_true",
                        help="ne pas réutiliser la fenêtre déjà ouverte")
    parser.add_argument("--fullscreen", action="store_true", help="démarrer en plein écran")
    parser.add_argument("--debug", action="store_true", help="journaux détaillés")
    parser.add_argument("-v", "--version", action="version", version=f"{APP_NAME} {__version__}")
    return parser


def _normalize(items: list[str]) -> list[str]:
    """Chemins relatifs → absolus (la seconde instance n'a pas le même dossier courant)."""
    return [item if "://" in item else os.path.abspath(item) for item in items]


def run_ytdlp(arguments: list[str]) -> int:
    """Mode « yt-dlp » : l'exécutable de PyPlayer lance le module yt-dlp embarqué (téléchargements d'un binaire autonome,
    sans Python installé). Aucune interface n'est créée."""
    import yt_dlp
    try:
        yt_dlp.main(arguments)
    except SystemExit as stop:
        return int(stop.code or 0) if isinstance(stop.code, int) or stop.code is None else 1
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if arguments and arguments[0] == "--ytdlp-run":
        return run_ytdlp(arguments[1:])
    from pyplayer import cli
    if cli.is_cli(arguments):                       # « pyplayer download … » : sans Qt, démarrage instantané
        return cli.main(arguments)
    args = build_parser().parse_args(arguments)
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

    from pyplayer.api import paths
    from pyplayer.api.logging_setup import setup_logging

    log_path = setup_logging(paths.data_dir(), debug=args.debug)
    logger = logging.getLogger("pyplayer")
    logger.info("Démarrage de %s %s (journal : %s)", APP_NAME, __version__, log_path)

    from PySide6 import QtCore, QtWidgets

    if os.environ.get("PYPLAYER_OPENGLES") == "1":  # réservé aux pilotes problématiques
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseOpenGLES)

    app = QtWidgets.QApplication([sys.argv[0]])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setDesktopFileName("pyplayer")

    from pyplayer.ui import theme

    theme.apply_dark_theme(app)  # avant toute fenêtre : l'apparence ne dépend pas du système
    from pyplayer.ui.single_instance import SingleInstance

    files = _normalize(args.files)
    single = SingleInstance()
    if not args.new_instance and single.send_to_running(files, args.enqueue):
        logger.info("Instance déjà ouverte : fichiers transmis")
        return 0

    app.setWindowIcon(theme.app_icon())

    from pyplayer.ui.main_window import MainWindow

    window = MainWindow()

    def handle_exception(exc_type, exc, tb):
        logger.error("Exception non gérée", exc_info=(exc_type, exc, tb))
        if not issubclass(exc_type, KeyboardInterrupt):
            QtWidgets.QMessageBox.critical(
                window, f"{APP_NAME} — erreur inattendue",
                f"{exc_type.__name__} : {exc}\n\nDétails dans :\n{log_path}")

    sys.excepthook = handle_exception

    def open_items(items: list[str], enqueue: bool = False):
        logger.info("Ouverture demandée : %s (ajout=%s)", items, enqueue)
        urls = [i for i in items if "://" in i and not i.lower().startswith("file://")]
        local = [i for i in items if i not in urls]
        if local:
            window.open_paths(local, enqueue=enqueue)
        elif urls:
            window.open_url(QtCore.QUrl.fromUserInput(urls[0]))
        if window.isMinimized():
            window.showNormal()
        window.raise_()
        window.activateWindow()

    if single.listen():
        single.message_received.connect(open_items)

    window.show()
    if args.fullscreen:
        window.enter_fullscreen()
    if files:
        QtCore.QTimer.singleShot(0, lambda: open_items(files, args.enqueue))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
