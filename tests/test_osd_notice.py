"""La carte de notification du lecteur (src/pyplayer/ui/widget/osd.py).

Règles : une pause reste affichée jusqu'à la reprise, avec son titre ; une reprise de lecture
s'annonce puis s'efface ; une action passe devant l'état de lecture, qui revient ensuite ;
l'arrêt efface la carte ; la carte ne reçoit jamais la souris."""

import pytest
from PySide6 import QtCore, QtWidgets
from PySide6.QtTest import QTest

from pyplayer.ui import theme
from pyplayer.ui.widget import osd as osd_module
from pyplayer.ui.widget.osd import (
    PAUSED,
    PLAYBACK_TIMEOUT_MS,
    PLAYING,
    STOPPED,
    Osd,
    playback_notice,
)


@pytest.fixture
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def scene(qapp):
    host = QtWidgets.QWidget()
    host.resize(800, 450)
    host.show()
    osd = Osd(host)
    osd._fade.setDuration(10)
    yield osd
    host.deleteLater()
    qapp.processEvents()


def _attendre(qapp, condition, ms=3000):
    fin = QtCore.QDeadlineTimer(ms)
    while not condition() and not fin.hasExpired():
        QTest.qWait(10)
        qapp.processEvents()
    return condition()


def test_les_annonces_de_lecture_sont_claires():
    assert playback_notice(PLAYING, "Mon film") == ("play", "Lecture", "Mon film")
    assert playback_notice(PAUSED, "Mon film") == ("pause", "Pause", "Mon film")
    assert playback_notice(STOPPED, "") is None


def test_les_icones_annoncees_existent_dans_la_police():
    for glyph in ("play", "pause", "info"):
        assert glyph in theme.GLYPHS


def test_la_pause_affiche_pause_et_le_titre(scene):
    scene.show_playback(PAUSED, "Mon film")
    assert scene.message.isVisible()
    assert scene.message.title.text() == "Pause"
    assert scene.message.sub.text() == "Mon film"
    assert scene.message.sub.isVisible()


def test_la_pause_reste_affichee_sans_minuteur(scene):
    scene.show_playback(PAUSED, "Mon film")
    assert not scene._timer.isActive()           # rien ne l'efface : seule la reprise le fait


def test_la_lecture_affiche_le_titre_puis_s_efface_seule(scene):
    scene.show_playback(PLAYING, "Mon film")
    assert scene.message.title.text() == "Lecture"
    assert scene.message.sub.text() == "Mon film"
    assert scene._timer.isActive() and scene._timer.interval() == PLAYBACK_TIMEOUT_MS


def test_la_reprise_remplace_la_pause(scene):
    scene.show_playback(PAUSED, "Mon film")
    scene.show_playback(PLAYING, "Mon film")
    assert scene.message.title.text() == "Lecture"


def test_l_arret_efface_la_carte(scene):
    scene.show_playback(PAUSED, "Mon film")
    scene.show_playback(STOPPED, "")
    assert not scene.message.isVisible()


def test_une_action_passe_devant_la_pause_puis_la_pause_revient(qapp, scene):
    scene.show_playback(PAUSED, "Mon film")
    scene.show_message("Volume : 50 %", 40)
    assert scene.message.title.text() == "Volume : 50 %"
    assert scene.currentMessage() == "Volume : 50 %"
    assert _attendre(qapp, lambda: scene.currentMessage() == "")
    assert scene.message.title.text() == "Pause" and scene.message.sub.text() == "Mon film"
    assert scene.message.isVisible()


def test_une_reprise_pendant_une_action_s_annonce_apres_elle_et_pas_avant(qapp, scene):
    """Pendant une action, le changement d'état attend : on n'écrase pas le message en cours."""
    scene.show_message("Vitesse : 1,5×", 40)
    scene.show_playback(PLAYING, "Mon film")
    assert scene.message.title.text() == "Vitesse : 1,5×"
    assert _attendre(qapp, lambda: scene.currentMessage() == "")
    assert scene.message.title.text() == "Lecture" and scene.message.sub.text() == "Mon film"


def test_un_reglage_pendant_la_lecture_ne_reannonce_pas_lecture(qapp, scene):
    """Régle le volume en lisant : la carte ne doit pas revenir sur « Lecture » après."""
    scene.show_playback(PLAYING, "Mon film")
    assert _attendre(qapp, lambda: not scene.message.isVisible())   # la reprise s'est effacée seule
    scene.show_message("Volume : 60 %", 40)
    assert _attendre(qapp, lambda: scene.currentMessage() == "")
    assert not scene.message.isVisible()


def test_la_carte_est_centree_en_bas_et_ne_prend_pas_la_souris(scene):
    scene.show_playback(PAUSED, "Mon film")
    host = scene.host
    assert scene.message.parent() is host
    assert scene.message.y() + scene.message.height() <= host.height()
    assert abs(scene.message.x() - (host.width() - scene.message.width()) / 2) <= 1
    assert scene.message.testAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_une_longue_annonce_reste_dans_la_scene(scene):
    scene.show_playback(PAUSED, "Un titre tout à fait interminable " * 12)
    assert scene.message.width() <= scene.host.width() - 2 * osd_module.MARGIN
