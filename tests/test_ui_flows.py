"""Parcours utilisateur complets pilotés par les boîtes de dialogue (QFileDialog, QInputDialog, QMessageBox patchés)."""

import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtMultimedia")
from PySide6 import QtCore, QtGui, QtMultimedia, QtWidgets  # noqa: E402

from tests.test_ui import FFMPEG, make_video, pump, qapp, wait_until  # noqa: E402,F401
from tests.test_ui_stress import no_unhandled_exceptions, window  # noqa: E402,F401

needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg absent")
HAS_AUDIO_DEVICE = bool(QtMultimedia.QMediaDevices.audioOutputs())
needs_audio_device = pytest.mark.skipif(
    not HAS_AUDIO_DEVICE, reason="aucun périphérique audio : Qt/FFmpeg bloque sur setActiveAudioTrack (voir test dédié)")


@pytest.fixture(scope="module")
def multitrack(tmp_path_factory):
    """MKV avec 2 pistes audio (440 Hz / 880 Hz) et une piste de sous-titres intégrée."""
    if FFMPEG is None:
        pytest.skip("ffmpeg absent")
    folder = tmp_path_factory.mktemp("multi")
    srt = folder / "s.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:09,000\nPiste intégrée\n", encoding="utf-8")
    out = folder / "multi.mkv"
    subprocess.run([FFMPEG, "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc=duration=8:size=320x180:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=8", "-f", "lavfi", "-i", "sine=frequency=880:duration=8",
                    "-i", str(srt), "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map", "3:s",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-c:s", "srt",
                    "-metadata:s:a:0", "language=fra", "-metadata:s:a:1", "language=eng", str(out)], check=True)
    return out


# ----------------------------------------------------------------- boîtes de dialogue simulées
def test_add_files_open_now_and_folder_dialogs(window, qapp, monkeypatch, media_dir, tmp_path):
    folder = media_dir("lib", 3)
    files = [str(p) for p in sorted(folder.iterdir())]
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **k: (files[:2], ""))
    window.add_video_to_playlist()
    assert len(window.active_playlist) == 2 and window.settings.get("last_open_dir") == str(folder)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder))
    assert window.choose_folder() is True
    assert len(window.active_playlist) == 3                      # le doublon n'est pas ajouté
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **k: ([], ""))
    window.add_video_to_playlist()
    window.open_file_now()                                        # annulation : rien ne change
    assert len(window.active_playlist) == 3 and window.active_playlist.kind != "quick"


def test_import_and_export_playlist_dialogs(window, monkeypatch, media_dir, tmp_path):
    folder = media_dir("lib", 3)
    window.open_paths([str(folder)], enqueue=True)
    target = tmp_path / "export.m3u8"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    window.export_playlist_file()
    assert target.read_text(encoding="utf-8").count("#EXTINF") == 3
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: (str(target), ""))
    window.import_playlist_file()
    assert window.active_playlist.name == "export" and len(window.active_playlist) == 3
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window.export_playlist_file()                                 # annulation sans effet
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window.import_playlist_file()
    # une erreur d'écriture est signalée à l'utilisateur au lieu de planter
    shown = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "nodir" / "x" / "y.m3u8"), ""))
    window.export_playlist_file()
    assert shown


def test_open_m3u_through_open_paths_imports_and_activates(window, media_dir, tmp_path):
    folder = media_dir("lib", 2)
    playlist_file = tmp_path / "mix.m3u"
    playlist_file.write_text("\n".join(str(p) for p in sorted(folder.iterdir())), encoding="utf-8")
    window.open_paths([str(playlist_file)], enqueue=True)
    assert window.active_playlist.name == "mix" and len(window.active_playlist) == 2


def test_rename_playlist_dialog(window, monkeypatch):
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, **k: ("Nouveau nom", True))
    window.rename_playlist()
    assert window.active_playlist.name == "Nouveau nom"
    assert window.dock_widget.tab_widget.tabText(0) == "Nouveau nom"
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, **k: ("", True))
    window.rename_playlist()                                      # nom vide refusé
    assert window.active_playlist.name == "Nouveau nom"
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, **k: ("autre", False))
    window.rename_playlist()                                      # annulé
    assert window.active_playlist.name == "Nouveau nom"


