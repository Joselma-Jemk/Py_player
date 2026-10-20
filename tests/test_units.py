"""Tests unitaires des modules « système » : veille, journalisation, chemins, widget lecteur, panneau de playlists."""

import logging
import subprocess
import sys
import types
from pathlib import Path

import pytest

from pyplayer.api import logging_setup, paths

pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui, QtTest, QtWidgets  # noqa: E402

from tests.test_ui import pump, qapp  # noqa: E402,F401


# ----------------------------------------------------------------- journalisation
def test_logging_setup_is_idempotent_and_writes_a_rotating_file(tmp_path):
    logger = logging.getLogger("pyplayer")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    path = logging_setup.setup_logging(tmp_path, debug=True)
    assert logger.level == logging.DEBUG
    again = logging_setup.setup_logging(tmp_path)                 # le dernier appel décide du niveau
    assert path == again == tmp_path / "pyplayer.log" and logger.level == logging.INFO
    assert len(logger.handlers) == 2                              # fichier + console, jamais dupliqués
    logging.getLogger("pyplayer.test").info("bonjour é")
    for handler in logger.handlers:
        handler.flush()
    assert "bonjour é" in path.read_text(encoding="utf-8")
    assert not logger.propagate
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_logging_setup_survives_an_unwritable_directory(tmp_path):
    logger = logging.getLogger("pyplayer")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    blocker = tmp_path / "file"
    blocker.write_text("x")
    logging_setup.setup_logging(blocker / "sub")                  # un fichier à la place du dossier : pas d'exception
    assert logger.handlers                                         # la console reste disponible
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


# ----------------------------------------------------------------- chemins
def test_package_dir_in_a_frozen_application(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.package_dir() == tmp_path / "pyplayer"
    assert paths.resources_dir() == tmp_path / "pyplayer" / "resources"


def test_resources_exist_in_the_source_tree():
    for resource in (paths.font_path(), paths.app_icon_path(), paths.placeholder_icon_path(), paths.icons_dir() / "light" / "play.png"):
        assert resource.is_file(), resource


def test_data_dir_honours_override_and_creates_it(monkeypatch, tmp_path):
    target = tmp_path / "custom" / "deep"
    monkeypatch.setenv(paths.HOME_ENV_VAR, str(target))
    assert paths.data_dir() == target and target.is_dir()


# ----------------------------------------------------------------- inhibition de veille
def test_inhibitor_windows_branch(monkeypatch):
    from pyplayer.ui import power
    calls = []
    fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(
        kernel32=types.SimpleNamespace(SetThreadExecutionState=lambda flags: calls.append(flags))))
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    monkeypatch.setattr(sys, "platform", "win32")
    inhibitor = power.SleepInhibitor()
    inhibitor.set_active(True)
    inhibitor.set_active(True)                                    # idempotent
    inhibitor.set_active(False)
    assert inhibitor.active is False
    assert calls == [0x80000000 | 0x3, 0x80000000]


def test_inhibitor_macos_branch(monkeypatch):
    from pyplayer.ui import power
    started = []

    class FakeProcess:
        def terminate(self):
            started.append("terminated")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(power.subprocess, "Popen", lambda cmd: started.append(cmd) or FakeProcess())
    inhibitor = power.SleepInhibitor()
    inhibitor.set_active(True)
    inhibitor.set_active(False)
    assert started == [["caffeinate", "-d", "-i"], "terminated"]


def test_inhibitor_never_raises_when_the_platform_service_is_missing(monkeypatch):
    from pyplayer.ui import power
    monkeypatch.setattr(sys, "platform", "linux")
    inhibitor = power.SleepInhibitor()
    inhibitor.set_active(True)        # pas de bus D-Bus de session dans le conteneur : l'erreur est absorbée
    assert inhibitor.active is False  # et l'état reste cohérent
    inhibitor.set_active(False)


# ----------------------------------------------------------------- widget lecteur
@pytest.fixture
def player_widget(qapp):
    from pyplayer.ui.widget.player import PlayerWidget
    widget = PlayerWidget()
    widget.resize(700, 450)
    widget.show()
    yield widget
    widget.deleteLater()


