"""Widget namespace compatibility package."""

from .dock_widget import DeletePlaylistDialog, DockWidget, VideoListItem
from .menu_bar import HelpDialog, MenuBarWidget
from .player import CustomSlider, PlayerWidget
from .statusbar_widget import StatusBar
from .tool_bar import (
    PlayerControlsWidget,
    PlaylistButtonWidget,
    TimeLabelWidget,
    ToolBarWidget,
    VolumeWidget,
)

__all__ = [
    "CustomSlider",
    "DeletePlaylistDialog",
    "DockWidget",
    "HelpDialog",
    "MenuBarWidget",
    "PlayerControlsWidget",
    "PlayerWidget",
    "PlaylistButtonWidget",
    "StatusBar",
    "TimeLabelWidget",
    "ToolBarWidget",
    "VideoListItem",
    "VolumeWidget",
]