def test_create_and_delete_playlist_through_their_dialogs(window, monkeypatch, media_dir):
    from pyplayer.ui import main_window as mw
    folder = media_dir("lib", 2)

    class FakeNew:
        def __init__(self, *a, **k): pass
        def exec(self): return QtWidgets.QDialog.DialogCode.Accepted
        def result_data(self): return {"name": "Via dialogue", "path": folder, "description": "d"}

    monkeypatch.setattr(mw, "NewPlaylistDialog", FakeNew)
    window.create_new_playlist()
    assert window.active_playlist.name == "Via dialogue" and window.active_playlist.description == "d"
    created = window.active_playlist

    class FakeDelete:
        selected_playlists = [created.id]
        def __init__(self, *a, **k): pass
        def exec(self): return QtWidgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr(mw, "DeletePlaylistDialog", FakeDelete)
    window.delete_playlist()
    assert created.id not in window.manager and window.active_playlist is not None

    class CancelDelete(FakeDelete):
        def exec(self): return QtWidgets.QDialog.DialogCode.Rejected

    monkeypatch.setattr(mw, "DeletePlaylistDialog", CancelDelete)
    count = len(window.manager)
    window.delete_playlist()
    assert len(window.manager) == count


def test_remove_videos_confirmation_dialog(window, monkeypatch, media_dir):
    window.open_paths([str(media_dir("lib", 8))], enqueue=True)
    informed = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *a, **k: informed.append(1))
    window.remove_video_from_playlist()                           # rien de sélectionné → message d'information
    assert informed == [1]
    questions = []
    window.dock_widget.get_video_items()[0].setSelected(True)
    monkeypatch.setattr(window, "confirm", lambda title, message, informative="": questions.append(message) or False)
    window.remove_video_from_playlist()
    assert len(window.active_playlist) == 8 and "v0.mp4" in questions[0]   # « Non » : rien n'est retiré
    monkeypatch.setattr(window, "confirm", lambda title, message, informative="": questions.append(message) or True)
    window.remove_video_from_playlist()
    assert len(window.active_playlist) == 7
    for item in window.dock_widget.get_video_items()[:6]:
        item.setSelected(True)
    window.remove_video_from_playlist()                           # message « … et N autres »
    assert len(window.active_playlist) == 1 and "et 1 autres" in questions[-1]


def test_confirm_dialog_returns_the_clicked_answer(window, monkeypatch):
    """La vraie boîte (sans la remplacer) : on simule le clic sur « Oui » puis « Non »."""
    answers = iter(["Oui", "Non"])

    def fake_exec(self):
        wanted = next(answers)
        self._answer = next(b for b in self.buttons() if b.text() == wanted)
        return 0

    class Probe(QtWidgets.QMessageBox):
        exec = fake_exec
        def clickedButton(self): return self._answer

    from pyplayer.ui import main_window as mw
    monkeypatch.setattr(mw.QtWidgets, "QMessageBox", Probe)
    assert window.confirm("t", "m", "info") is True
    assert window.confirm("t", "m") is False


def test_open_url_goto_time_and_missing_file_dialogs(window, qapp, monkeypatch, media_dir):
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, **k: ("http://127.0.0.1:9/video.mp4", True))
    window.open_url_dialog()
    assert "127.0.0.1" in window.title_text and window._loaded_video is None
    window.unload_media()
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, **k: ("", True))
    window.open_url_dialog()                                      # vide : ignoré
    # fichier introuvable : boîte d'erreur (manuel) ou simple message (enchaînement automatique)
    folder = media_dir("lib", 2)
    window.open_paths([str(folder)], enqueue=True)
    video = window.active_playlist[0]
    video.path.unlink()
    errors = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", lambda *a, **k: errors.append(a[2]))
    window.play_video(video)
    assert errors and video.name in errors[0]
    window.play_video(video, silent_if_missing=True)
    assert "introuvable" in window.osd.currentMessage().lower()
    assert window.dock_widget.find_item(video).missing


