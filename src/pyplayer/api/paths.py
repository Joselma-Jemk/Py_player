"""Emplacements des ressources embarquées et des données utilisateur."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HOME_ENV_VAR = "PYPLAYER_HOME"


def package_dir() -> Path:
    """Dossier du package ``pyplayer`` (fonctionne aussi une fois gelé par PyInstaller/Nuitka)."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root) / "pyplayer"
    return Path(__file__).resolve().parent.parent


def resources_dir() -> Path:
    return package_dir() / "resources"


def icons_dir() -> Path:
    return resources_dir() / "icons"


def font_path() -> Path:
    return resources_dir() / "material-symbols-outlined.ttf"


def app_icon_path() -> Path:
    return icons_dir() / "pyplayer_1.png"


def placeholder_icon_path() -> Path:
    return icons_dir() / "pyplayer_4.png"


def data_dir() -> Path:
    """Dossier des données utilisateur (playlists, réglages, logs).

    ``$PYPLAYER_HOME`` prime (tests, installations portables). Sinon ``~/.pyplayer``
    (emplacement historique, conservé pour ne pas perdre les playlists existantes).
    Si le dossier n'est pas inscriptible, repli sur un dossier temporaire.
    """
    override = os.environ.get(HOME_ENV_VAR)
    candidate = Path(override).expanduser() if override else Path.home() / ".pyplayer"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / ".write_probe"
        probe.touch()
        probe.unlink()
        return candidate
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "pyplayer"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
