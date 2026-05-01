"""Compatibility wrapper for configuration.

The implementation now lives under `src.pyplayer.infrastructure.config`.
"""

from src.pyplayer.infrastructure.config.settings import CONFIG, PyPlayerConfig

__all__ = ["CONFIG", "PyPlayerConfig"]