@needs_ffmpeg
def test_goto_time_accepts_seconds_minutes_hours_and_rejects_garbage(window, qapp, monkeypatch, tmp_path):
    long = make_video(tmp_path / "goto.mp4", seconds=70)
    window.set_speed(1.0)
    window.open_paths([str(long)])
    assert wait_until(qapp, lambda: window._resume_ready and window.player.isSeekable())
    for text, expected in (("30", 30_000), ("1:05", 65_000), ("0:0:20", 20_000), ("999", 70_000)):
        monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, answer=text, **k: (answer, True))
        window.goto_time_dialog()
        assert wait_until(qapp, lambda e=expected: abs(window.player.position() - e) < 2500, 4), (text, window.player.position())
    before = window.player.position()
    for bad in ("abc", "-5", "1:2:3:4", ""):
        monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, bad=bad, **k: (bad, True))
        window.goto_time_dialog()
        assert "invalide" in window.osd.currentMessage()
    assert abs(window.player.position() - before) < 1500


# ----------------------------------------------------------------- pistes audio / sous-titres intégrés
@needs_ffmpeg
@pytest.mark.skipif(HAS_AUDIO_DEVICE, reason="ce test décrit le comportement SANS périphérique audio")
def test_audio_track_switch_is_refused_instead_of_freezing_when_no_audio_device(window, qapp, multitrack, monkeypatch):
    """Sans sortie audio, ``QMediaPlayer.setActiveAudioTrack`` se bloque définitivement (reproduit avec Qt seul) :
    l'application doit refuser le changement au lieu de figer."""
    window.set_speed(1.0)
    window.open_paths([str(multitrack)])
    assert wait_until(qapp, lambda: len(window.player.audioTracks()) == 2)
    calls = []
    monkeypatch.setattr(window.player, "setActiveAudioTrack", lambda i: calls.append(i))
    window.next_audio_track()
    assert calls == [] and "Aucun périphérique audio" in window.osd.currentMessage()
    window.fill_audio_menu()
    window.menubar_widget.audioTrackMenu.actions()[3].trigger()
    assert calls == []                                            # ni par le raccourci ni par le menu
    window.fill_audio_menu()
    assert len(window.menubar_widget.audioTrackMenu.actions()) == 4   # le menu liste quand même les pistes


@needs_ffmpeg
@needs_audio_device
def test_audio_tracks_menu_and_cycling(window, qapp, multitrack):
    window.set_speed(1.0)
    window.open_paths([str(multitrack)])
    assert wait_until(qapp, lambda: len(window.player.audioTracks()) == 2)
    window.fill_audio_menu()
    labels = [a.text() for a in window.menubar_widget.audioTrackMenu.actions()[2:]]
    assert len(labels) == 2 and "fra" in labels[0].lower() or "Piste 1" in labels[0]
    assert window.menubar_widget.audioTrackMenu.actions()[2].isChecked()
    assert window.player.activeAudioTrack() == 0
    window.next_audio_track()
    assert window.player.activeAudioTrack() == 1
    window.next_audio_track()
    assert window.player.activeAudioTrack() == 0                  # cycle
    window.menubar_widget.audioTrackMenu.actions()[3].trigger()
    assert window.player.activeAudioTrack() == 1


