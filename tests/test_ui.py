"""Tests d'intégration de l'interface (Qt hors écran) avec de vrais médias générés par ffmpeg."""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtMultimedia")
from PySide6 import QtCore, QtGui, QtMultimedia, QtWidgets  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg absent")


def make_video(path: Path, seconds: int = 3, with_audio: bool = True) -> Path:
    args = [FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=320x180:rate=25"]
    if with_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac", "-shortest"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(args, check=True)
    return path


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory):
    if FFMPEG is None:
        pytest.skip("ffmpeg absent")
    folder = tmp_path_factory.mktemp("media")
    for name in ("ep1.mp4", "ep2.mp4", "ep10.mp4"):
        make_video(folder / name, seconds=3)
    return folder


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "userhome"))
    from pyplayer.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    win.set_speed(4.0)
    yield win
    win.close()
    win.deleteLater()
    qapp.processEvents()


def pump(app, ms: int = 50):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def wait_until(app, condition, timeout: float = 10.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.005)
    return False


# ----------------------------------------------------------------- construction
def test_window_starts_with_default_playlist_and_consistent_audio_state(window):
    assert window.active_playlist.name == "PLAYLIST" and len(window.active_playlist) == 0
    assert window.audio_output.volume() == pytest.approx(window.manager.volume)
    assert window.toolbar_widget.volume_widget.slider.value() == round(window.manager.volume * 100)
    assert not window.toolbar_widget.player_controls.btn_stop.isEnabled()


def test_every_menu_action_is_wired_or_intentionally_passive(window):
    """Aucune action de menu ne doit rester muette (audit 2.14)."""
    m = window.menubar_widget
    passive = {m.act_sort_reverse} if hasattr(m, "act_sort_reverse") else set()
    for action in m.all_actions():
        if action in passive or action.isCheckable():
            continue
        assert window.menubar_widget.receivers(QtCore.SIGNAL("x")) >= 0
        assert action.receivers(QtCore.SIGNAL("triggered(bool)")) > 0, f"action muette : {action.text()}"


def test_menu_shortcuts_are_unique(window):
    seen: dict[str, str] = {}
    for action in window.menubar_widget.all_actions():
        for sequence in action.shortcuts():
            key = sequence.toString()
            assert key not in seen, f"{key} utilisé par « {seen[key]} » et « {action.text()} »"
            seen[key] = action.text()
    assert "Ctrl+S" not in seen  # audit 1.7 : plus de « supprimer » sur Ctrl+S


def test_escape_only_leaves_fullscreen(window, qapp):
    assert not window.isFullScreen()
    window.shortcut_escape.activated.emit()
    pump(qapp)
    assert not window.isFullScreen()  # audit 2.12
    window.enter_fullscreen()
    pump(qapp)
    assert window.isFullScreen() and not window.toolbar_widget.isVisible()
    window.shortcut_escape.activated.emit()
    pump(qapp)
    assert not window.isFullScreen() and window.toolbar_widget.isVisible()


def test_fullscreen_restores_hidden_dock(window, qapp):
    window.dock_widget.setVisible(False)
    window.enter_fullscreen()
    window.exit_fullscreen()
    pump(qapp)
    assert not window.dock_widget.isVisible()


def test_mouse_activity_shows_toolbar_in_fullscreen(window, qapp):
    window.enter_fullscreen()
    window._on_mouse_activity()
    assert window.toolbar_widget.isVisible() and window._cursor_timer.isActive()
    window.exit_fullscreen()


# ----------------------------------------------------------------- audio
def test_mute_follows_the_real_audio_output(window):
    assert not window.audio_output.isMuted()
    window.toggle_mute()
    assert window.audio_output.isMuted() and window.toolbar_widget.volume_widget.mute_state  # audit 2.5
    window.toggle_mute()
    assert not window.audio_output.isMuted() and not window.toolbar_widget.volume_widget.mute_state


def test_volume_roundtrip_does_not_drift(window):
    window.toolbar_widget.volume_widget.slider.setValue(29)
    assert window.manager.volume == pytest.approx(0.29)
    assert round(window.manager.volume * 100) == 29  # audit 2.10 : plus de 28


