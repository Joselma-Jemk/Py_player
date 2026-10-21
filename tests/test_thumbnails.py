"""Miniatures de la barre de progression : cache (sans Qt), décodage réel, bulle, dessin de la barre."""

import shutil
import subprocess

import pytest
from hypothesis import given, strategies as st
from PySide6 import QtCore, QtGui, QtTest

from pyplayer.ui.widget.thumbnails import MAX_BUCKETS, ThumbnailBubble, ThumbnailCache, ThumbnailProvider
from tests.test_ui import pump, qapp, wait_until, window  # noqa: F401 -- qapp et window sont des fixtures

FFMPEG = shutil.which("ffmpeg")


# ----------------------------------------------------------------- cache : logique pure
def test_bucket_step_is_at_least_one_second_and_covers_the_whole_duration():
    cache = ThumbnailCache()
    cache.reset(30_000)
    assert cache.step_ms == 1000 and cache.bucket(0) == 0 and cache.bucket(29_999) == 29
    cache.reset(3_600_000)                                        # 1 h : 120 tranches de 30 s
    assert cache.step_ms == 30_000 and cache.bucket(3_599_999) == MAX_BUCKETS - 1
    cache.reset(0)
    assert cache.step_ms == 1000 and cache.bucket(5000) == 0


@given(st.integers(1, 10 * 3600 * 1000), st.integers(-5000, 11 * 3600 * 1000))
def test_bucket_and_position_always_stay_inside_the_media(duration, position):
    cache = ThumbnailCache()
    cache.reset(duration)
    bucket = cache.bucket(position)
    assert 0 <= bucket <= MAX_BUCKETS
    assert 0 <= cache.position_of(bucket) < duration
    assert cache.bucket(cache.position_of(bucket)) == bucket      # aller-retour cohérent


def test_cache_is_lru_and_reset_clears_it():
    cache = ThumbnailCache(limit=3)
    cache.reset(60_000)
    for i in range(3):
        cache.put(i, f"img{i}")
    assert cache.get(0) == "img0"                                  # 0 devient le plus récent
    cache.put(3, "img3")                                           # évince le plus ancien : 1
    assert cache.get(1) is None and cache.get(0) == "img0" and len(cache) == 3
    cache.reset(60_000)
    assert len(cache) == 0


# ----------------------------------------------------------------- bulle
def test_bubble_shows_time_and_image_and_never_steals_the_mouse(qapp):
    bubble = ThumbnailBubble()
    bubble.set_time("00:01:30")
    image = QtGui.QImage(176, 99, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor("red"))
    bubble.set_image(image)
    assert bubble.time_label.text() == "00:01:30" and not bubble.image_label.isHidden()
    assert bubble.testAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    bubble.set_image(None)
    assert bubble.image_label.isHidden()
    bubble.deleteLater()


# ----------------------------------------------------------------- décodage réel
@pytest.fixture
def long_video(tmp_path):
    if FFMPEG is None:
        pytest.skip("ffmpeg absent")
    path = tmp_path / "long.mp4"
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=20:size=320x180:rate=10",
                    "-pix_fmt", "yuv420p", str(path)], check=True, timeout=60)
    return path


def test_provider_decodes_distinct_frames_caches_them_and_releases_the_player(qapp, long_video):
    provider = ThumbnailProvider()
    got = {}
    provider.thumbnail_ready.connect(lambda bucket, image: got.__setitem__(bucket, image))
    provider.set_source(str(long_video), 20_000)
    provider.request(2_000)
    assert wait_until(qapp, lambda: 2 in got, 15), "aucune miniature livrée pour 2 s"
    provider.request(15_000)
    assert wait_until(qapp, lambda: 15 in got, 15), "aucune miniature livrée pour 15 s"
    assert got[2].width() == 176 and got[2] != got[15]             # largeur fixe, images différentes
    again = []
    provider.thumbnail_ready.connect(lambda bucket, image: again.append(bucket))
    provider.request(2_300)                                        # même tranche : réponse immédiate depuis le cache
    assert again == [2]
    provider.shutdown()
    assert provider._player is None and not provider.has_source
    provider.deleteLater()


def test_provider_ignores_requests_without_a_source_and_for_audio(qapp):
    provider = ThumbnailProvider()
    got = []
    provider.thumbnail_ready.connect(lambda *a: got.append(a))
    provider.request(1000)                                         # aucune source
    provider.set_source("/tmp/x.mp3", 0)                           # durée inconnue / audio : refusé
    provider.request(1000)
    pump(qapp, 200)
    assert got == [] and provider._player is None
    provider.deleteLater()


# ----------------------------------------------------------------- barre : survol, dessin
def test_hovering_the_slider_shows_the_bubble_with_the_time_and_leaving_hides_it(window, qapp):
    widget = window.player_widget
    slider = widget.slider
    slider.setEnabled(True)
    slider.setRange(0, 100_000)
    slider.resize(500, 20)
    QtTest.QTest.mouseMove(slider, QtCore.QPoint(250, 10))
    slider.hovered.emit(50_000, 250)
    pump(qapp, 30)
    assert widget.bubble.isVisible() and widget.bubble.time_label.text() == "00:00:50"
    slider.hover_left.emit()
    assert not widget.bubble.isVisible()


def test_slider_paints_in_every_state_without_errors(window, qapp):
    slider = window.player_widget.slider
    slider.resize(400, 20)
    for enabled in (False, True):
        slider.setEnabled(enabled)
        slider.setRange(0, 1000)
        slider.setValue(400)
        slider.set_loop(200, None)
        slider.grab()
        slider.set_loop(200, 700)
        slider._hover_x = 123.0
        slider._grow = 1.0
        image = slider.grab().toImage()
        assert not image.isNull()
    slider.set_loop(None, None)


def test_thumbnail_setting_is_saved_and_disables_the_source(window, qapp):
    assert window.menubar_widget.act_thumbnails.isChecked()                  # activé par défaut
    window.menubar_widget.act_thumbnails.setChecked(False)
    assert window.settings.get("thumbnails") is False and not window.player_widget.thumbnails.has_source