@needs_ffmpeg
def test_embedded_subtitles_menu_cycle_and_external_override(window, qapp, multitrack, tmp_path):
    window.set_speed(1.0)
    window.open_paths([str(multitrack)])
    assert wait_until(qapp, lambda: len(window.player.subtitleTracks()) == 1)
    assert window.player.activeSubtitleTrack() == -1 and window._subtitles is None
    window.next_subtitle()
    assert window.player.activeSubtitleTrack() == 0
    window.next_subtitle()
    assert window.player.activeSubtitleTrack() == -1              # retour à « désactivés »
    window.fill_subtitle_menu()
    texts = [a.text() for a in window.menubar_widget.subtitleMenu.actions() if a.text()]
    assert any("Désactivés" in t for t in texts) and any("Piste 1" in t for t in texts)
    assert any("Charger un fichier" in t for t in texts)
    external = tmp_path / "ext.srt"
    external.write_text("1\n00:00:00,000 --> 00:00:30,000\nExterne\n", encoding="utf-8")
    window._set_external_subtitles(external)
    assert window._subtitles is not None and window.player.activeSubtitleTrack() == -1
    assert wait_until(qapp, lambda: window.player_widget.subtitle_label.text() == "Externe", 4)
    window.fill_subtitle_menu()
    assert any("Fichier : ext.srt" in a.text() for a in window.menubar_widget.subtitleMenu.actions())
    window.set_subtitle_source(None, 0)                           # choisir une piste intégrée désactive le fichier
    assert window._subtitles is None and window.player.activeSubtitleTrack() == 0
    empty = tmp_path / "empty.srt"
    empty.write_text("rien", encoding="utf-8")
    window._set_external_subtitles(empty)
    assert "valide" in window.osd.currentMessage()
    monkey = QtWidgets.QFileDialog
    window.shift_subtitles(100)
    assert "Le décalage" in window.osd.currentMessage() or window._subtitles is None


def test_load_subtitle_dialog_and_no_subtitle_messages(window, monkeypatch, tmp_path):
    window.next_subtitle()
    assert "Aucun sous-titre" in window.osd.currentMessage()
    window.next_audio_track()
    assert "Une seule piste" in window.osd.currentMessage()
    srt = tmp_path / "x.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nA\n", encoding="utf-8")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: (str(srt), ""))
    window.load_subtitle_dialog()
    assert window._subtitles is not None and window._subtitles.source == "x.srt"
    window.shift_subtitles(-200)
    assert window._subtitles.delay == -200
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window.load_subtitle_dialog()


# ----------------------------------------------------------------- fenêtre : divers
def test_info_reveal_logs_about_help_and_screenshot_without_media(window, monkeypatch, media_dir):
    from pyplayer.ui import main_window as mw
    opened = []
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    monkeypatch.setattr("pyplayer.api.mediainfo.find_ffprobe", lambda: None)    # Popen est remplacé ci-dessous
    launched = []                                             # Windows/macOS : l'explorateur est lancé par un sous-processus
    monkeypatch.setattr(mw.subprocess, "Popen", lambda args, *a, **k: launched.append(list(args)))
    shown = []
    monkeypatch.setattr(mw.MediaInfoDialog, "exec", lambda self: shown.append(self.findChildren(QtWidgets.QLabel)[0].text()) or 0)
    monkeypatch.setattr(mw.AboutDialog, "exec", lambda self: shown.append("about") or 0)
    monkeypatch.setattr(mw.HelpDialog, "exec", lambda self: shown.append("help") or 0)
    window.show_media_info()
    assert "sélectionné" in window.osd.currentMessage()
    window.open_paths([str(media_dir("lib", 2))], enqueue=True)
    window.dock_widget.get_video_items()[1].setSelected(True)
    window.show_media_info()
    window.reveal_current_file()
    window.open_log_folder()
    window.about_pyplayer()
    window.show_help_dialog()
    assert shown == ["v1.mp4", "about", "help"] and len(opened) + len(launched) == 2
    if launched:                                              # Windows / macOS : le fichier est sélectionné dans l'explorateur
        assert launched[0][-1] == str(window.active_playlist[1].path)
    else:                                                     # Linux : on ouvre le dossier qui le contient
        assert Path(opened[0]) == window.active_playlist[1].parent
    window.take_screenshot()
    assert "Aucune image" in window.osd.currentMessage()


