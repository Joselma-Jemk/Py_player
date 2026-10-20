"""Tests de charge et de chaos de l'interface : séquences aléatoires d'actions utilisateur, saisies clavier, glisser-déposer."""

import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtMultimedia")
from PySide6 import QtCore, QtGui, QtMultimedia, QtTest, QtWidgets  # noqa: E402

from tests.test_ui import FFMPEG, make_video, pump, qapp, wait_until  # noqa: E402,F401

needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg absent")


@pytest.fixture(autouse=True)
def no_unhandled_exceptions():
    """Toute exception levée dans un slot Qt (qui ne ferait qu'afficher une trace) fait échouer le test."""
    caught = []
    previous = sys.excepthook
    sys.excepthook = lambda t, e, tb: caught.append((t, e, tb))
    yield caught
    sys.excepthook = previous
    assert not caught, "exceptions non gérées dans l'interface : " + "; ".join(f"{t.__name__}: {e}" for t, e, _ in caught)


@pytest.fixture
def window(qapp, tmp_path, isolated_home):
    from pyplayer.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    win.set_speed(4.0)
    yield win
    win.close()
    win.deleteLater()
    qapp.processEvents()


@pytest.fixture(scope="module")
def library(tmp_path_factory):
    """Bibliothèque mixte : vrais médias courts, faux médias invalides, sous-dossiers, noms exotiques."""
    root = tmp_path_factory.mktemp("library")
    if FFMPEG:
        for name in ("real1.mp4", "real2.mp4"):
            make_video(root / name, seconds=2)
    for name in ("fake1.mp4", "fake2.mkv", "ep10.avi", "ep2.avi", "²x.mp4", "é à ç.mp3"):
        (root / name).write_bytes(b"not really media")
    (root / "sub").mkdir()
    (root / "sub" / "deep.webm").write_bytes(b"nope")
    return root


def consistent(window):
    """Invariants UI ↔ API qui doivent toujours être vrais."""
    playlist = window.active_playlist
    assert playlist is not None and playlist.id in window.manager
    items = window.dock_widget.get_video_items()
    assert [i.video for i in items] == list(playlist.videos), "liste affichée ≠ playlist"
    assert [i.index for i in items] == list(range(1, len(items) + 1)), "numérotation incorrecte"
    assert window.dock_widget.lstw_archive.count() == len(window.manager)
    current = playlist.current
    if current is not None:
        assert any(v is current for v in playlist)
    if window._loaded_video is not None and window.player.mediaStatus() != QtMultimedia.QMediaPlayer.MediaStatus.NoMedia:
        pass  # la vidéo chargée peut avoir été retirée de la playlist active : le lecteur l'a alors arrêtée
    volume = window.toolbar_widget.volume_widget.slider.value()
    assert round(window.audio_output.volume() * 100) == volume
    assert window.toolbar_widget.volume_widget.mute_state == window.audio_output.isMuted()
    assert window.isVisible()


