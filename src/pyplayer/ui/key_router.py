"""LES FLÈCHES DU LECTEUR, OÙ QUE SOIT LE FOCUS.

Avant, avance/recul et volume ne marchaient que si la touche REMONTAIT jusqu'à la fenêtre principale.
Elle n'y arrivait pas quand :
* le dock de playlist était détaché (c'est une autre fenêtre : elle ne remonte jamais) ;
* une liste remplie avait le focus (elle garde ↑ ↓ pour naviguer) — et le focus y reste après un clic.

Le routeur voit les touches au niveau de l'application, avant le widget qui a le focus. Il laisse
passer, sans y toucher :
* les champs de saisie (texte, nombre, liste déroulante) : on y tape, on n'y pilote pas le lecteur ;
* ↑ ↓ dans une liste : naviguer reste le sens naturel de ces touches ;
* tout ce qui porte Ctrl, Alt ou Méta (les raccourcis des menus s'en chargent) ;
* les menus déroulants ouverts et les boîtes de dialogue (autre fenêtre active)."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

_KEY = QtCore.Qt.Key
ARROWS = (_KEY.Key_Left, _KEY.Key_Right, _KEY.Key_Up, _KEY.Key_Down)
_VERTICAL = (_KEY.Key_Up, _KEY.Key_Down)
_NO_PLAYER_MODIFIERS = (
    QtCore.Qt.KeyboardModifier.ControlModifier
    | QtCore.Qt.KeyboardModifier.AltModifier
    | QtCore.Qt.KeyboardModifier.MetaModifier
)
_TEXT_INPUTS = (
    QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit,
    QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox,
)


def wants_key(key, modifiers, focus: QtWidgets.QWidget | None) -> bool:
    """Cette touche pilote-t-elle le lecteur, étant donné le widget qui a le focus ?"""
    if key not in ARROWS or modifiers & _NO_PLAYER_MODIFIERS:
        return False
    if isinstance(focus, _TEXT_INPUTS):
        return False
    return not (key in _VERTICAL and isinstance(focus, QtWidgets.QAbstractItemView))


class PlayerKeyRouter(QtCore.QObject):
    """Filtre d'application : envoie les flèches à `window.handle_navigation_key`.

    Enfant de la fenêtre : détruit avec elle, Qt retire alors lui-même le filtre."""

    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        QtWidgets.QApplication.instance().installEventFilter(self)

    def _own_windows(self) -> tuple:
        """La fenêtre principale et son dock quand il est détaché — jamais une boîte de dialogue."""
        dock = getattr(self._window, "dock_widget", None)
        return (self._window, dock) if dock is not None and dock.isFloating() else (self._window,)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 -- surcharge Qt
        if event.type() != QtCore.QEvent.Type.KeyPress:
            return False
        app = QtWidgets.QApplication
        if app.activePopupWidget() is not None or app.activeWindow() not in self._own_windows():
            return False
        if not wants_key(event.key(), event.modifiers(), app.focusWidget()):
            return False
        return bool(self._window.handle_navigation_key(event.key(), event.modifiers()))