def test_settings_are_restored_by_a_new_window(qapp, isolated_home, monkeypatch):
    from pyplayer.api.manager import PlaylistManager
    from pyplayer.ui.main_window import MainWindow
    first = MainWindow(PlaylistManager(isolated_home))
    first.show()
    first.resize(777, 523)
    first.dock_widget.setVisible(False)
    first.set_aspect_mode("fill")
    first.menubar_widget.act_always_on_top.setChecked(True)
    first.toolbar_widget.volume_widget.slider.setValue(61)
    first.toggle_mute()
    first.close()
    second = MainWindow(PlaylistManager(isolated_home))
    second.show()
    pump(qapp, 100)
    assert second.settings.get("aspect_mode") == "fill"
    assert second.player_widget.video_output.aspectRatioMode() == QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding
    assert second.menubar_widget.aspect_actions["fill"].isChecked()
    assert second.menubar_widget.act_always_on_top.isChecked()
    assert second.toolbar_widget.volume_widget.slider.value() == 61 and second.audio_output.isMuted()
    assert second.audio_output.volume() == pytest.approx(0.61)
    assert not second.dock_widget.isVisible()
    assert abs(second.width() - 777) < 40 and abs(second.height() - 523) < 60
    second.close()


def test_fullscreen_controls_auto_hide_only_while_playing(window, qapp, monkeypatch):
    window.enter_fullscreen()
    window._on_mouse_activity()
    assert window.toolbar_widget.isVisible()
    window._hide_fullscreen_controls()                            # lecteur arrêté : on ne cache pas la barre
    assert window.toolbar_widget.isVisible()
    monkeypatch.setattr(window.player, "playbackState", lambda: QtMultimedia.QMediaPlayer.PlaybackState.PlayingState)
    window._hide_fullscreen_controls()
    assert not window.toolbar_widget.isVisible()
    window.exit_fullscreen()
    assert window.toolbar_widget.isVisible() and window.menubar_widget.isVisible()
    window.exit_fullscreen()                                      # idempotent
    window.enter_fullscreen()
    window.enter_fullscreen()
    window.exit_fullscreen()


def test_set_speed_and_aspect_helpers(window):
    window.set_speed(0.25)
    assert window._rate == 0.25 and window.menubar_widget.speed_actions[0.25].isChecked()
    window.step_speed(-1)                                         # déjà au minimum : reste au minimum
    assert window._rate == 0.25
    window.set_speed(4.0)
    window.step_speed(+1)
    assert window._rate == 4.0
    window.set_speed(1.3)                                         # vitesse hors liste : le cran le plus proche est utilisé
    window.step_speed(+1)
    assert window._rate == 1.5
    assert window.osd.info_text == "1.5×"


def test_closing_the_window_persists_resume_and_playlists(qapp, isolated_home, tmp_path):
    from pyplayer.api.manager import PlaylistManager
    from pyplayer.ui.main_window import MainWindow
    folder = tmp_path / "m"
    folder.mkdir()
    (folder / "a.mp4").write_bytes(b"x")
    win = MainWindow(PlaylistManager(isolated_home))
    win.open_paths([str(folder)], enqueue=True)
    win.active_playlist.set_current(0)
    win.resume.update(folder / "a.mp4", 40_000, 100_000)
    win.close()                                                   # pas de flush manuel : closeEvent s'en charge
    again = PlaylistManager(isolated_home)
    assert again.resume.position(folder / "a.mp4") == 40_000
    assert again.active.current is not None and again.active.current.name == "a.mp4"


@needs_ffmpeg
def test_stop_unloads_the_media_and_never_calls_qt_stop(window, qapp, tmp_path, monkeypatch):
    """Qt 6/FFmpeg : ``QMediaPlayer.stop()`` se bloque par intermittence (0 série sur 4 aboutit sans périphérique audio,
    mesuré avec Qt seul) ; l'application décharge le média avec ``setSource(QUrl())`` à la place."""
    long = make_video(tmp_path / "unload.mp4", seconds=6)
    forbidden = []
    monkeypatch.setattr(window.player, "stop", lambda: forbidden.append(1))
    window.open_paths([str(long)])
    assert wait_until(qapp, lambda: window._resume_ready)
    window.stop_playing()
    assert wait_until(qapp, lambda: window.player.mediaStatus() == QtMultimedia.QMediaPlayer.MediaStatus.NoMedia, 3)
    assert window.player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.StoppedState
    assert window.player_widget.placeholder_label.isVisible() and not window.toolbar_widget.player_controls.btn_stop.isEnabled()
    window.close()                                                # la fermeture non plus n'appelle pas stop()
    assert forbidden == []


