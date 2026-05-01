"""Optimized recursive file and folder search with caching."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.pyplayer.infrastructure.config.settings import CONFIG

PROJECT_ROOT = CONFIG.project_root
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
    """Recursive optimized file or folder search by name."""
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


def reset_find_path_cache() -> None:
    """Clear the find_path cache."""
    _FIND_PATH_CACHE.clear()
