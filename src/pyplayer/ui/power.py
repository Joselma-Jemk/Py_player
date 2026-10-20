"""Empêche la mise en veille / l'économiseur d'écran pendant la lecture vidéo (Windows, macOS, Linux)."""

from __future__ import annotations

import logging
import subprocess
import sys

from pyplayer import APP_NAME

logger = logging.getLogger(__name__)

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


class SleepInhibitor:
    def __init__(self) -> None:
        self._active = False
        self._cookie: int | None = None
        self._process: subprocess.Popen | None = None

    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        try:
            if sys.platform.startswith("win"):
                self._windows(active)
            elif sys.platform == "darwin":
                self._macos(active)
            else:
                self._linux(active)
            self._active = active
        except Exception as error:  # jamais bloquant pour la lecture
            logger.debug("Inhibition de veille indisponible : %s", error)

    # ------------------------------------------------------------------ plateformes
    @staticmethod
    def _windows(active: bool) -> None:
        import ctypes
        flags = _ES_CONTINUOUS | (_ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED if active else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)  # type: ignore[attr-defined]

    def _macos(self, active: bool) -> None:
        if active:
            self._process = subprocess.Popen(["caffeinate", "-d", "-i"])
        elif self._process:
            self._process.terminate()
            self._process = None

    def _linux(self, active: bool) -> None:
        from PySide6 import QtDBus
        bus = QtDBus.QDBusConnection.sessionBus()
        interface = QtDBus.QDBusInterface(
            "org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver", bus)
        if not interface.isValid():
            raise RuntimeError("service ScreenSaver absent")
        if active:
            reply = interface.call("Inhibit", APP_NAME, "Lecture vidéo")
            args = reply.arguments()
            self._cookie = int(args[0]) if args else None
        elif self._cookie is not None:
            interface.call("UnInhibit", self._cookie)
            self._cookie = None