def random_operation(window, rng, library, tmp_path):
    ops = []
    d, m, t = window.dock_widget, window.menubar_widget, window.toolbar_widget
    pl = window.active_playlist

    def enqueue():
        window.open_paths([str(library)], enqueue=True)

    def open_now():
        window.open_paths([str(rng.choice(sorted(library.glob("*.*"))))], enqueue=False)

    def select_some():
        items = d.get_video_items()
        d.lstw.clearSelection()
        for item in rng.sample(items, k=min(len(items), rng.randint(0, 3))):
            item.setSelected(True)

    def remove_selected():
        select_some()
        videos = d.get_selected_videos()
        if videos:
            window.remove_videos(videos)

    def reorder_drag():
        n = len(pl)
        if n >= 2:
            rows = sorted(rng.sample(range(n), k=rng.randint(1, min(3, n))))
            window.on_rows_move_requested(rows, rng.randint(0, n))

    def move_key():
        select_some()
        window.move_selected(rng.choice([-1, 1]))

    def jump():
        if len(pl):
            window.double_click(rng.choice(d.get_video_items()))

    def create_playlist():
        folder = tmp_path / f"extra{rng.randint(0, 3)}"
        folder.mkdir(exist_ok=True)
        (folder / f"x{rng.randint(0, 5)}.mp4").write_bytes(b"z")
        window.create_playlist_from(f"P{rng.randint(0, 5)}", folder)

    def delete_playlist():
        ids = [p.id for p in window.manager]
        window.remove_playlists(rng.sample(ids, k=rng.randint(1, len(ids))))

    def switch_playlist():
        target = rng.choice(window.manager.playlists)
        item = d._archive_item(target.id)
        d.lstw_archive.setCurrentItem(item)

    def mode_click():
        t.player_controls.btn_play_mode.click()

    def key(k, mods=QtCore.Qt.KeyboardModifier.NoModifier):
        QtTest.QTest.keyClick(window, k, mods)

    ops += [("enqueue", enqueue), ("open_now", open_now), ("remove", remove_selected), ("drag", reorder_drag),
            ("move_key", move_key), ("jump", jump), ("create", create_playlist), ("delete", delete_playlist),
            ("switch", switch_playlist), ("mode", mode_click),
            ("play_pause", lambda: window.play_or_pause()), ("stop", lambda: window.stop_playing()),
            ("next", lambda: window.next_video()), ("prev", lambda: window.previous_video()),
            ("speed", lambda: window.set_speed(rng.choice([0.5, 1.0, 2.0, 4.0]))),
            ("mute", lambda: window.toggle_mute()), ("volume", lambda: window.change_volume(rng.randint(-30, 30))),
            ("slider_volume", lambda: t.volume_widget.slider.setValue(rng.randint(0, 100))),
            ("fullscreen", lambda: window.toggle_fullscreen()),
            ("aspect", lambda: window.set_aspect_mode(rng.choice(["fit", "fill", "stretch"]))),
            ("ab", lambda: window.cycle_ab_loop()), ("subs", lambda: window.next_subtitle()),
            ("audio", lambda: window.next_audio_track()), ("seek", lambda: window.player_widget.seek_relative(rng.choice([-60000, -10000, 10000, 60000]))),
            ("sort", lambda: window.sort_playlist(rng.choice(["name", "path", "date", "size", "duration"]))),
            ("refresh", lambda: window.refresh_from_source()), ("missing", lambda: window.remove_missing_files()),
            ("pause_click", lambda: window.player_widget.clicked.emit()),
            ("keys_lr", lambda: key(rng.choice([QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Right]))),
            ("keys_ud", lambda: key(rng.choice([QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down]))),
            ("always_on_top", lambda: m.act_always_on_top.toggle()),
            ("menus", lambda: [f() for f in (window.fill_recent_menu, window.fill_audio_menu, window.fill_subtitle_menu,
                                             window.fill_audio_device_menu)]),
            ("info_rows", lambda: window._info_rows(rng.choice(pl.videos)) if len(pl) else None),
            ("rename", lambda: (window.manager.rename(pl.id, f"R{rng.randint(0, 9)}"), d.rename_playlist_state(pl))),
            ("wheel", lambda: window.change_volume(rng.choice([-5, 5]))),
            ("shuffle_dirty_flush", lambda: window.manager.flush())]
    name, fn = rng.choice(ops)
    return name, fn


@pytest.mark.parametrize("seed", range(8))
def test_random_user_actions_never_break_ui_or_data(window, qapp, library, tmp_path, seed):
    rng = random.Random(seed)
    window.open_paths([str(library)], enqueue=True)
    history = []
    for step in range(120):
        name, fn = random_operation(window, rng, library, tmp_path)
        history.append(name)
        try:
            fn()
        except Exception as error:   # noqa: BLE001
            pytest.fail(f"étape {step} « {name} » a levé {type(error).__name__}: {error}\nhistorique: {history[-15:]}")
        pump(qapp, 4)
        try:
            consistent(window)
        except AssertionError as error:
            pytest.fail(f"invariant cassé après l'étape {step} « {name} » : {error}\nhistorique: {history[-15:]}")
    window.exit_fullscreen()
    window.manager.flush()
    reopened = type(window.manager)(window.manager.data_dir)              # tout ce qui est écrit se relit
    assert len(reopened) == len(window.manager)
    assert {p.id for p in reopened} == {p.id for p in window.manager}