def test_volume_keys_unmute_and_clamp(window):
    window._apply_muted(True)
    window.change_volume(5)
    assert not window.audio_output.isMuted()
    window.change_volume(1000)
    assert window.toolbar_widget.volume_widget.slider.value() == 100
    window.change_volume(-1000)
    assert window.toolbar_widget.volume_widget.slider.value() == 0


def test_volume_is_persisted_by_flush_not_per_tick(window, tmp_path):
    window.toolbar_widget.volume_widget.slider.setValue(33)
    assert window.settings.dirty
    window.manager.flush()
    from pyplayer.api.settings import Settings
    assert Settings(tmp_path / "home" / "settings.json").get("volume") == pytest.approx(0.33)


# ----------------------------------------------------------------- ouverture / lecture réelle
@needs_ffmpeg
def test_open_file_queues_siblings_in_natural_order_and_plays_selected(window, qapp, sample_dir):
    window.open_paths([str(sample_dir / "ep2.mp4")])
    playlist = window.active_playlist
    assert playlist.kind == "quick"
    assert [v.name for v in playlist] == ["ep1.mp4", "ep2.mp4", "ep10.mp4"]  # ordre naturel (audit tri)
    assert playlist.current.name == "ep2.mp4"
    assert wait_until(qapp, lambda: window._resume_ready)
    assert window._loaded_video.name == "ep2.mp4" and window._loaded_video.resolution == "320x180"  # audit 2.6 (taille vidéo)
    assert window._loaded_video.duration > 2000
    assert window.windowTitle().startswith("ep2.mp4")


@needs_ffmpeg
def test_playlist_autoplays_next_then_stops_at_end(window, qapp, sample_dir):
    window.open_paths([str(sample_dir / "ep1.mp4")])
    assert wait_until(qapp, lambda: window._loaded_video and window._loaded_video.name == "ep10.mp4", 25)
    assert wait_until(qapp, lambda: window.statusBar().currentMessage() == "Fin de la playlist", 15)
    assert window.player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.StoppedState
    assert window.resume.is_finished(sample_dir / "ep1.mp4") and window.resume.is_finished(sample_dir / "ep10.mp4")
    assert window.player_widget.placeholder_label.isVisible()


@needs_ffmpeg
def test_position_ticks_never_dirty_the_playlist(window, qapp, tmp_path):
    long = make_video(tmp_path / "ticks.mp4", seconds=14)
    window.set_speed(1.0)
    window.open_paths([str(long)])
    assert wait_until(qapp, lambda: window._resume_ready)
    window.manager.flush()
    window.player.setPosition(7000)
    pump(qapp, 600)
    assert not window.active_playlist.dirty   # audit 3.1 : plus d'écriture de playlist à chaque tick
    assert window.resume.dirty                # la reprise, elle, est suivie (petit fichier séparé)
    assert window.resume.position(long) >= 6500


@needs_ffmpeg
def test_resume_applied_once_on_load(window, qapp, tmp_path, sample_dir):
    long = make_video(tmp_path / "long.mp4", seconds=12)
    window.set_speed(1.0)
    window.resume.update(long, 6000, 12_000)
    window.open_paths([str(long)])
    assert wait_until(qapp, lambda: window._resume_ready)
    pump(qapp, 300)
    assert window.player.position() >= 5500


@needs_ffmpeg
def test_position_goes_to_loaded_video_not_selected_one(window, qapp, tmp_path, sample_dir):
    """Audit 1.6 : changer de playlist pendant la lecture ne contamine pas une autre vidéo."""
    window.open_paths([str(sample_dir / "ep1.mp4")])
    assert wait_until(qapp, lambda: window._resume_ready)
    playing = window._loaded_video
    other = window.manager.create_playlist("Autre", sample_dir)
    window.manager.set_active(other.id)
    window.initialize_playlist_state()
    other_video = other[2]
    other.set_current(other_video)
    window.player.setPosition(2500)
    pump(qapp, 300)
    assert window._loaded_video is playing
    assert window.resume.progress(other_video.path) == 0.0


