"""Centralized runtime configuration for PyPlayer."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class PyPlayerConfig:
    """Holds project and runtime configuration."""

    def __init__(self, current_file: Path) -> None:
        self.current_file = current_file.resolve()
        self.project_root = self._find_project_root(self.current_file)
        self.main_dir = self.project_root / "src" / "main"
        self.icons_dir = self.main_dir / "icons"
        self.resources_dir = self.main_dir / "resources"

        self.default_preferences: dict[str, str | int] = {
            "icon_number": 1,
            "icon_name": "pyplayer",
            "theme": "light",
        }
        self.valid_themes = {"light", "dark"}

        self.runtime_dir = self._ensure_runtime_dir()
        self.log_file_path = self.runtime_dir / "pyplayer-runtime.log"
        self.logger = self._build_logger()

        self.preferences = self.load_preferences()

    def _find_project_root(self, start_path: Path) -> Path:
        marker_sets = [
            ("requirements.txt", "README.md"),
            ("requirements.txt",),
        ]

        for candidate in [start_path, *start_path.parents]:
            for marker_set in marker_sets:
                if all((candidate / marker).exists() for marker in marker_set):
                    return candidate

        raise FileNotFoundError(
            f"Impossible de trouver la racine projet depuis {start_path}. "
            "Marqueurs attendus: requirements.txt (et idealement README.md)."
        )

    def _ensure_runtime_dir(self) -> Path:
        runtime_dir = Path.home() / ".pyplayer"
        try:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            return runtime_dir
        except (PermissionError, OSError):
            fallback_dir = Path("/tmp/.pyplayer")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return fallback_dir

    def _build_logger(self) -> logging.Logger:
        logger = logging.getLogger("pyplayer.constant")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        has_rotating_handler = any(
            isinstance(handler, RotatingFileHandler)
            and Path(getattr(handler, "baseFilename", "")) == self.log_file_path
            for handler in logger.handlers
        )

        if not has_rotating_handler:
            file_handler = RotatingFileHandler(
                self.log_file_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
            )
            logger.addHandler(file_handler)

        return logger

    def _normalize_theme(self, value: object) -> str:
        normalized = str(value).strip().lower()
        if normalized in self.valid_themes:
            return normalized

        self.logger.warning(
            "Theme invalide '%s', fallback '%s'.",
            value,
            self.default_preferences["theme"],
        )
        return str(self.default_preferences["theme"])

    def _normalize_icon_number(self, value: object) -> int:
        try:
            normalized = int(value)
            if normalized >= 1:
                return normalized
            raise ValueError("icon_number must be >= 1")
        except (TypeError, ValueError):
            self.logger.warning(
                "icon_number invalide '%s', fallback %s.",
                value,
                self.default_preferences["icon_number"],
            )
            return int(self.default_preferences["icon_number"])

    def _normalize_icon_name(self, value: object) -> str:
        normalized = str(value).strip()
        if normalized:
            return normalized

        self.logger.warning(
            "icon_name vide/invalide '%s', fallback '%s'.",
            value,
            self.default_preferences["icon_name"],
        )
        return str(self.default_preferences["icon_name"])

    def load_preferences(self) -> dict[str, str | int]:
        preferences_path = self.resources_dir / "preferences.json"
        if not preferences_path.exists():
            return self.default_preferences.copy()

        try:
            with preferences_path.open("r", encoding="utf-8") as file_handle:
                loaded = json.load(file_handle)
                if not isinstance(loaded, dict):
                    return self.default_preferences.copy()

                return {
                    "icon_number": self._normalize_icon_number(
                        loaded.get("icon_number", self.default_preferences["icon_number"])
                    ),
                    "icon_name": self._normalize_icon_name(
                        loaded.get("icon_name", self.default_preferences["icon_name"])
                    ),
                    "theme": self._normalize_theme(
                        loaded.get("theme", self.default_preferences["theme"])
                    ),
                }
        except (json.JSONDecodeError, OSError, ValueError, TypeError) as error:
            self.logger.warning("preferences.json invalide (%s), fallback par defaut.", error)
            return self.default_preferences.copy()


CONFIG = PyPlayerConfig(Path(__file__).resolve())
