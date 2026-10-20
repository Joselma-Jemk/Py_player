"""Lecture/écriture JSON robustes (écriture atomique)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from uuid import uuid4


def write_json_atomic(
    file_path: Path,
    data: object,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
) -> None:
    """Écrit un JSON de manière atomique : fichier temporaire + fsync + remplacement.

    En cas d'échec pendant l'écriture, le fichier cible existant n'est jamais remplacé
    par un contenu partiel.
    """
    target = Path(file_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{uuid4().hex}")

    try:
        with open(temp, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=indent, ensure_ascii=ensure_ascii)
            stream.flush()
            os.fsync(stream.fileno())

        _replace_with_retry(temp, target)
        _fsync_directory(target.parent)
    finally:
        temp.unlink(missing_ok=True)


def read_json(file_path: Path) -> object:
    with open(file_path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _replace_with_retry(source: Path, target: Path, attempts: int = 5) -> None:
    """``os.replace`` peut échouer brièvement sous Windows (antivirus, indexeur) : on réessaie."""
    for attempt in range(attempts):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def _fsync_directory(directory: Path) -> None:
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return  # Windows et certains FS ne permettent pas d'ouvrir un dossier
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
