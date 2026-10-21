"""Mise à jour de PyPlayer depuis les releases GitHub du dépôt (sans Qt).

Sécurité : HTTPS et hôtes GitHub uniquement ; le fichier n'est gardé que si sa somme SHA-256, publiée dans la même
release (``SHA256SUMS-<système>.txt``), correspond. Limite à connaître : ces sommes protègent contre un fichier
corrompu ou altéré en route, pas contre une release publiée par un compte compromis (il faudrait une signature).
"""

from __future__ import annotations

import logging
import os
import platform
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import fetch
from .fetch import FetchError, FetchPolicy

logger = logging.getLogger(__name__)

REPO = "Joselma-Jemk/Py_player"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_INTERVAL_S = 24 * 3600
MAX_APP_BYTES = 300 * 1024 * 1024
NO_CHECK_ENV = "PYPLAYER_NO_UPDATE_CHECK"
INSTALLER_UNINSTALLER = "unins000.exe"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    tag: str
    notes: str
    page_url: str
    kind: str                       # "windows-installer" | "windows-portable" | "linux-binary" | "manual"
    asset_name: str = ""
    asset_url: str = ""
    sha256: str = ""
    size: int = 0

    @property
    def can_install(self) -> bool:
        return bool(self.asset_url and self.sha256)


@dataclass(frozen=True)
class ApplyResult:
    action: str                     # "run-installer" | "restart" | "saved"
    path: Path


def system_name() -> str:
    return {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(platform.system(), "")


def install_kind(*, frozen: bool | None = None, executable: str | None = None, system: str | None = None) -> str:
    """Comment PyPlayer est installé : détermine quel fichier de la release convient et comment le mettre en place."""
    from .downloads import is_frozen
    frozen = is_frozen() if frozen is None else frozen
    system = system or system_name()
    executable = executable or (sys.argv[0] if frozen else sys.executable)
    if not frozen:
        return "manual"                                                   # pip / sources : on ne touche à rien
    if system == "windows":
        installed = (Path(executable).resolve().parent / INSTALLER_UNINSTALLER).is_file()
        return "windows-installer" if installed else "windows-portable"
    if system == "linux":
        return "linux-binary"
    return "manual"


def asset_names(version: str, kind: str, machine: str | None = None) -> tuple[str, str]:
    """(fichier à télécharger, fichier des sommes) pour cette version et ce mode d'installation."""
    machine = machine or platform.machine()
    if kind == "windows-installer":
        return f"pyplayer-{version}-windows-setup.exe", "SHA256SUMS-windows.txt"
    if kind == "windows-portable":
        return f"pyplayer-{version}-windows-{machine}.exe", "SHA256SUMS-windows.txt"
    if kind == "linux-binary":
        return f"pyplayer-{version}-linux-{machine}", "SHA256SUMS-linux.txt"
    return "", ""


def should_check(last_check: float, now: float | None = None, interval: float = CHECK_INTERVAL_S) -> bool:
    now = time.time() if now is None else now
    return last_check <= 0 or last_check > now or now - last_check >= interval        # horloge reculée : on revérifie


def check(current_version: str, *, kind: str | None = None, policy: FetchPolicy | None = None,
          get_json: Callable[..., Any] = fetch.get_json, get_text: Callable[..., str] = fetch.get_text,
          api_url: str = API_LATEST, machine: str | None = None) -> UpdateInfo | None:
    """Dernière release publiée si elle est plus récente que ``current_version`` ; ``None`` sinon.
    Lève ``FetchError`` si le réseau ou la réponse est inutilisable."""
    policy = policy or FetchPolicy()
    release = get_json(api_url, policy)
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag = str(release.get("tag_name") or "")
    version = tag.lstrip("vV")
    if not version or not fetch.is_newer(version, current_version):
        return None
    kind = kind if kind is not None else install_kind()
    raw_assets = release.get("assets")
    assets = {a["name"]: a for a in (raw_assets if isinstance(raw_assets, list) else [])
              if isinstance(a, dict) and isinstance(a.get("name"), str) and isinstance(a.get("browser_download_url"), str)}
    name, sums_name = asset_names(version, kind, machine)
    page = str(release.get("html_url") or f"https://github.com/{REPO}/releases/tag/{tag}")
    notes = str(release.get("body") or "")[:20_000]
    base = dict(version=version, tag=tag, notes=notes, page_url=page)
    if not name or name not in assets or sums_name not in assets:
        return UpdateInfo(kind="manual", **base)                          # rien d'installable automatiquement
    try:
        sha = fetch.parse_sums(get_text(assets[sums_name]["browser_download_url"], policy)).get(name, "")
    except FetchError:
        sha = ""
    if not sha:
        return UpdateInfo(kind="manual", **base)                          # pas de somme : installation automatique refusée
    return UpdateInfo(kind=kind, asset_name=name, asset_url=assets[name]["browser_download_url"], sha256=sha,
                      size=int(assets[name].get("size") or 0), **base)


def updates_dir() -> Path:
    from . import paths
    return paths.data_dir() / "updates"


def apply(info: UpdateInfo, *, progress: Callable[[int, int], None] | None = None,
          cancelled: Callable[[], bool] | None = None, policy: FetchPolicy | None = None,
          download: Callable[..., Path] = fetch.download_verified, current_executable: str | None = None) -> ApplyResult:
    """Télécharge et prépare la mise à jour (vérifiée). L'appelant lance ensuite l'installateur ou redémarre."""
    if not info.can_install:
        raise FetchError("Cette mise à jour ne peut pas s'installer automatiquement : ouvrez la page de la version.")
    target_dir = updates_dir()
    staged = target_dir / info.asset_name
    download(info.asset_url, staged, info.sha256, policy=policy or FetchPolicy(), max_bytes=MAX_APP_BYTES,
             progress=progress, cancelled=cancelled)
    if info.kind == "windows-installer":
        return ApplyResult("run-installer", staged)
    if info.kind == "linux-binary":
        current = Path(current_executable or sys.argv[0]).resolve()
        replacement = current.with_name(current.name + ".new")
        try:
            replacement.write_bytes(staged.read_bytes())
            replacement.chmod(replacement.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            os.replace(replacement, current)                              # Linux : on peut remplacer un exécutable en cours
        except OSError as error:
            replacement.unlink(missing_ok=True)
            raise FetchError(f"Remplacement impossible ({error}). Le fichier vérifié est dans : {staged}") from error
        staged.unlink(missing_ok=True)
        return ApplyResult("restart", current)
    return ApplyResult("saved", staged)                                   # version portable : on laisse l'utilisateur la lancer


def run_installer(path: Path) -> None:
    """Lance l'installateur Windows en silence puis laisse l'application se fermer (il relance PyPlayer ensuite)."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
                     creationflags=flags, close_fds=True)


def relaunch() -> None:
    """Relance l'application (binaire autonome)."""
    subprocess.Popen([sys.argv[0]], close_fds=True)