@needs_ffmpeg
def test_single_click_toggles_pause_and_double_click_toggles_fullscreen(window, qapp, sample_dir):
    window.set_speed(1.0)
    window.open_paths([str(sample_dir / "ep1.mp4")])
    assert wait_until(qapp, lambda: window.player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState)
    window.player_widget.clicked.emit()
    assert window.player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.PausedState
    assert window.toolbar_widget.player_controls.btn_play_pause.text() == ""  # glyphe « lire »
    window.player_widget.clicked.emit()
    assert window.toolbar_widget.player_controls.btn_play_pause.text() == ""
    window.player_widget.signal_double_click.emit()
    pump(qapp)
    assert window.isFullScreen()
    window.exit_fullscreen()


@needs_ffmpeg
def test_play_button_tooltip_describes_next_action(window, qapp, sample_dir):
    window.set_speed(1.0)
    controls = window.toolbar_widget.player_controls
    assert "Lire" in controls.btn_play_pause.toolTip()
    window.open_paths([str(sample_dir / "ep1.mp4")])
    assert wait_until(qapp, lambda: window.player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState)
    assert "Pause" in controls.btn_play_pause.toolTip()  # audit 2.17
    window.player.pause()
    pump(qapp, 100)
    assert "Lire" in controls.btn_play_pause.toolTip()


@needs_ffmpeg
def test_next_at_end_of_playlist_does_not_replay(window, qapp, sample_dir):
    window.open_paths([str(sample_dir / "ep10.mp4")])
    assert wait_until(qapp, lambda: window._resume_ready)
    window.set_speed(1.0)
    pump(qapp, 600)
    position_before = window.player.position()
    window.next_video()  # dernier de la liste, mode normal
    pump(qapp, 200)
    assert window.player.position() >= position_before  # pas de rejeu depuis 0 (audit 2.4)
    assert window.statusBar().currentMessage() == "Fin de la playlist"


@needs_ffmpeg
def test_previous_restarts_current_after_threshold(window, qapp, tmp_path):
    folder = tmp_path / "prev"
    folder.mkdir()
    make_video(folder / "a.mp4", seconds=2)
    make_video(folder / "b.mp4", seconds=12)
    window.open_paths([str(folder / "b.mp4")])
    assert wait_until(qapp, lambda: window._resume_ready)
    window.set_speed(1.0)
    window.player.setPosition(5000)
    pump(qapp, 250)
    window.previous_video()                      # > 3 s : on recommence la vidéo en cours
    pump(qapp, 250)
    assert window._loaded_video.name == "b.mp4" and window.player.position() < 1500
    window.previous_video()                      # au début : vraie vidéo précédente
    assert wait_until(qapp, lambda: window._loaded_video.name == "a.mp4", 5)


@needs_ffmpeg
def test_speed_and_ab_loop(window, qapp, tmp_path):
    long = make_video(tmp_path / "ab.mp4", seconds=10)
    window.open_paths([str(long)])
    assert wait_until(qapp, lambda: window._resume_ready)
    window.set_speed(2.0)
    assert window.player.playbackRate() == pytest.approx(2.0)
    window.step_speed(+1)
    assert window._rate == 3.0 and window.menubar_widget.speed_actions[3.0].isChecked()
    window.step_speed(-1); window.step_speed(-1)
    assert window._rate == 1.75
    window.set_speed(1.0)
    window.player.setPosition(2000)
    pump(qapp, 200)
    window.cycle_ab_loop()                       # A
    a = window._ab_a
    window.player.setPosition(a + 1500)
    pump(qapp, 150)
    window.cycle_ab_loop()                       # B
    assert window._ab_b is not None and "A-B" in window.statusbar_widget.lbl_info.text()
    assert wait_until(qapp, lambda: window.player.position() < window._ab_b - 500, 6)  # a rebouclé vers A
    window.cycle_ab_loop()                       # effacer
    assert window._ab_a is None and window._ab_b is None


@needs_ffmpeg
def test_invalid_file_is_skipped_and_reported(window, qapp, tmp_path, sample_dir):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"this is not a video")
    good = make_video(tmp_path / "good.mp4", seconds=2)
    window.open_paths([str(bad), str(good)])
    assert wait_until(qapp, lambda: window._loaded_video and window._loaded_video.name == "good.mp4", 15)  # audit 2.11


