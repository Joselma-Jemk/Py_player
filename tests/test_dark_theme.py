"""Thème sombre imposé : les menus ne dépendent pas du thème du système.

Régression : sous Windows en thème clair, les sous-menus (« Vitesse de lecture »…) s'ouvraient sur
fond blanc avec un texte clair, donc illisibles."""

import pytest
from PySide6 import QtGui, QtWidgets

from pyplayer.ui import theme


@pytest.fixture
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def theme_isole(qapp):
    """Rend l'application à son état d'avant : ce thème est global, il ne doit pas fuir."""
    ancien_style = qapp.style().objectName()
    ancienne_palette = QtGui.QPalette(qapp.palette())
    yield
    qapp.setStyle(ancien_style)
    qapp.setPalette(ancienne_palette)


def _luminance(couleur: QtGui.QColor) -> float:
    return 0.299 * couleur.red() + 0.587 * couleur.green() + 0.114 * couleur.blue()


def test_la_palette_est_sombre_pour_les_fonds_et_claire_pour_les_textes():
    palette = theme.dark_palette()
    role = QtGui.QPalette.ColorRole
    for fond in (role.Window, role.Base, role.Button, role.ToolTipBase):
        assert _luminance(palette.color(fond)) < 80
    for texte in (role.WindowText, role.Text, role.ButtonText, role.ToolTipText):
        assert _luminance(palette.color(texte)) > 200


def test_le_texte_desactive_reste_lisible_sur_le_fond_sombre():
    palette = theme.dark_palette()
    desactive = palette.color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text)
    fond = palette.color(QtGui.QPalette.ColorRole.Base)
    assert _luminance(desactive) > _luminance(fond) + 40


def _tous_les_menus(menu, vus=None):
    vus = set() if vus is None else vus
    if id(menu) in vus:
        return
    vus.add(id(menu))
    yield menu
    for action in menu.actions():
        if action.menu() is not None:
            yield from _tous_les_menus(action.menu(), vus)


def test_chaque_menu_de_la_barre_est_sombre_sur_un_systeme_clair(qapp, theme_isole):
    """L'audit complet : système en thème clair + style natif, thème de l'application appliqué.

    Avant le correctif, les 10 menus et sous-menus de la barre sortaient à plus de 70 % de pixels
    blancs (texte clair sur fond blanc). Le test parcourt TOUS les menus réels, récursivement."""
    from pyplayer.ui.widget.menu_bar import MenuBarWidget

    qapp.setStyle("Windows")
    clair = QtGui.QPalette()
    clair.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#f0f0f0"))
    clair.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#ffffff"))
    clair.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#000000"))
    qapp.setPalette(clair)
    theme.apply_dark_theme(qapp)

    barre = MenuBarWidget()
    menus = [m for a in barre.actions() if a.menu() is not None for m in _tous_les_menus(a.menu())]
    assert len(menus) >= 8  # on a bien atteint les sous-menus (vitesse, pistes, format…)
    for menu in menus:
        menu.show()
        qapp.processEvents()
        image = menu.grab().toImage()
        pixel = image.pixelColor(5, image.height() - 5)
        assert _luminance(pixel) < 80, f"menu clair : {menu.title() or menu.objectName() or menu}"
        menu.close()


def test_un_menu_sans_feuille_de_style_est_sombre_avec_son_sous_menu(qapp, theme_isole):
    """Le cas du bug : un sous-menu n'a pas de feuille de style propre, il lit la palette."""
    theme.apply_dark_theme(qapp)
    assert qapp.style().objectName().lower() == "fusion"
    menu = QtWidgets.QMenu()
    menu.addAction("Lire")
    sous_menu = menu.addMenu("Vitesse de lecture")
    sous_menu.addAction("0,5x")
    menu.show()
    qapp.processEvents()
    pixel = menu.grab().toImage().pixelColor(5, menu.height() - 5)
    assert _luminance(pixel) < 80
    assert _luminance(sous_menu.palette().color(QtGui.QPalette.ColorRole.Window)) < 80
    menu.close()
