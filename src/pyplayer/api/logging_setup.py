"""Configuration du logging applicatif (fichier tournant + console)."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_NAME = "pyplayer.log"
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(log_dir: Path, *, debug: bool = False) -> Path:
    """Configure le logger racine ``pyplayer`` (idempotent). Retourne le chemin du fichier de log."""
    log_path = Path(log_dir) / _LOG_NAME
    logger = logging.getLogger("pyplayer")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    if not any(getattr(h, "_pyplayer_file", False) for h in logger.handlers):
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(logging.Formatter(_FORMAT))
            file_handler._pyplayer_file = True  # type: ignore[attr-defined]
            logger.addHandler(file_handler)
        except OSError:
            pass

    if not any(getattr(h, "_pyplayer_console", False) for h in logger.handlers):
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.DEBUG if debug else logging.WARNING)
        console.setFormatter(logging.Formatter(_FORMAT))
        console._pyplayer_console = True  # type: ignore[attr-defined]
        logger.addHandler(console)

    return log_path
