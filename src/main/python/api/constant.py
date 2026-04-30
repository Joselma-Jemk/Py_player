"""Py player constants and path helpers."""

from __future__ import annotations

import os
from pathlib import Path

from .config import CONFIG


PROJECT_ROOT = CONFIG.project_root
MAIN_DIR = CONFIG.main_dir
ICONS_DIR = CONFIG.icons_dir
RESOURCES_DIR = CONFIG.resources_dir

RUNTIME_DIR = CONFIG.runtime_dir
LOG_FILE_PATH = CONFIG.log_file_path
LOGGER = CONFIG.logger


_FIND_PATH_CACHE: dict[tuple, Path | list[Path] | None] = {}


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
    """Recherche récursive optimisée d'un fichier ou dossier par son nom."""
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

    if not name:
        raise ValueError("Le nom ne peut pas être vide")

    base_dir = (Path(parent_dir) if parent_dir is not None else PROJECT_ROOT).resolve()
    if not base_dir.exists():
        raise FileNotFoundError(f"Le dossier parent n'existe pas : {base_dir}")

    normalized_extensions: tuple[str, ...] | None = None
    if extensions:
        normalized_extensions = tuple(ext.lower() if ignore_case else ext for ext in extensions)

    normalized_allowed_root: Path | None = allowed_root.resolve() if allowed_root is not None else None
    if normalized_allowed_root is not None:
        try:
            base_dir.relative_to(normalized_allowed_root)
        except ValueError:
            raise ValueError(
                f"Le dossier parent '{base_dir}' sort du périmètre autorisé '{normalized_allowed_root}'."
            )

    cache_key = (
        name,
        is_file,
        str(base_dir),
        max_depth,
        normalized_extensions,
        ignore_case,
        first_only,
        str(normalized_allowed_root) if normalized_allowed_root else None,
    )
    if cache_key in _FIND_PATH_CACHE:
        cached = _FIND_PATH_CACHE[cache_key]
        if cached is None:
            return default
        return cached

    search_name = name.lower() if ignore_case else name
    has_extension = "." in name and is_file
    name_without_ext = name.rsplit(".", 1)[0] if has_extension else ""
    if ignore_case:
        name_without_ext = name_without_ext.lower()

    def matches(item: Path) -> bool:
        if is_file != item.is_file():
            return False

        item_name = item.name.lower() if ignore_case else item.name
        name_match = item_name == search_name

        if is_file and has_extension and not name_match:
            item_stem = item.stem.lower() if ignore_case else item.stem
            name_match = item_stem == name_without_ext

        if not name_match:
            return False

        if normalized_extensions and is_file:
            suffix = item.suffix.lower() if ignore_case else item.suffix
            return suffix in normalized_extensions

        return True

    # Fast path: test direct candidate in current base directory
    direct_candidate = base_dir / name
    if direct_candidate.exists() and matches(direct_candidate):
        _FIND_PATH_CACHE[cache_key] = direct_candidate
        return direct_candidate

    results: list[Path] = []

    def search_recursive(current_dir: Path, current_depth: int) -> bool:
        if 0 <= max_depth < current_depth:
            return False

        try:
            for item in current_dir.iterdir():
                try:
                    if matches(item):
                        results.append(item)
                        if first_only:
                            return True

                    if item.is_dir() and search_recursive(item, current_depth + 1):
                        return True
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            return False

        return False

    search_recursive(base_dir, 0)

    if not results:
        _FIND_PATH_CACHE[cache_key] = None
        return default

    if first_only:
        _FIND_PATH_CACHE[cache_key] = results[0]
        return results[0]

    _FIND_PATH_CACHE[cache_key] = results
    return results


def load_preferences() -> dict[str, str | int]:
    return CONFIG.load_preferences()


preferences = CONFIG.preferences


def py_player_icone(number: int | None = None) -> str:
    icon_number = number if number is not None else int(preferences.get("icon_number", 1))
    icon_name = str(preferences.get("icon_name", "pyplayer"))

    base_names = [icon_name, "pyplayer"]
    extensions = [".png", ".ico", ".jpg", ".jpeg", ".svg"]

    for base_name in base_names:
        candidates = [
            f"{base_name}_{icon_number}{ext}" for ext in extensions
        ] + [
            f"{base_name}{ext}" for ext in extensions
        ]

        for filename in candidates:
            icon_path = ICONS_DIR / filename
            if icon_path.exists():
                return str(icon_path)

            found = find_path(
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


def get_icon_path(icon_name: str, theme: str | None = None) -> str:
    """Retourne le chemin d'une icône en fonction du thème (light/dark)."""
    selected_theme = (theme or str(preferences.get("theme", "light"))).lower()
    if selected_theme not in {"light", "dark"}:
        selected_theme = "light"

    icon_filename = f"{icon_name}.png"
    primary_dir = ICONS_DIR / selected_theme
    alternate_dir = ICONS_DIR / ("dark" if selected_theme == "light" else "light")

    direct_primary = primary_dir / icon_filename
    if direct_primary.exists():
        return str(direct_primary)

    found_primary = find_path(
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

    found_alternate = find_path(
        name=icon_filename,
        parent_dir=alternate_dir,
        ignore_case=True,
        safe=True,
        allowed_root=ICONS_DIR,
    )
    if isinstance(found_alternate, Path):
        return str(found_alternate)

    return ""


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


def reset_runtime_caches() -> None:
    """Réinitialise les caches runtime du module constant."""
    _FIND_PATH_CACHE.clear()
    _ICON_CACHE.clear()
    _LAZY_MISC_CACHE.clear()


def _get_cached_icon_path(icon_name: str, theme: str) -> str:
    cache_key = (icon_name, theme)
    if cache_key not in _ICON_CACHE:
        _ICON_CACHE[cache_key] = get_icon_path(icon_name, theme)
    return _ICON_CACHE[cache_key]


def get_current_theme_icon(icon_name: str) -> str:
    """Retourne l'icône pour le thème actuel."""
    theme = str(preferences.get("theme", "light"))
    return _get_cached_icon_path(icon_name, theme)


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


# Constantes de couleur
PRINCIPAL_COLOR = "#1c1c1e"
SECONDARY_COLOR = "#2c2c2e"
THIRD_COLOR = "#3a3a3c"
HOVER_COLOR = "#48484a"
PRESSED_COLOR = "#636366"
PRINCIPAL_TEXT_COLOR = "#f2f2f7"
OK_ONE_COLOR = "#2196F3"
ACCENT_COLOR = "#ff3b30"


# Extensions supportées
VIDEO_EXTENSIONS = {
    ".mp4", ".avi", ".mkv", ".mov", ".webm",
    ".wmv", ".flv", ".mpeg", ".mpg", ".m4v",
}
SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}

SEPARATOR_ICON = "⮞"  # Icône entre nom et progression (modifiable)