# ----------------------------------------------------------------- clavier
def test_arrow_keys_drive_volume_and_seek_only_when_the_list_is_not_focused(window, qapp, library):
    window.open_paths([str(library)], enqueue=True)
    slider = window.toolbar_widget.volume_widget.slider
    before = slider.value()
    window.dock_widget.lstw.setFocus()
    window.dock_widget.lstw.setCurrentRow(0)
    QtTest.QTest.keyClick(window.dock_widget.lstw, QtCore.Qt.Key.Key_Down)
    assert slider.value() == before                                      # la liste garde ses flèches
    window.setFocus()
    QtTest.QTest.keyClick(window, QtCore.Qt.Key.Key_Up)
    assert slider.value() == before + 2
    QtTest.QTest.keyClick(window, QtCore.Qt.Key.Key_Down)
    assert slider.value() == before


@needs_ffmpeg
def test_left_right_seek_and_shift_for_long_jumps(window, qapp, tmp_path):
    long = make_video(tmp_path / "keys.mp4", seconds=130)
    window.set_speed(1.0)
    window.open_paths([str(long)])
    assert wait_until(qapp, lambda: window._resume_ready and window.player.isSeekable())
    window.player.setPosition(20_000)
    pump(qapp, 150)
    QtTest.QTest.keyClick(window, QtCore.Qt.Key.Key_Right)
    assert wait_until(qapp, lambda: 29_000 <= window.player.position() <= 33_000, 3)
    QtTest.QTest.keyClick(window, QtCore.Qt.Key.Key_Right, QtCore.Qt.KeyboardModifier.ShiftModifier)
    assert wait_until(qapp, lambda: 89_000 <= window.player.position() <= 95_000, 3)
    QtTest.QTest.keyClick(window, QtCore.Qt.Key.Key_Left, QtCore.Qt.KeyboardModifier.ShiftModifier)
    assert wait_until(qapp, lambda: 29_000 <= window.player.position() <= 36_000, 3)


def test_space_toggles_play_without_double_trigger_from_focused_buttons(window, qapp, library):
    """Audit : Espace sur un bouton ayant le focus déclenchait deux fois play/pause."""
    for button in window.toolbar_widget.player_controls.btn_list:
        assert button.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus


# ----------------------------------------------------------------- glisser-déposer
def make_drop(urls, source=None):
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(str(u)) for u in urls])
    return mime