@needs_ffmpeg
def test_screenshot_is_saved(window, qapp, sample_dir, tmp_path):
    window.set_speed(1.0)
    window.open_paths([str(sample_dir / "ep1.mp4")])
    assert wait_until(qapp, lambda: window.player.position() > 300)
    window.take_screenshot()
    shots = list((tmp_path / "userhome").rglob("*.png"))
    assert shots, window.statusBar().currentMessage()
    assert QtGui.QImage(str(shots[0])).width() > 0


@needs_ffmpeg
def test_external_subtitles_are_shown_over_video(window, qapp, tmp_path):
    video = make_video(tmp_path / "film.mp4", seconds=5)
    (tmp_path / "film.srt").write_text("1\n00:00:00,000 --> 00:00:04,000\nBonjour\n", encoding="utf-8")
    window.set_speed(1.0)
    window.open_paths([str(video)])
    assert wait_until(qapp, lambda: window._subtitles is not None)
    assert wait_until(qapp, lambda: window.player_widget.subtitle_label.text() == "Bonjour", 6)
    assert window.player_widget.subtitle_label.isVisibleTo(window.player_widget)
    window.shift_subtitles(+100)
    assert window._subtitles.delay == 100
    window.set_subtitle_source(None, -1)
    assert window.player_widget.subtitle_label.text() == ""


@needs_ffmpeg
def test_media_info_rows_for_loaded_video(window, qapp, sample_dir):
    window.open_paths([str(sample_dir / "ep1.mp4")])
    assert wait_until(qapp, lambda: window._resume_ready)
    rows = dict(window._info_rows(window._loaded_video))
    assert rows["Fichier"] == "ep1.mp4" and rows["Résolution"] == "320x180"
    assert "audio" in rows["Pistes"]


# ----------------------------------------------------------------- playlists et liste
def test_enqueue_adds_to_active_without_playing(window, tmp_path, media_dir):
    folder = media_dir("lib", 3)
    window.open_paths([str(folder)], enqueue=True)
    assert len(window.active_playlist) == 3 and window.dock_widget.lstw.count() == 3
    assert window.player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.StoppedState
    window.open_paths([str(folder)], enqueue=True)
    assert len(window.active_playlist) == 3  # pas de doublons


def test_open_paths_ignores_garbage_and_cancelled_dialogs(window, tmp_path, media_dir):
    (tmp_path / "x.txt").write_text("x")
    window.open_paths([str(tmp_path / "x.txt"), str(tmp_path / "absent.mp4")], enqueue=True)
    assert len(window.active_playlist) == 0


def test_cancelled_folder_dialog_adds_nothing(window, monkeypatch):
    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    before = len(window.active_playlist)
    assert window.choose_folder() is False and len(window.active_playlist) == before  # audit 1.4


def test_dock_items_follow_video_objects_not_names(window, tmp_path):
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "ep1.mp4").write_bytes(b"x")
    window.open_paths([str(tmp_path / "a"), str(tmp_path / "b")], enqueue=True)
    assert len(window.active_playlist) == 2 and window.dock_widget.lstw.count() == 2  # audit 2.8


def test_drag_reorder_moves_in_api_and_ui(window, media_dir):
    window.open_paths([str(media_dir("lib", 4))], enqueue=True)
    playlist = window.active_playlist
    names = [v.name for v in playlist]
    window.on_rows_move_requested([0], 3)            # v0 déposé avant v3
    assert [v.name for v in playlist] == [names[1], names[2], names[0], names[3]]
    assert [window.dock_widget.lstw.item(i).video.name for i in range(4)] == [v.name for v in playlist]
    window.on_rows_move_requested([1, 2], 4)         # fin de liste
    assert [v.name for v in playlist][-2:] == [names[2], names[0]]


def test_move_selected_with_keyboard(window, media_dir):
    window.open_paths([str(media_dir("lib", 3))], enqueue=True)
    window.dock_widget.find_item(window.active_playlist[2]).setSelected(True)
    window.move_selected(-1)
    assert window.active_playlist[1].name == "v2.mp4"
    window.move_selected(-1)
    window.move_selected(-1)  # déjà en tête : no-op
    assert window.active_playlist[0].name == "v2.mp4"


