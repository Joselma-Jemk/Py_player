"""Couleurs, icônes et police d'icônes de l'interface (look inchangé)."""

from __future__ import annotations

import functools
import logging

from PySide6 import QtCore, QtGui, QtWidgets

from pyplayer.api import paths

logger = logging.getLogger(__name__)

# Couleurs
PRINCIPAL_COLOR = "#1c1c1e"
SECONDARY_COLOR = "#2c2c2e"
THIRD_COLOR = "#3a3a3c"
HOVER_COLOR = "#48484a"
PRESSED_COLOR = "#636366"
PRINCIPAL_TEXT_COLOR = "#f2f2f7"
OK_ONE_COLOR = "#2196F3"
ACCENT_COLOR = "#ff3b30"
GREEN = "#4CAF50"

# Codes Material Symbols (extraits de la police embarquée)
GLYPHS: dict[str, str] = {
    "play": "", "pause": "", "stop": "", "skip_next": "", "skip_previous": "",
    "repeat": "", "repeat_one": "", "shuffle": "", "block": "",
    "volume_up": "", "volume_down": "", "volume_mute": "", "volume_off": "",
    "fullscreen": "", "fullscreen_exit": "", "playlist_play": "", "playlist_add": "",
    "delete": "", "folder_open": "", "file_open": "", "add": "", "remove": "",
    "close": "", "settings": "", "info": "", "help": "", "keyboard": "",
    "subtitles": "", "closed_caption": "", "speed": "", "photo_camera": "",
    "content_copy": "", "open_in_new": "", "sort": "", "schedule": "",
    "history": "", "search": "", "link": "", "laps": "", "aspect_ratio": "",
    "fit_screen": "", "keep": "", "devices": "", "headphones": "",
    "refresh": "", "save": "", "upload_file": "", "download": "", "edit": "",
    "check": "", "arrow_upward": "", "arrow_downward": "", "audio_file": "",
    "movie": "", "queue_music": "", "tune": "", "language": "",
    "drive_file_move": "", "clear_all": "", "check_circle": "",
}

_FONT_FAMILY: str | None = None


def icon_font_family() -> str:
    """Charge la police d'icônes une seule fois ; chaîne vide si indisponible."""
    global _FONT_FAMILY
    if _FONT_FAMILY is None:
        _FONT_FAMILY = ""
        font_id = QtGui.QFontDatabase.addApplicationFont(str(paths.font_path()))
        families = QtGui.QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            _FONT_FAMILY = families[0]
        else:
            logger.warning("Police d'icônes introuvable : %s", paths.font_path())
    return _FONT_FAMILY


def load_icon_font(size: int = 14, *, bold: bool = False) -> QtGui.QFont:
    """Police d'icônes ; ``bold`` épaissit les glyphes (boutons de lecture)."""
    family = icon_font_family()
    font = QtGui.QFont(family) if family else QtGui.QFont()
    font.setPointSize(size)
    if bold:
        font.setWeight(QtGui.QFont.Weight.Bold)
        try:   # la police est variable : on règle vraiment l'axe de graisse (Qt ≥ 6.7), sinon l'épaississement serait invisible
            font.setVariableAxis(QtGui.QFont.Tag("wght"), 700.0)
            font.setVariableAxis(QtGui.QFont.Tag("GRAD"), 120.0)
        except (AttributeError, TypeError):
            pass
    return font


@functools.lru_cache(maxsize=None)
def icon_path(name: str, variant: str = "light") -> str:
    """Chemin d'une icône PNG (variante claire par défaut), chaîne vide si absente."""
    for folder in (variant, "dark" if variant == "light" else "light"):
        candidate = paths.icons_dir() / folder / f"{name}.png"
        if candidate.is_file():
            return str(candidate)
    return ""


def icon(name: str) -> QtGui.QIcon:
    """Icône de menu : PNG existant, sinon glyphe de la police rendu en blanc (même taille/teinte que les PNG)."""
    png = icon_path(name)
    if png:
        return QtGui.QIcon(png)
    return _glyph_icon(name)


@functools.lru_cache(maxsize=None)
def _glyph_icon(name: str, size: int = 24, color: str = "#ffffff") -> QtGui.QIcon:
    glyph = GLYPHS.get(name)
    family = icon_font_family()
    if not glyph or not family:
        return QtGui.QIcon()
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
    font = QtGui.QFont(family)
    font.setPixelSize(int(size * 0.85))
    painter.setFont(font)
    painter.setPen(QtGui.QColor(color))
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, glyph)
    painter.end()
    return QtGui.QIcon(pixmap)


def app_icon() -> QtGui.QIcon:
    return QtGui.QIcon(str(paths.app_icon_path()))


def dark_palette() -> QtGui.QPalette:
    """Palette sombre complète, indépendante du thème du système.

    Sans elle, tout widget qui n'a pas de feuille de style propre (sous-menus, menus contextuels,
    boîtes de dialogue) retombait sur la palette claire de Windows : fond blanc, texte clair."""
    role = QtGui.QPalette.ColorRole
    group = QtGui.QPalette.ColorGroup
    palette = QtGui.QPalette()
    colors = {
        role.Window: SECONDARY_COLOR,
        role.WindowText: PRINCIPAL_TEXT_COLOR,
        role.Base: PRINCIPAL_COLOR,
        role.AlternateBase: SECONDARY_COLOR,
        role.Text: PRINCIPAL_TEXT_COLOR,
        role.Button: THIRD_COLOR,
        role.ButtonText: PRINCIPAL_TEXT_COLOR,
        role.BrightText: "#ffffff",
        role.ToolTipBase: SECONDARY_COLOR,
        role.ToolTipText: PRINCIPAL_TEXT_COLOR,
        role.PlaceholderText: "#8e8e93",
        role.Highlight: GREEN,
        role.HighlightedText: "#ffffff",
        role.Link: OK_ONE_COLOR,
        role.Light: HOVER_COLOR,
        role.Midlight: THIRD_COLOR,
        role.Mid: SECONDARY_COLOR,
        role.Dark: PRINCIPAL_COLOR,
        role.Shadow: "#000000",
    }
    for color_role, color in colors.items():
        palette.setColor(color_role, QtGui.QColor(color))
    disabled = QtGui.QColor("#666666")
    for color_role in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(group.Disabled, color_role, disabled)
    return palette


def apply_dark_theme(app: QtWidgets.QApplication) -> None:
    """Impose le thème sombre à toute l'application, quel que soit le thème du système.

    Le style Fusion est le même sur tous les systèmes et respecte entièrement la palette ; le style
    natif de Windows, lui, peignait ses propres menus clairs."""
    app.setStyle("Fusion")
    app.setPalette(dark_palette())


def tooltip_html(text: str, color: str = GREEN) -> str:
    """Infobulle au style de l'application."""
    return (
        "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; "
        "border: 1px solid rgba(76, 175, 80, 0.3);'>"
        f"<b style='color:{color}; font-size: 12px;'>{text}</b></div>"
    )
