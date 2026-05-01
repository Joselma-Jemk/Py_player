"""PyPlayer legacy facade — delegates to modern modules."""

from __future__ import annotations

import os
from pathlib import Path

from src.pyplayer.domain.media.media_formats import SUPPORTED_AUDIO_FORMATS, VIDEO_EXTENSIONS
from src.pyplayer.infrastructure.config.settings import CONFIG
from src.pyplayer.ui.theme.colors import (
    ACCENT_COLOR,
    HOVER_COLOR,
    OK_ONE_COLOR,
    PRESSED_COLOR,
    PRINCIPAL_COLOR,
    PRINCIPAL_TEXT_COLOR,
    SECONDARY_COLOR,
    THIRD_COLOR,
)
from src.pyplayer.ui.theme.icons import (
    py_player_icone as _py_player_icone_impl,
    get_icon_path as _get_icon_path_impl,
    get_current_theme_icon as _get_current_theme_icon_impl,
    _ICON_SPECS,
    _ICON_CACHE,
    _LIGHT_ICON_NAMES,
    _DARK_ICON_NAMES,
    _ICON_CONST_ALIASES,
)
from src.pyplayer.infrastructure.filesystem.resource_locator import (
    find_path as _find_path_impl,
)


# --- Path / config proxies ---
PROJECT_ROOT = CONFIG.project_root
MAIN_DIR = CONFIG.main_dir
ICONS_DIR = CONFIG.icons_dir
RESOURCES_DIR = CONFIG.resources_dir
RUNTIME_DIR = CONFIG.runtime_dir
LOG_FILE_PATH = CONFIG.log_file_path
LOGGER = CONFIG.logger

# --- Runtime caches (internal, preserve legacy behavior) ---
_FIND_PATH_CACHE: dict[tuple, Path | list[Path] | None] = {}
_LAZY_MISC_CACHE: dict[str, str] = {}


# --- find_path: delegate to resource_locator ---
def find_path(
    name: str,
    is_file: bool = True,
    parent_dir: str | Path | None = None,
    max_depth: int = -1,
    extensions: list[str] | None = None,
    ignore_case: bool = False,
    first_only: bool = True,
    safe: bool = False,
    default: Path | list[Path] | None = None,
    allowed_root: Path | None = None,
) -> Path | list[Path] | None:
    """Recherche récursive — délègue à resource_locator."""
    if safe:
        try:
            return find_path(
                name=name,
                is_file=is_file,
                parent_dir=parent_dir,
                max_depth=max_depth,
                extensions=extensions,
                ignore_case=ignore_case,
                first_only=first_only,
                safe=False,
                default=default,
                allowed_root=allowed_root,
            )
        except (ValueError, FileNotFoundError, PermissionError, OSError) as error:
            if os.getenv("DEBUG_FIND_PATH"):
                LOGGER.warning("find_path('%s') failed: %s", name, error)
            return default

    result = _find_path_impl(
        name=name,
        is_file=is_file,
        parent_dir=parent_dir,
        max_depth=max_depth,
        extensions=extensions,
        ignore_case=ignore_case,
        first_only=first_only,
        safe=False,
        default=default,
        allowed_root=allowed_root,
    )
    return result


# --- Icon helpers: delegate to icons module ---
def py_player_icone(number: int | None = None) -> str:
    """Délègue à src.pyplayer.ui.theme.icons.py_player_icone."""
    return _py_player_icone_impl(number)


def get_icon_path(icon_name: str, theme: str | None = None) -> str:
    """Délègue à src.pyplayer.ui.theme.icons.get_icon_path."""
    return _get_icon_path_impl(icon_name, theme)


def get_current_theme_icon(icon_name: str) -> str:
    """Délègue à src.pyplayer.ui.theme.icons.get_current_theme_icon."""
    return _get_current_theme_icon_impl(icon_name)


def _get_cached_icon_path(icon_name: str, theme: str) -> str:
    cache_key = (icon_name, theme)
    if cache_key not in _ICON_CACHE:
        _ICON_CACHE[cache_key] = get_icon_path(icon_name, theme)
    return _ICON_CACHE[cache_key]


def reset_runtime_caches() -> None:
    """Réinitialise les caches runtime."""
    _FIND_PATH_CACHE.clear()
    _ICON_CACHE.clear()
    _LAZY_MISC_CACHE.clear()


def _get_icon_directory() -> str:
    if "icon_directory" in _LAZY_MISC_CACHE:
        return _LAZY_MISC_CACHE["icon_directory"]
    try:
        resolved = py_player_icone()
    except FileNotFoundError as error:
        LOGGER.warning("Icon directory not found: %s", error)
        resolved = ""
    _LAZY_MISC_CACHE["icon_directory"] = resolved
    return resolved


def _get_chemin_video() -> str:
    if "chemin_video" in _LAZY_MISC_CACHE:
        return _LAZY_MISC_CACHE["chemin_video"]
    chemin_video_path = find_path(
        "samplevideo.mp4",
        safe=True,
        default=None,
        allowed_root=PROJECT_ROOT,
    )
    resolved = str(chemin_video_path) if isinstance(chemin_video_path, Path) else ""
    _LAZY_MISC_CACHE["chemin_video"] = resolved
    return resolved


def _get_font_dir() -> str:
    if "font_dir" in _LAZY_MISC_CACHE:
        return _LAZY_MISC_CACHE["font_dir"]
    font_path = RESOURCES_DIR / "material-symbols-outlined.ttf"
    resolved = str(font_path) if font_path.exists() else ""
    _LAZY_MISC_CACHE["font_dir"] = resolved
    return resolved


# --- Preferences ---
def load_preferences() -> dict[str, str | int]:
    return CONFIG.load_preferences()


preferences = CONFIG.preferences


# --- Legacy __getattr__ for lazy constants ---
def __getattr__(name: str) -> str:
    if name in _ICON_SPECS:
        icon_name, theme = _ICON_SPECS[name]
        return _get_cached_icon_path(icon_name, theme)

    if name == "icon_directory":
        return _get_icon_directory()

    if name == "chemin_video":
        return _get_chemin_video()

    if name == "font_dir":
        return _get_font_dir()

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def pyplayer_directory() -> Path:
    return RUNTIME_DIR


SEPARATOR_ICON = "⮞"