@needs_ffmpeg
def test_stop_keeps_the_resume_position(window, qapp, tmp_path):
    """Appuyer sur Stop mémorise l'endroit ; le retour de la position à 0 ne doit pas effacer cette reprise."""
    long = make_video(tmp_path / "stop_resume.mp4", seconds=16)
    window.set_speed(1.0)
    window.open_paths([str(long)])
    assert wait_until(qapp, lambda: window._resume_ready and window.player.isSeekable())
    window.player.setPosition(8000)
    assert wait_until(qapp, lambda: window.player.position() >= 8000, 4)
    pump(qapp, 200)
    window.stop_playing()
    pump(qapp, 600)
    assert window.resume.position(long) >= 7500                  # toujours là après le retour à la position 0
    window.play_or_pause()                                        # et « lire » reprend à cet endroit
    assert wait_until(qapp, lambda: window._resume_ready and window.player.position() >= 7000, 6)


# ----------------------------------------------------------------- lecture : la playlist qui joue n'est pas celle qui est affichée
@needs_ffmpeg
def test_browsing_another_playlist_does_not_hijack_what_plays_next(window, qapp, media_dir):
    from pyplayer.api.media import scan_folder
    a = window.manager.create_playlist("A")
    a.add_many(scan_folder(media_dir("pl_a", 3)))
    b = window.manager.create_playlist("B")
    b.add_many(scan_folder(media_dir("pl_b", 3)))
    window.manager.set_active(a.id)
    window.initialize_playlist_state()
    window.play_video(a[0])
    assert wait_until(qapp, lambda: window._loaded_video is a[0], 5)

    window.manager.set_active(b.id)                       # on parcourt B pendant que A joue
    window.initialize_playlist_state()
    assert window.active_playlist is b and window.playback_playlist is a

    window.next_video()                                   # « suivant » : toujours dans A
    assert window._loaded_video is a[1] and window.playback_playlist is a
    window._on_media_ended()                              # fin de média : A[2], pas B
    assert window._loaded_video is a[2]
    assert b.current is None or b.current not in a.videos
    window.previous_video()
    assert window._loaded_video in a.videos
    assert "0 ➤" not in window.title_text      # l'indice vient de la playlist qui joue
    window.stop_playing()


@needs_ffmpeg
def test_playback_playlist_falls_back_to_the_displayed_one_when_the_playing_one_is_deleted(window, qapp, media_dir):
    from pyplayer.api.media import scan_folder
    a = window.manager.create_playlist("Ephemere")
    a.add_many(scan_folder(media_dir("pl_c", 2)))
    window.manager.set_active(a.id)
    window.play_video(a[0])
    assert wait_until(qapp, lambda: window._loaded_video is a[0], 5)
    window.stop_playing()
    window.manager.remove_playlist(a.id)
    assert window.playback_playlist is window.active_playlist


@needs_ffmpeg
def test_media_info_collects_file_ffprobe_and_qt_metadata_for_the_loaded_video(window, qapp, tmp_path):
    path = tmp_path / "info.mp4"
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-metadata", "title=Titre de test", str(path)], check=True, timeout=60)
    window.open_paths([str(path)])
    assert wait_until(qapp, lambda: window._loaded_video is not None and window.player.duration() > 0, 8)
    pump(qapp, 200)
    sections, _cover = window._info_sections(window._loaded_video)
    titles = [s.title for s in sections]
    assert titles[0] == "Fichier" and "Conteneur" in titles and "Vidéo" in titles and "Audio" in titles
    rows = {label: value for s in sections for label, value in s.rows}
    assert rows["Résolution"] == "320×180" and rows["Nom"] == "info.mp4"
    assert any("Titre de test" in value for value in rows.values())          # métadonnée lue, sans doublon
    window.stop_playing()