def test_single_click_is_emitted_after_the_delay_and_cancelled_by_double_click(player_widget, qapp):
    clicks, doubles = [], []
    player_widget.clicked.connect(lambda: clicks.append(1))
    player_widget.signal_double_click.connect(lambda: doubles.append(1))
    target = player_widget.video_output
    # clic simple
    QtTest.QTest.mouseClick(target, QtCore.Qt.MouseButton.LeftButton)
    assert clicks == []                     # pas immédiat : on attend de savoir si c'est un double-clic
    pump(qapp, 400)
    assert clicks == [1] and doubles == []
    # double-clic : un seul signal « double », aucun clic simple parasite
    QtTest.QTest.mouseDClick(target, QtCore.Qt.MouseButton.LeftButton)
    pump(qapp, 400)
    assert doubles == [1] and clicks == [1]


def test_wheel_move_and_context_menu_events_are_forwarded(player_widget, qapp):
    wheel, moves, menus = [], [], []
    player_widget.wheel_volume.connect(wheel.append)
    player_widget.mouse_moved.connect(lambda: moves.append(1))
    player_widget.context_menu_requested.connect(menus.append)
    target = player_widget.video_output
    for delta in (120, -120, 0):
        event = QtGui.QWheelEvent(QtCore.QPointF(5, 5), QtCore.QPointF(5, 5), QtCore.QPoint(0, 0), QtCore.QPoint(0, delta),
                                  QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier,
                                  QtCore.Qt.ScrollPhase.NoScrollPhase, False)
        QtWidgets.QApplication.sendEvent(target, event)
    assert wheel == [1, -1]                 # un cran nul n'émet rien
    QtTest.QTest.mouseMove(target, QtCore.QPoint(20, 20))
    assert moves
    context = QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, QtCore.QPoint(5, 5), QtCore.QPoint(15, 15))
    QtWidgets.QApplication.sendEvent(target, context)
    assert len(menus) == 1


def test_display_modes_and_subtitle_overlay(player_widget):
    assert player_widget.placeholder_label.isVisibleTo(player_widget) and not player_widget.stage.isVisibleTo(player_widget)
    player_widget.show_video()
    assert player_widget.stage.isVisibleTo(player_widget) and not player_widget.placeholder_label.isVisibleTo(player_widget)
    player_widget.set_subtitle_text("Bonjour")
    assert player_widget.subtitle_label.isVisibleTo(player_widget) and player_widget.subtitle_label.text() == "Bonjour"
    player_widget.set_subtitle_text("")
    assert not player_widget.subtitle_label.isVisibleTo(player_widget)
    for mode, expected in (("fit", QtCore.Qt.AspectRatioMode.KeepAspectRatio),
                           ("stretch", QtCore.Qt.AspectRatioMode.IgnoreAspectRatio),
                           ("fill", QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding),
                           ("inconnu", QtCore.Qt.AspectRatioMode.KeepAspectRatio)):
        player_widget.set_aspect_mode(mode)
        assert player_widget.video_output.aspectRatioMode() == expected
    assert player_widget.position_to_hms(3_725_000) == "01:02:05" and player_widget.position_to_hms(-5) == "00:00:00"


def test_seek_relative_is_safe_without_media(player_widget):
    player_widget.seek_relative(10_000)      # durée 0 : ne fait rien, ne lève pas
    assert player_widget.video_player.position() == 0


# ----------------------------------------------------------------- panneau de playlists
def test_delete_dialog_confirmation_flow(qapp):
    from pyplayer.ui.widget.dock_widget import DeletePlaylistDialog
    dialog = DeletePlaylistDialog([("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")])
    assert not dialog.btn_delete.isEnabled()
    dialog.radio_buttons[0].setChecked(True)
    dialog.radio_buttons[2].setChecked(True)
    assert dialog.btn_delete.isEnabled()
    dialog.show_confirm_dialog()
    assert dialog.confirm_dialog is not None
    texts = " ".join(l.text() for l in dialog.confirm_dialog.findChildren(QtWidgets.QLabel))
    assert "2 playlists" in texts
    dialog.back_to_selection()                                  # « Revoir la sélection » : la fenêtre principale n'est pas rejetée
    assert dialog._back_to_selection_flag is False or dialog.result() != QtWidgets.QDialog.DialogCode.Rejected
    dialog.show_confirm_dialog()
    dialog.final_delete()                                       # confirmation finale
    assert dialog.selected_playlists == ["a", "c"] and dialog.result() == QtWidgets.QDialog.DialogCode.Accepted
    dialog.deleteLater()


