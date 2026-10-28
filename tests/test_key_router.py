"""Les flèches du lecteur marchent quel que soit le widget qui a le focus (src/pyplayer/ui/key_router.py)."""

import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtTest import QTest

from pyplayer.ui import key_router

K = QtCore.Qt.Key
M = QtCore.Qt.KeyboardModifier


# ───────────────────────── la décision, sans fenêtre ─────────────────────────

@pytest.mark.parametrize("key", [K.Key_Left, K.Key_Right, K.Key_Up, K.Key_Down])
def test_sans_focus_ou_sur_un_widget_ordinaire_les_fleches_pilotent_le_lecteur(qapp, key):
    assert key_router.wants_key(key, M.NoModifier, None)
    assert key_router.wants_key(key, M.ShiftModifier, QtWidgets.QPushButton())


@pytest.mark.parametrize("champ", [
    QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit,
    QtWidgets.QSpinBox, QtWidgets.QComboBox,
])
@pytest.mark.parametrize("key", [K.Key_Left, K.Key_Right, K.Key_Up, K.Key_Down])
def test_dans_un_champ_de_saisie_on_ne_vole_aucune_fleche(qapp, champ, key):
    assert not key_router.wants_key(key, M.NoModifier, champ())


def test_dans_une_liste_haut_et_bas_naviguent_mais_gauche_et_droite_pilotent_le_lecteur(qapp):
    liste = QtWidgets.QListWidget()
    assert not key_router.wants_key(K.Key_Up, M.NoModifier, liste)
    assert not key_router.wants_key(K.Key_Down, M.NoModifier, liste)
    assert key_router.wants_key(K.Key_Left, M.NoModifier, liste)
    assert key_router.wants_key(K.Key_Right, M.NoModifier, liste)


@pytest.mark.parametrize("modificateur", [M.ControlModifier, M.AltModifier, M.MetaModifier])
def test_ctrl_alt_meta_restent_aux_raccourcis_des_menus(modificateur):
    assert not key_router.wants_key(K.Key_Right, modificateur, None)
    assert not key_router.wants_key(K.Key_Right, modificateur | M.ShiftModifier, None)


@pytest.mark.parametrize("key", [K.Key_Space, K.Key_M, K.Key_F, K.Key_Return, K.Key_A])
def test_les_autres_touches_ne_sont_pas_les_siennes(key):
    assert not key_router.wants_key(key, M.NoModifier, None)


# ───────────────────────── avec la vraie fenêtre ─────────────────────────

@pytest.fixture
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def fenetre(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "userhome"))
    from pyplayer.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    win.activateWindow()
    qapp.processEvents()
    appels: list[str] = []
    monkeypatch.setattr(win.player_widget, "seek_relative", lambda ms: appels.append(f"seek{ms:+d}"))
    monkeypatch.setattr(win, "change_volume", lambda delta: appels.append(f"vol{delta:+d}"))
    win.appels = appels
    yield win
    win.close()
    win.deleteLater()
    qapp.processEvents()


def _appuyer(qapp, widget, key, modificateur=M.NoModifier):
    QTest.keyClick(widget, key, modificateur)
    qapp.processEvents()


def test_le_dock_detache_garde_avance_recul_et_volume(qapp, fenetre):
    """Le bug : détaché, le dock est une autre fenêtre, les flèches n'arrivaient jamais au lecteur."""
    dock = fenetre.dock_widget
    dock.setFloating(True)
    dock.show()
    dock.activateWindow()
    qapp.processEvents()
    fenetre.dock_widget.lstw.clearFocus()
    for key in (K.Key_Left, K.Key_Right):
        _appuyer(qapp, dock, key)
    _appuyer(qapp, dock, K.Key_Right, M.ShiftModifier)
    assert fenetre.appels == ["seek-10000", "seek+10000", "seek+60000"]


def test_une_liste_remplie_garde_haut_et_bas_mais_gauche_droite_marchent(qapp, fenetre):
    liste = fenetre.dock_widget.lstw
    for i in range(5):
        liste.addItem(f"Titre {i}")
    liste.setCurrentRow(2)
    liste.setFocus()
    qapp.processEvents()
    _appuyer(qapp, liste, K.Key_Down)
    assert fenetre.appels == []                 # ↓ a navigué dans la liste
    assert liste.currentRow() == 3
    _appuyer(qapp, liste, K.Key_Right)
    assert fenetre.appels == ["seek+10000"]


def test_dans_un_champ_de_saisie_la_fleche_deplace_le_curseur_pas_la_lecture(qapp, fenetre):
    champ = QtWidgets.QLineEdit("texte")
    champ.setParent(fenetre)
    champ.show()
    champ.setFocus()
    qapp.processEvents()
    _appuyer(qapp, champ, K.Key_Left)
    assert fenetre.appels == []
    assert champ.cursorPosition() == 4


def test_une_boite_de_dialogue_active_ne_pilote_pas_le_lecteur(qapp, fenetre, monkeypatch):
    dialogue = QtWidgets.QDialog(fenetre)
    monkeypatch.setattr(QtWidgets.QApplication, "activeWindow", staticmethod(lambda: dialogue))
    evenement = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, K.Key_Left, M.NoModifier)
    assert fenetre.key_router.eventFilter(dialogue, evenement) is False
    assert fenetre.appels == []


def test_un_double_clic_sur_un_titre_rend_le_focus_au_lecteur(qapp, fenetre, monkeypatch):
    from pyplayer.ui.widget.dock_widget import VideoListItem

    monkeypatch.setattr(fenetre, "play_video", lambda *a, **k: None)
    monkeypatch.setattr(fenetre.active_playlist, "set_current", lambda *a, **k: None)
    item = VideoListItem.__new__(VideoListItem)
    item.video = object()
    fenetre.dock_widget.lstw.setFocus()
    fenetre.double_click(item)
    qapp.processEvents()
    assert qapp.focusWidget() is fenetre.player_widget


def test_la_fenetre_reprend_le_focus_au_lecteur_quand_rien_ne_l_a(qapp, fenetre):
    fenetre.clearFocus()
    fenetre.focus_player()
    assert qapp.focusWidget() is fenetre.player_widget
