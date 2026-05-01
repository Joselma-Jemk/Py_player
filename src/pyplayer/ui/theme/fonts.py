"""UI font resolution helpers."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui

from src.pyplayer.infrastructure.config.settings import CONFIG

FONTS_DIR = CONFIG.fonts_dir

_LAZY_FONT_CACHE: dict[str, str] = {}

# Global cache for QFont objects to avoid redundant loading
_FONT_DATABASE_CACHE: dict[int, QtGui.QFont] = {}
_FONT_FAMILY_CACHE: dict[str, str] = {}


def get_font_path(font_name: str = "material-symbols-outlined.ttf") -> str:
    """Return the path to a UI font file."""
    if "font_dir" in _LAZY_FONT_CACHE:
        return _LAZY_FONT_CACHE["font_dir"]
    font_path = FONTS_DIR / font_name
    resolved = str(font_path) if font_path.exists() else ""
    _LAZY_FONT_CACHE["font_dir"] = resolved
    return resolved


def find_font(font_name: str = "material-symbols-outlined.ttf") -> Path | None:
    """Return Path to font if it exists, None otherwise."""
    path = FONTS_DIR / font_name
    return path if path.exists() else None


def get_icon_font_path() -> str:
    """Return path to the material-symbols icon font."""
    return get_font_path("material-symbols-outlined.ttf")


def get_icon_font(size: int = 14) -> QtGui.QFont:
    """Return cached icon font for given size.

    This method uses a global cache to avoid redundant loading of the same font
    with different sizes. The font family is loaded once and reused.
    """
    if size in _FONT_DATABASE_CACHE:
        return _FONT_DATABASE_CACHE[size]

    # Load font family once
    if "material-symbols" not in _FONT_FAMILY_CACHE:
        font_path = get_font_path("material-symbols-outlined.ttf")
        if not font_path:
            return QtGui.QFont()  # Fallback to default font

        font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
        families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if families:
            _FONT_FAMILY_CACHE["material-symbols"] = families[0]

    # Create font for requested size
    family = _FONT_FAMILY_CACHE.get("material-symbols", "Material Symbols Outlined")
    font = QtGui.QFont(family)
    font.setPointSize(size)
    _FONT_DATABASE_CACHE[size] = font
    return font


def __getattr__(name: str) -> str:
    if name == "font_dir":
        return get_font_path()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
