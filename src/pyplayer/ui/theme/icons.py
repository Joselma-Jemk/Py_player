"""UI icon resolution and icon name constants."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.pyplayer.infrastructure.config.settings import CONFIG

ICONS_DIR = CONFIG.icons_dir
PROJECT_ROOT = CONFIG.project_root

_LIGHT_ICON_NAMES = [
    "add", "audio_file", "dark_mode", "exit", "forward_ten", "fullscreen",
    "fullscreen_exit", "help", "infos", "keyboard", "light_mode", "loop",
    "metadata", "music_history", "music_note", "open_file", "open_folder",
    "pause", "play", "playlist", "playlist_add", "playlist_check",
    "playlist_remove", "recent_files", "remove", "delete", "replay_ten",
    "save", "upload", "shuffle", "skip_next", "skip_previous", "stop",
    "volume_off", "volume_up", "minimize", "close", "check_circle",
]

_DARK_ICON_NAMES = [
    "add", "audio_file", "dark_mode", "exit", "forward_ten", "fullscreen",
    "fullscreen_exit", "help", "infos", "keyboard", "light_mode", "loop",
    "metadata", "music_history", "music_note", "open_file", "open_folder",
    "pause", "play", "playlist", "playlist_add", "playlist_check",
    "playlist_remove", "recent_files", "remove", "replay_ten", "save",
    "upload", "shuffle", "skip_next", "skip_previous", "stop", "volume_off",
    "volume_up",
]

_ICON_CONST_ALIASES = {
    "check_circle": "PLAYED",
}


def _build_icon_specs() -> dict[str, tuple[str, str]]:
    specs: dict[str, tuple[str, str]] = {}
    for icon_name in _LIGHT_ICON_NAMES:
        const_suffix = _ICON_CONST_ALIASES.get(icon_name, icon_name.upper())
        specs[f"ICON_{const_suffix}"] = (icon_name, "light")
    for icon_name in _DARK_ICON_NAMES:
        const_suffix = _ICON_CONST_ALIASES.get(icon_name, icon_name.upper())
        specs[f"ICON_DARK_{const_suffix}"] = (icon_name, "dark")
    return specs


_ICON_SPECS = _build_icon_specs()
_ICON_CACHE: dict[tuple[str, str], str] = {}
_LAZY_MISC_CACHE: dict[str, str] = {}


def _get_cached_icon_path(icon_name: str, theme: str) -> str:
    cache_key = (icon_name, theme)
    if cache_key not in _ICON_CACHE:
        _ICON_CACHE[cache_key] = get_icon_path(icon_name, theme)
    return _ICON_CACHE[cache_key]


def get_icon_path(icon_name: str, theme: str | None = None) -> str:
    """Return the path to an icon based on theme."""
    selected_theme = (theme or str(CONFIG.preferences.get("theme", "light"))).lower()
    if selected_theme not in {"light", "dark"}:
        selected_theme = "light"

    icon_filename = f"{icon_name}.png"
    primary_dir = ICONS_DIR / selected_theme
    alternate_dir = ICONS_DIR / ("dark" if selected_theme == "light" else "light")

    direct_primary = primary_dir / icon_filename
    if direct_primary.exists():
        return str(direct_primary)

    found_primary = _find_path_impl(
        name=icon_filename,
        parent_dir=primary_dir,
        ignore_case=True,
        safe=True,
        allowed_root=ICONS_DIR,
    )
    if isinstance(found_primary, Path):
        return str(found_primary)

    direct_alternate = alternate_dir / icon_filename
    if direct_alternate.exists():
        return str(direct_alternate)

    found_alternate = _find_path_impl(
        name=icon_filename,
        parent_dir=alternate_dir,
        ignore_case=True,
        safe=True,
        allowed_root=ICONS_DIR,
    )
    if isinstance(found_alternate, Path):
        return str(found_alternate)

    return ""


def get_current_theme_icon(icon_name: str) -> str:
    """Return the icon for the current theme."""
    theme = str(CONFIG.preferences.get("theme", "light"))
    return _get_cached_icon_path(icon_name, theme)


def get_icon_directory() -> str:
    """Return the app icon path."""
    if "icon_directory" in _LAZY_MISC_CACHE:
        return _LAZY_MISC_CACHE["icon_directory"]
    try:
        resolved = py_player_icone()
    except FileNotFoundError:
        resolved = ""
    _LAZY_MISC_CACHE["icon_directory"] = resolved
    return resolved


def py_player_icone(number: int | None = None) -> str:
    """Return path to player icon."""
    prefs = CONFIG.preferences
    icon_number = number if number is not None else int(prefs.get("icon_number", 1))
    icon_name = str(prefs.get("icon_name", "pyplayer"))

    base_names = [icon_name, "pyplayer"]
    extensions = [".png", ".ico", ".jpg", ".jpeg", ".svg"]

    for base_name in base_names:
        candidates = (
            [f"{base_name}_{icon_number}{ext}" for ext in extensions]
            + [f"{base_name}{ext}" for ext in extensions]
        )
        for filename in candidates:
            icon_path = ICONS_DIR / filename
            if icon_path.exists():
                return str(icon_path)
            found = _find_path_impl(
                name=filename,
                is_file=True,
                parent_dir=PROJECT_ROOT,
                ignore_case=True,
                safe=True,
                allowed_root=PROJECT_ROOT,
            )
            if isinstance(found, Path):
                return str(found)

    raise FileNotFoundError(f"Aucune icône trouvée pour '{icon_name}' (numéro: {icon_number})")


def _find_path_impl(
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
    """Internal find_path implementation (mirrors constant.find_path)."""
    from src.pyplayer.infrastructure.filesystem.resource_locator import (
        find_path as _fp,
    )

    return _fp(
        name=name,
        is_file=is_file,
        parent_dir=parent_dir,
        max_depth=max_depth,
        extensions=extensions,
        ignore_case=ignore_case,
        first_only=first_only,
        safe=safe,
        default=default,
        allowed_root=allowed_root,
    )


def __getattr__(name: str) -> str:
    if name in _ICON_SPECS:
        icon_name, theme = _ICON_SPECS[name]
        return _get_cached_icon_path(icon_name, theme)
    if name == "icon_directory":
        return get_icon_directory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
