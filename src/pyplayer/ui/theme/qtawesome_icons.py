"""QtAwesome icon helpers for PyPlayer widgets."""

from __future__ import annotations

from PySide6 import QtGui

from .colors import ACCENT_COLOR, PRINCIPAL_TEXT_COLOR

try:
    import qtawesome as qta
except ImportError:  # pragma: no cover - dependency is expected at runtime
    qta = None


DEFAULT_ICON_COLOR = PRINCIPAL_TEXT_COLOR
ACTIVE_ICON_COLOR = "#ffffff"
DISABLED_ICON_COLOR = "#70757d"
MUTED_ICON_COLOR = "#ff6b6b"


def _empty_icon() -> QtGui.QIcon:
    return QtGui.QIcon()


def make_icon(
    name: str,
    *,
    color: str = DEFAULT_ICON_COLOR,
    color_active: str = ACTIVE_ICON_COLOR,
    color_selected: str | None = None,
    color_disabled: str = DISABLED_ICON_COLOR,
    scale_factor: float = 1.0,
) -> QtGui.QIcon:
    """Return a QtAwesome icon with sensible defaults."""
    if qta is None:
        return _empty_icon()

    return qta.icon(
        name,
        color=color,
        color_active=color_active,
        color_selected=color_selected or color_active,
        color_disabled=color_disabled,
        scale_factor=scale_factor,
    )


def playback_icon(kind: str) -> QtGui.QIcon:
    mapping = {
        "play": "fa6s.play",
        "pause": "fa6s.pause",
        "stop": "fa6s.stop",
        "next": "fa6s.forward-step",
        "previous": "fa6s.backward-step",
    }
    return make_icon(mapping[kind], color=DEFAULT_ICON_COLOR, color_active=ACTIVE_ICON_COLOR, scale_factor=1.0)


def playlist_action_icon(kind: str) -> QtGui.QIcon:
    mapping = {
        "show_playlist": "mdi6.playlist-music",
        "add": "fa6s.plus",
        "remove": "fa6s.xmark",
        "save_playlist": "mdi6.playlist-plus",
        "delete_playlist": "mdi6.trash-can-outline",
    }
    color = ACCENT_COLOR if kind in {"show_playlist", "add", "save_playlist"} else "#ff6b6b"
    return make_icon(mapping[kind], color=color, color_active=ACTIVE_ICON_COLOR, scale_factor=1.0)


def volume_icon(level: int, *, muted: bool = False) -> QtGui.QIcon:
    if muted or level <= 0:
        return make_icon("mdi6.volume-off", color=MUTED_ICON_COLOR, color_active="#ffd4d4")
    if level < 33:
        return make_icon("mdi6.volume-low", color=ACCENT_COLOR, color_active=ACTIVE_ICON_COLOR)
    if level < 66:
        return make_icon("mdi6.volume-medium", color=ACCENT_COLOR, color_active=ACTIVE_ICON_COLOR)
    return make_icon("mdi6.volume-high", color=ACCENT_COLOR, color_active=ACTIVE_ICON_COLOR)


def play_mode_icon(mode_name: str) -> QtGui.QIcon:
    mapping = {
        "NORMAL": "fa6s.list",
        "LOOP_ONE": "mdi6.repeat-once",
        "LOOP_ALL": "mdi6.repeat",
        "SHUFFLE": "mdi6.shuffle",
    }
    return make_icon(mapping[mode_name], color=ACCENT_COLOR, color_active=ACTIVE_ICON_COLOR, scale_factor=1.0)
