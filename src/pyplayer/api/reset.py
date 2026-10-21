"""Suppression et réinitialisation des données utilisateur (sans Qt).

Chaque catégorie correspond à des fichiers précis du dossier de données ; rien d'autre n'est jamais touché
(le dossier lui-même, d'éventuels fichiers étrangers placés dedans et les médias de l'utilisateur sont intacts).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PLAYLISTS = "playlists"
BACKUPS = "backups"
RESUME = "resume"
SETTINGS = "settings"
LOGS = "logs"

LABELS = {
    PLAYLISTS: "Playlists",
    BACKUPS: "Sauvegardes automatiques des playlists",
    RESUME: "Positions de reprise de lecture",
    SETTINGS: "Réglages (volume, fenêtre, fichiers récents…)",
    LOGS: "Journaux",
}
ALL_CATEGORIES = tuple(LABELS)


@dataclass
class CategoryInfo:
    key: str
    label: str
    files: int
    size: int


@dataclass
class ResetReport:
    deleted_files: int = 0
    freed_bytes: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _files_of(home: Path, category: str) -> list[Path]:
    """Fichiers d'une catégorie (jamais de dossier : on ne supprime que ce qui appartient à PyPlayer)."""
    home = Path(home)
    if category == PLAYLISTS:
        folder = home / "playlists"
        if not folder.is_dir():
            return []
        return sorted(p for p in (*folder.glob("*.json"), *folder.glob("*.corrupt")) if p.is_file())
    if category == BACKUPS:
        folder = home / "playlists" / "backups"
        return sorted(p for p in folder.glob("*.json") if p.is_file()) if folder.is_dir() else []
    if category == RESUME:
        return [p for p in (home / "resume.json", home / "resume.json.corrupt") if p.is_file()]
    if category == SETTINGS:
        return [p for p in (home / "settings.json", home / "settings.json.corrupt") if p.is_file()]
    if category == LOGS:
        return sorted(p for p in home.glob("pyplayer.log*") if p.is_file())
    raise KeyError(category)


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def summarize(home: Path | str) -> list[CategoryInfo]:
    """Ce que contient chaque catégorie (pour l'afficher avant de supprimer)."""
    home = Path(home)
    infos = []
    for key in ALL_CATEGORIES:
        files = _files_of(home, key)
        infos.append(CategoryInfo(key, LABELS[key], len(files), sum(_size(f) for f in files)))
    return infos


def reset_data(home: Path | str, categories: tuple[str, ...] | list[str] = ALL_CATEGORIES,
               *, truncate_logs: bool = True) -> ResetReport:
    """Supprime les catégories demandées. Les erreurs sont rapportées, jamais levées : on supprime le maximum.

    Le fichier de journal ouvert ne peut pas être effacé sous Windows : avec ``truncate_logs`` le fichier courant est
    vidé plutôt que supprimé (les journaux tournants ``.log.1``… sont supprimés normalement).
    """
    home = Path(home)
    report = ResetReport()
    unknown = [c for c in categories if c not in LABELS]
    if unknown:
        raise KeyError(unknown[0])
    for key in categories:
        for path in _files_of(home, key):
            size = _size(path)
            try:
                if key == LOGS and truncate_logs and path.name == "pyplayer.log":
                    if size == 0:
                        continue                                   # déjà vide : rien à vider, rien à compter
                    path.write_text("", encoding="utf-8")
                else:
                    path.unlink()
                report.deleted_files += 1
                report.freed_bytes += size
            except OSError as error:
                report.errors.append(f"{path.name} : {error}")
                logger.warning("Suppression de %s impossible : %s", path, error)
    # Dossiers devenus vides et créés par PyPlayer (jamais un dossier non vide ni le dossier de données).
    for folder in (home / "playlists" / "backups", home / "playlists"):
        try:
            folder.rmdir()
        except OSError:
            pass
    return report


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("o", "Ko", "Mo", "Go"):
        if value < 1024 or unit == "Go":
            return f"{value:.0f} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} o"