def test_delete_dialog_single_selection_and_cancel(qapp):
    from pyplayer.ui.widget.dock_widget import DeletePlaylistDialog
    dialog = DeletePlaylistDialog([("a", "Alpha")])
    dialog.radio_buttons[0].setChecked(True)
    dialog.show_confirm_dialog()
    assert "'Alpha'" in " ".join(l.text() for l in dialog.confirm_dialog.findChildren(QtWidgets.QLabel))
    dialog.cancel_confirm()
    assert dialog.selected_playlists == []
    dialog.deleteLater()


class FakeDrop:
    """Événement de dépôt minimal (QDropEvent ne permet pas de choisir la source)."""
    def __init__(self, source, mime, pos):
        self._source, self._mime, self._pos = source, mime, pos
        self.ignored = self.accepted = False

    def source(self): return self._source
    def mimeData(self): return self._mime
    def position(self): return QtCore.QPointF(self._pos)
    def ignore(self): self.ignored = True
    def acceptProposedAction(self): self.accepted = True


def test_list_internal_drop_requests_a_move_and_never_moves_items_itself(qapp, media_dir):
    from pyplayer.api.playlist import Playlist
    from pyplayer.ui.widget.dock_widget import DockWidget
    playlist = Playlist("t")
    playlist.add_folder(media_dir("lib", 5))
    dock = DockWidget()
    dock.resize(330, 420)
    dock.show()
    dock.populate(playlist.videos)
    lst = dock.lstw
    requests = []
    lst.rows_move_requested.connect(lambda rows, target: requests.append((rows, target)))
    items = dock.get_video_items()
    items[0].setSelected(True)
    items[1].setSelected(True)
    pump(qapp, 30)
    target_pos = lst.visualItemRect(items[3]).center()
    event = FakeDrop(lst, QtCore.QMimeData(), target_pos)
    lst.dropEvent(event)
    assert requests == [([0, 1], 3)] and event.ignored            # Qt ne déplace rien lui-même
    below = FakeDrop(lst, QtCore.QMimeData(), QtCore.QPoint(5, lst.viewport().height() - 2))
    lst.dropEvent(below)
    assert requests[-1] == ([0, 1], 5)                            # dépôt sous la dernière ligne = fin de liste
    assert [i.video.name for i in dock.get_video_items()] == [v.name for v in playlist]
    dock.deleteLater()


def test_list_accepts_external_files_and_emits_paths(qapp, tmp_path):
    from pyplayer.ui.widget.dock_widget import ReorderableList
    lst = ReorderableList()
    dropped = []
    lst.files_dropped.connect(dropped.append)
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(str(tmp_path / "a.mp4")), QtCore.QUrl("https://x/y.mp4")])
    event = FakeDrop(None, mime, QtCore.QPoint(1, 1))
    lst.dropEvent(event)
    assert dropped == [[str(tmp_path / "a.mp4")]] and event.accepted
    lst.deleteLater()


def test_video_item_state_machine_and_text(qapp, tmp_path):
    from pyplayer.api.video import Video
    from pyplayer.ui.widget.dock_widget import VideoListItem, progress_bar
    path = tmp_path / "x.mp4"
    path.write_bytes(b"x")
    item = VideoListItem(3, Video.from_path(path), progress=0.35)
    assert item.state == "normal" and item.main_text == "3 ➤  x.mp4" and item.progress_text == progress_bar(0.35)
    item.is_current = True
    assert item.state == "current"
    item.is_current = False
    assert item.state == "read" and item.is_read                  # on quitte une vidéo : elle devient « lue »
    item.missing = True
    assert item.state == "missing"
    item.missing = False
    item.is_read = False
    item.set_progress(1.0, finished=True)
    assert item.is_read and item.progress_text == "▰" * 10
    assert progress_bar(-1) == "▱" * 10 and progress_bar(5) == "▰" * 10
    assert str(item).startswith("VideoListItem[3:")