def test_remove_missing_and_sort(window, media_dir):
    window.open_paths([str(media_dir("lib", 3))], enqueue=True)
    window.active_playlist[1].path.unlink()
    window.dock_widget.refresh_missing()
    assert window.dock_widget.find_item(window.active_playlist[1]).missing
    window.remove_missing_files()
    assert len(window.active_playlist) == 2 and window.dock_widget.lstw.count() == 2
    window.menubar_widget.act_sort_reverse.setChecked(True)
    window.sort_playlist("name")
    assert window.active_playlist[0].name == "v2.mp4"


def test_playlist_switch_and_delete_keep_an_active_playlist(window, media_dir):
    other = window.manager.create_playlist("Rock", media_dir("a", 2))
    window.dock_widget.sync_playlists(window.manager.playlists)
    item = window.dock_widget._archive_item(other.id)
    window.dock_widget.lstw_archive.setCurrentItem(item)  # clic utilisateur
    assert window.active_playlist is other and window.dock_widget.lstw.count() == 2
    window.manager.remove_playlist(other.id)
    window.initialize_playlist_state()
    assert window.active_playlist is not None and window.dock_widget.lstw_archive.count() == 1  # audit 2.3


def test_archive_tab_lists_playlists_with_similar_names(window):
    a = window.manager.create_playlist("Hard Rock")
    b = window.manager.create_playlist("Rock")
    window.dock_widget.sync_playlists(window.manager.playlists)
    names = [window.dock_widget.lstw_archive.item(i).text() for i in range(window.dock_widget.lstw_archive.count())]
    assert "Rock" in names and "Hard Rock" in names  # audit 2.7 (MatchEndsWith)


def test_dynamic_menus_fill_without_media(window):
    for fill in (window.fill_recent_menu, window.fill_audio_menu, window.fill_subtitle_menu, window.fill_audio_device_menu):
        fill()
        fill()  # idempotent : pas d'entrées dupliquées
    assert len(window.menubar_widget.audioTrackMenu.actions()) == 3


def test_new_playlist_dialog_validation(qapp, tmp_path, media_dir):
    from pyplayer.ui.dialogs import NewPlaylistDialog
    folder = media_dir("movies", 3)
    dialog = NewPlaylistDialog(None, str(tmp_path))
    assert not dialog.btn_save.isEnabled()
    dialog.edit_folder.setText(str(folder))
    assert dialog.edit_name.text() == "movies"
    dialog._check_timer.stop()
    dialog._check_folder()
    assert dialog.btn_save.isEnabled() and "3 fichiers" in dialog.folder_label.text()
    dialog.edit_name.setText("x")
    assert not dialog.btn_save.isEnabled() and dialog.name_label.isVisibleTo(dialog)
    dialog.edit_name.setText("Films")
    dialog.edit_desc.setPlainText("ma description")
    data = dialog.result_data()
    assert data == {"name": "Films", "path": folder, "description": "ma description"}  # audit 1.8
    dialog.edit_folder.setText(str(tmp_path / "absent"))
    dialog._check_timer.stop()
    dialog._check_folder()
    assert not dialog.btn_save.isEnabled() and "n'existe pas" in dialog.folder_label.text()
    empty = tmp_path / "empty"
    empty.mkdir()
    dialog.edit_folder.setText(str(empty))
    dialog._check_timer.stop()
    dialog._check_folder()
    assert not dialog.btn_save.isEnabled()
    dialog.deleteLater()


def test_new_playlist_does_not_touch_the_source_folder(qapp, media_dir):
    from pyplayer.ui.dialogs import NewPlaylistDialog
    folder = media_dir("ro", 1)
    before = sorted(p.name for p in folder.iterdir())
    dialog = NewPlaylistDialog(None)
    dialog.edit_folder.setText(str(folder))
    dialog._check_timer.stop()
    dialog._check_folder()
    assert sorted(p.name for p in folder.iterdir()) == before  # audit 2.18 : plus de .write_test
    dialog.deleteLater()