def test_drop_files_and_folders_onto_window_opens_them(window, qapp, library, monkeypatch):
    opened = []
    monkeypatch.setattr(window, "open_paths", lambda items, enqueue=False: opened.append((list(items), enqueue)))
    mime = make_drop([library / "fake1.mp4", library / "sub"])
    event = QtGui.QDropEvent(QtCore.QPointF(10, 10), QtCore.Qt.DropAction.CopyAction, mime,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    window.dropEvent(event)
    assert opened == [([str(library / "fake1.mp4"), str(library / "sub")], False)]


def test_drop_onto_playlist_enqueues_instead_of_playing(window, qapp, library, monkeypatch):
    opened = []
    monkeypatch.setattr(window, "open_paths", lambda items, enqueue=False: opened.append((list(items), enqueue)))
    lst = window.dock_widget.lstw
    mime = make_drop([library / "fake1.mp4"])
    event = QtGui.QDropEvent(QtCore.QPointF(5, 5), QtCore.Qt.DropAction.CopyAction, mime,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    lst.dropEvent(event)
    assert opened == [([str(library / "fake1.mp4")], True)]


def test_drop_of_non_local_urls_is_ignored(window, qapp):
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl("https://example.com/video.mp4")])
    event = QtGui.QDropEvent(QtCore.QPointF(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    window.dropEvent(event)   # ne doit pas lever
    assert len(window.active_playlist) == 0


# ----------------------------------------------------------------- menus contextuels
def labels(menu):
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def test_player_context_menu_content(window):
    entries = " | ".join(labels(window.build_player_context_menu()))
    for expected in ("Lire", "Stop", "Vitesse de lecture", "Piste audio", "Sous-titres", "Format de l'image",
                     "capture d'écran", "plein écran", "Informations"):
        assert expected.lower() in entries.lower(), expected


def test_playlist_context_menu_adapts_to_selection(window, library):
    window.open_paths([str(library)], enqueue=True)
    without_selection = " | ".join(labels(window.build_playlist_context_menu()))
    assert "Retirer de la playlist" not in without_selection and "Ajouter un dossier" in without_selection
    window.dock_widget.get_video_items()[0].setSelected(True)
    with_selection = " | ".join(labels(window.build_playlist_context_menu()))
    for expected in ("Lire", "Monter", "Descendre", "Retirer de la playlist", "Afficher dans le dossier",
                     "Copier le chemin", "Informations"):
        assert expected in with_selection, expected


def test_copy_path_action_puts_paths_on_the_clipboard(window, qapp, library):
    window.open_paths([str(library)], enqueue=True)
    items = window.dock_widget.get_video_items()
    for item in items[:2]:
        item.setSelected(True)
    menu = window.build_playlist_context_menu()
    next(a for a in menu.actions() if a.text() == "Copier le chemin").trigger()
    assert QtWidgets.QApplication.clipboard().text().splitlines() == [str(i.video.path) for i in items[:2]]


def test_remove_action_of_context_menu_is_wired(window, library, monkeypatch):
    window.open_paths([str(library)], enqueue=True)
    window.dock_widget.get_video_items()[0].setSelected(True)
    called = []
    monkeypatch.setattr(window, "remove_video_from_playlist", lambda: called.append(True))
    menu = window.build_playlist_context_menu()          # reconstruit après le patch : les lambdas résolvent self.<méthode>
    next(a for a in menu.actions() if a.text().startswith("Retirer de la playlist")).trigger()
    assert called == [True]


# ----------------------------------------------------------------- l'aide dit la vérité
def help_shortcuts_text(qapp):
    from pyplayer.ui.widget.menu_bar import HelpDialog
    dialog = HelpDialog()
    labels = [lbl.text() for lbl in dialog.findChildren(QtWidgets.QLabel)]
    dialog.deleteLater()
    return labels


def test_every_shortcut_promised_by_the_help_dialog_really_exists(window, qapp):
    """Audit 2.15 : l'aide documentait Ctrl+→/← et « Ctrl+D = créer une playlist » qui n'existaient pas."""
    actions = {s.toString(): a.text() for a in window.menubar_widget.all_actions() for s in a.shortcuts()}
    handled_by_keys = {"←", "→", "↑", "↓", "Échap", "Glisser", "Maj", "molette", "Clic", "Double"}
    labels = help_shortcuts_text(qapp)
    promised = [t for t in labels if re.fullmatch(r"(Ctrl\+[A-Za-z→←]+|F\d+|F / F11|Espace|M|A|V|S|L|\[  \]  ⌫)", t.strip())]
    assert promised, "aucun raccourci détecté dans l'aide (le test doit rester pertinent)"
    translate = {"Ctrl+→": "Ctrl+Right", "Ctrl+←": "Ctrl+Left", "Espace": "Space"}
    for text in promised:
        text = text.strip()
        for part in ("F11", "F") if text == "F / F11" else (["[", "]", "Backspace"] if text.startswith("[") else [text]):
            key = translate.get(part, part)
            assert key in actions, f"« {part} » est annoncé dans l'aide mais ne correspond à aucune action"
    assert actions["Ctrl+D"] == "Ajouter un dossier à la playlist"
    assert "Ctrl+S" not in actions


def test_help_and_about_report_the_real_version(qapp):
    from pyplayer import __version__
    from pyplayer.ui.dialogs import AboutDialog
    about = AboutDialog()
    texts = " ".join(l.text() for l in about.findChildren(QtWidgets.QLabel))
    assert __version__ in texts and "0.0.1" not in texts
    assert any(__version__ in t for t in help_shortcuts_text(qapp))
    about.deleteLater()


# ----------------------------------------------------------------- performances (bornes larges, anti-régression)
def test_populating_a_huge_playlist_is_fast(window, qapp, tmp_path):
    folder = tmp_path / "huge"
    folder.mkdir()
    for i in range(1500):
        (folder / f"video{i:05d}.mp4").write_bytes(b"x")
    start = time.perf_counter()
    window.open_paths([str(folder)], enqueue=True)
    assert len(window.active_playlist) == 1500
    assert time.perf_counter() - start < 20.0
    start = time.perf_counter()
    window.refresh_playlist_view()
    assert time.perf_counter() - start < 15.0
    assert window.dock_widget.lstw.count() == 1500


def test_ten_thousand_position_ticks_are_cheap(window, qapp, library):
    window.open_paths([str(library)], enqueue=True)
    window._loaded_video = window.active_playlist[0]
    window._resume_ready = True
    window.manager.flush()
    start = time.perf_counter()
    for position in range(10_000):
        window.on_position_changed(10_000 + position * 50)
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0, f"{elapsed:.2f}s pour 10 000 ticks"
    assert not window.active_playlist.dirty


def test_big_playlist_serialization_and_reload_are_fast(isolated_home, tmp_path):
    from pyplayer.api.manager import PlaylistManager
    folder = tmp_path / "big"
    folder.mkdir()
    for i in range(5000):
        (folder / f"f{i}.mp4").write_bytes(b"x")
    manager = PlaylistManager(isolated_home)
    start = time.perf_counter()
    playlist = manager.create_playlist("Big", folder)
    manager.flush()
    created = time.perf_counter() - start
    start = time.perf_counter()
    reloaded = PlaylistManager(isolated_home)
    loaded = time.perf_counter() - start
    assert len(next(p for p in reloaded if p.name == "Big")) == 5000
    assert created < 10 and loaded < 5, (created, loaded)


# ----------------------------------------------------------------- rendu de la liste (délégué de dessin)
def _count_close(image, rect, rgb, tolerance=14):
    count = 0
    for y in range(rect.top(), rect.bottom()):
        for x in range(rect.left(), rect.right()):
            c = QtGui.QColor(image.pixel(x, y))
            if abs(c.red() - rgb[0]) <= tolerance and abs(c.green() - rgb[1]) <= tolerance and abs(c.blue() - rgb[2]) <= tolerance:
                count += 1
    return count


def test_list_rows_are_painted_with_the_color_of_their_state(window, qapp, tmp_path):
    names = ["a_normal.mp4", "b_current.mp4", "c_read.mp4", "d_missing.mp4"]
    for name in names[:3]:
        (tmp_path / name).write_bytes(b"x")
    window.dock_widget.setFloating(True)
    window.dock_widget.resize(360, 420)
    window.open_paths([str(tmp_path / n) for n in names[:3]], enqueue=True)
    missing = tmp_path / names[3]
    missing.write_bytes(b"x")
    window.open_paths([str(missing)], enqueue=True)
    missing.unlink()
    window.dock_widget.refresh_missing()
    items = window.dock_widget.get_video_items()
    items[1].is_current = True
    items[2].is_read = True
    pump(qapp, 50)
    lst = window.dock_widget.lstw
    image = lst.viewport().grab().toImage()
    expected = {0: (0xe0, 0xe0, 0xe0), 1: (0xff, 0xff, 0xff), 2: (0xa5, 0xd6, 0xa7), 3: (0x8e, 0x8e, 0x93)}
    for row, rgb in expected.items():
        rect = lst.visualItemRect(items[row])
        text_zone = QtCore.QRect(rect.left() + 6, rect.top() + 4, int(rect.width() * 0.6), rect.height() - 8)
        assert _count_close(image, text_zone, rgb) > 25, f"ligne {row} ({items[row].state}) : couleur {rgb} absente"
    # et les états ne se contaminent pas : la ligne « missing » n'a pas de texte blanc
    rect = lst.visualItemRect(items[3])
    assert _count_close(image, QtCore.QRect(rect.left() + 6, rect.top() + 4, int(rect.width() * 0.6), rect.height() - 8),
                        (0xff, 0xff, 0xff), 4) < 5


def test_progress_updates_repaint_only_when_the_bar_changes(window, qapp, media_dir):
    window.open_paths([str(media_dir("lib", 1))], enqueue=True)
    item = window.dock_widget.get_video_items()[0]
    changes = []
    window.dock_widget.lstw.model().dataChanged.connect(lambda *a: changes.append(1))
    for pct in range(0, 100, 1):          # 100 ticks de 1 %
        item.set_progress(pct / 100)
    assert len(changes) <= 11             # une seule mise à jour par segment de la barre (10 segments), pas 100


# ----------------------------------------------------------------- éléments restants de l'audit
def test_shortcuts_are_never_ambiguous(window):
    """Audit 2.13 : deux QShortcut sur la même touche s'annulaient (la touche muet ne faisait rien)."""
    seen: dict[str, str] = {}
    for shortcut in window.findChildren(QtGui.QShortcut):
        key = shortcut.key().toString()
        if not key or shortcut.context() == QtCore.Qt.ShortcutContext.WidgetShortcut:
            continue
        assert key not in seen, f"{key} est déclaré deux fois"
        seen[key] = key
    for action in window.menubar_widget.all_actions():
        for sequence in action.shortcuts():
            assert sequence.toString() not in seen, f"{sequence.toString()} entre en conflit avec un QShortcut"


def test_volume_mute_key_toggles_mute(window, qapp):
    shortcut = next(s for s in window.findChildren(QtGui.QShortcut) if s.key().toString() == "Volume Mute")
    assert not window.audio_output.isMuted()
    shortcut.activated.emit()
    assert window.audio_output.isMuted()


def test_description_typed_in_the_dialog_is_really_saved(window, tmp_path, media_dir):
    """Audit 1.8 : la description était lue puis jetée."""
    playlist = window.create_playlist_from("Avec description", media_dir("d", 2), "ma description")
    window.manager.flush()
    from pyplayer.api.manager import PlaylistManager
    reloaded = next(p for p in PlaylistManager(window.manager.data_dir) if p.name == "Avec description")
    assert reloaded.description == "ma description" and len(reloaded) == 2 and playlist.id == reloaded.id


def test_slider_dragging_does_not_flood_the_player_with_seeks(window, qapp, monkeypatch):
    """Audit 3.7 : un clic/glissement déclenchait plusieurs recherches par mouvement de souris."""
    widget = window.player_widget
    slider = widget.slider
    slider.setEnabled(True)
    slider.setRange(0, 100_000)
    calls = []
    monkeypatch.setattr(widget.video_player, "setPosition", lambda pos: calls.append(pos))
    QtTest.QTest.mousePress(slider, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(10, 5))
    for x in range(10, 200, 2):                      # 95 mouvements quasi instantanés
        QtTest.QTest.mouseMove(slider, QtCore.QPoint(x, 5))
    assert len(calls) <= 3                            # recherches limitées dans le temps, pas une par pixel
    QtTest.QTest.mouseRelease(slider, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(200, 5))
    assert len(calls) <= 4 and calls[-1] == slider.value()   # et la position finale est toujours appliquée


def test_clicking_the_slider_jumps_to_that_position(window, qapp, monkeypatch):
    slider = window.player_widget.slider
    slider.setEnabled(True)
    slider.setRange(0, 1000)
    slider.resize(500, 20)
    calls = []
    monkeypatch.setattr(window.player_widget.video_player, "setPosition", lambda pos: calls.append(pos))
    QtTest.QTest.mouseClick(slider, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(250, 10))
    assert calls and abs(calls[-1] - 500) <= 5       # milieu du slider = milieu du média


def test_folder_validation_is_debounced_not_run_per_keystroke(qapp, media_dir, monkeypatch):
    """Audit 3.9 : jusqu'à 6 parcours de dossier par frappe."""
    from pyplayer.ui import dialogs
    folder = media_dir("deb", 3)
    dialog = dialogs.NewPlaylistDialog(None)
    scans = []
    real = dialogs.media.count_media
    monkeypatch.setattr(dialogs.media, "count_media", lambda *a, **k: scans.append(1) or real(*a, **k))
    for i in range(1, len(str(folder)) + 1):          # frappe caractère par caractère
        dialog.edit_folder.setText(str(folder)[:i])
    pump(qapp, 700)
    assert len(scans) <= 2 and dialog.btn_save.isEnabled()
    dialog.deleteLater()


def test_playlist_name_follows_the_typed_folder_until_the_user_edits_it(qapp, tmp_path):
    """Sous Windows, la 1re frappe (« C ») figeait le nom à 1 caractère, invalide : le nom doit suivre la saisie."""
    from pyplayer.ui import dialogs
    dialog = dialogs.NewPlaylistDialog(None)
    for text in ("a", "ab", "ab/mes_films", str(tmp_path / "Films")):
        dialog.edit_folder.setText(text)
    assert dialog.edit_name.text() == "Films"
    dialog.edit_name.setText("Perso")
    dialog.edit_name.textEdited.emit("Perso")                      # modification faite par l'utilisateur
    dialog.edit_folder.setText(str(tmp_path / "Autre"))
    assert dialog.edit_name.text() == "Perso"
    dialog.deleteLater()


def test_icon_font_is_registered_only_once(qapp, monkeypatch):
    """Audit 3.11 : la police d'icônes était rechargée par quatre widgets."""
    from pyplayer.ui import theme
    monkeypatch.setattr(theme, "_FONT_FAMILY", None)              # repart d'un état « jamais chargé »
    calls = []
    real = QtGui.QFontDatabase.addApplicationFont
    monkeypatch.setattr(QtGui.QFontDatabase, "addApplicationFont", staticmethod(lambda path: calls.append(path) or real(path)))
    for size in (10, 12, 14, 15):
        theme.load_icon_font(size)
    assert theme.icon_font_family() != "" and len(calls) == 1


def test_version_is_defined_in_one_place_and_displayed_everywhere(window):
    import re
    from pathlib import Path
    from pyplayer import __version__
    import tomllib
    project = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dynamic"] == ["version"] and "version" not in project      # une seule source : pyplayer.__version__
    sources = Path(__file__).resolve().parent.parent / "src"
    offenders = [str(p) for p in sources.rglob("*.py") if re.search(r"['\"]0\.0\.1['\"]|v0\.0\.1", p.read_text(encoding="utf-8"))]
    assert not offenders, offenders                    # audit chap. 5 : « 0.0.1 » codé en dur dans plusieurs fichiers


def test_every_glyph_button_uses_the_icon_font(window):
    """Capture réelle : le bouton de volume affichait « ! » car la police d'icônes ne lui était pas appliquée."""
    from pyplayer.ui import theme
    family = theme.icon_font_family()
    controls = window.toolbar_widget.player_controls
    glyph_buttons = [window.toolbar_widget.volume_widget.btn, window.toolbar_widget.btn_playlist, *controls.btn_list,
                     window.dock_widget.btn_add_to_playlist, window.dock_widget.btn_remove_to_playlist,
                     window.dock_widget.btn_save_playlist, window.dock_widget.btn_remove_save]
    for button in glyph_buttons:
        assert button.font().family() == family, f"{button.text()!r} n'utilise pas la police d'icônes"
    metrics = QtGui.QFontMetrics(window.toolbar_widget.volume_widget.btn.font())
    for glyph in ("", "", "", ""):          # les 4 états du bouton de volume existent dans la police
        assert metrics.inFontUcs4(ord(glyph)), hex(ord(glyph))
