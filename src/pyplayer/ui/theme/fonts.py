"""UI font resolution helpers."""

from __future__ import annotations

from pathlib import Path

from src.pyplayer.infrastructure.config.settings import CONFIG

RESOURCES_DIR = CONFIG.resources_dir

_LAZY_FONT_CACHE: dict[str, str] = {}


def get_font_path(font_name: str = "material-symbols-outlined.ttf") -> str:
    """Return the path to a UI font file."""
    if "font_dir" in _LAZY_FONT_CACHE:
        return _LAZY_FONT_CACHE["font_dir"]
    font_path = RESOURCES_DIR / font_name
    resolved = str(font_path) if font_path.exists() else ""
    _LAZY_FONT_CACHE["font_dir"] = resolved
    return resolved


def find_font(font_name: str = "material-symbols-outlined.ttf") -> Path | None:
    """Return Path to font if it exists, None otherwise."""
    path = RESOURCES_DIR / font_name
    return path if path.exists() else None


def get_icon_font_path() -> str:
    """Return path to the material-symbols icon font."""
    return get_font_path("material-symbols-outlined.ttf")


def __getattr__(name: str) -> str:
    if name == "font_dir":
        return get_font_path()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