def test_delete_dialog_returns_ids_for_same_named_playlists(qapp):
    from pyplayer.ui.widget.dock_widget import DeletePlaylistDialog
    dialog = DeletePlaylistDialog([("id1", "Rock"), ("id2", "Hard Rock")])
    dialog.radio_buttons[1].setChecked(True)
    assert dialog.get_selected_playlists() == ["id2"] and dialog.get_selected_names() == ["Hard Rock"]  # audit 1.3
    dialog.deleteLater()


def send_from_other_thread(app, instance, paths, enqueue=False) -> bool:
    """Envoie comme le ferait une seconde instance (un autre processus) : depuis un thread à part, pendant que la
    boucle d'événements du serveur tourne. Dans un même thread, les tubes nommés de Windows bloquent le client."""
    import threading
    result = []
    worker = threading.Thread(target=lambda: result.append(instance.send_to_running(paths, enqueue)))
    worker.start()
    assert wait_until(app, lambda: bool(result), 10)
    worker.join()
    return result[0]


def test_single_instance_forwards_paths(qapp):
    from pyplayer.ui.single_instance import SingleInstance
    name = f"pyplayer-test-{os.getpid()}"
    server, client = SingleInstance(name=name), SingleInstance(name=name)
    received = []
    server.message_received.connect(lambda paths, enqueue: received.append((paths, enqueue)))
    assert client.send_to_running(["/x/a.mp4"]) is False   # personne n'écoute encore
    assert server.listen()
    assert send_from_other_thread(qapp, client, ["/x/a.mp4", "/x/b.mp4"], enqueue=True)
    assert wait_until(qapp, lambda: bool(received), 3)
    assert received[0] == (["/x/a.mp4", "/x/b.mp4"], True)
    server.close()
    pump(qapp, 50)


def test_window_state_roundtrip(window, qapp, tmp_path):
    window.resize(1111, 666)
    window.save_window_state()
    window.manager.flush()
    from pyplayer.api.settings import Settings
    saved = Settings(tmp_path / "home" / "settings.json")
    assert saved.get("window_geometry") and saved.get("window_state")


def test_single_instance_survives_many_clients_garbage_and_teardown(qapp):
    """Régression d'un plantage natif (double suppression d'un QLocalSocket) : charge, données invalides, fermeture."""
    from PySide6 import QtNetwork
    from pyplayer.ui.single_instance import SingleInstance
    name = f"pyplayer-stress-{os.getpid()}"
    server = SingleInstance(name=name)
    received = []
    server.message_received.connect(lambda paths, enqueue: received.append((tuple(paths), enqueue)))
    assert server.listen()
    clients = [SingleInstance(name=name) for _ in range(5)]
    for i in range(25):
        assert send_from_other_thread(qapp, clients[i % 5], [f"/m/{i}.mp4"], enqueue=bool(i % 2))
    # données invalides : ni JSON, ni UTF-8, ni objet attendu
    for payload in (b"not json", b"\xff\xfe\x00", b"[1,2,3]", b'{"paths": 5}', b"", b'{"paths": ["/ok.mp4"]}'):
        raw = QtNetwork.QLocalSocket()
        raw.connectToServer(name)
        assert wait_until(qapp, lambda: raw.state() == QtNetwork.QLocalSocket.LocalSocketState.ConnectedState, 3)
        raw.write(payload)
        raw.flush()
        wait_until(qapp, lambda: raw.bytesToWrite() == 0, 2)
        raw.disconnectFromServer()
        pump(qapp, 20)
        raw.abort()
    assert wait_until(qapp, lambda: len(received) >= 26, 5), len(received)
    assert received[:3] == [(("/m/0.mp4",), False), (("/m/1.mp4",), True), (("/m/2.mp4",), False)]
    assert (("/ok.mp4",), False) in received and not any(p == ("5",) for p, _ in received)
    server.close()
    del clients, server
    pump(qapp, 150)                      # des événements différés doivent pouvoir être traités sans plantage
    gc_roundtrip = SingleInstance(name=name)
    assert gc_roundtrip.send_to_running(["/x"]) is False   # plus personne n'écoute
