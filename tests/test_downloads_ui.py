"""Interface des téléchargements : lignes d'état, panneau, bulle de lien, presse-papiers, playlist, bascule vers le local."""

import dataclasses
import json
import threading
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from pyplayer.api import downloads as dl
from pyplayer.api.links import Link
from pyplayer.ui.widget import downloads_panel as panel_module
from pyplayer.ui.widget.downloads_panel import DownloadOptionsDialog, status_text, summary_text
from tests.test_downloads import FakeProcess, progress, until  # noqa: F401
from tests.test_ui import pump, qapp, wait_until, window  # noqa: E402,F401 -- fixtures

URL = "https://www.youtube.com/watch?v=abc123"


def item(**kw):
    base = dict(id="a1", url=URL, out_dir="/tmp", options={}, title="Mon film")
    base.update(kw)
    return dl.DownloadItem(**base)


# ----------------------------------------------------------------- textes (sans fenêtre)
def test_status_text_for_every_state(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 2048)
    assert status_text(item(state=dl.State.QUEUED)) == "En attente"
    assert status_text(item(state=dl.State.QUEUED, error="Nouvelle tentative (1/3)…")) == "Nouvelle tentative (1/3)…"
    running = status_text(item(state=dl.State.RUNNING, progress=0.5, downloaded=5 * 1024 * 1024, total=10 * 1024 * 1024,
                               speed=2 * 1024 * 1024, eta=90))
    assert running == "50 % · 5.0 Mo / 10.0 Mo · 2.0 Mo/s · reste 1:30"
    assert status_text(item(state=dl.State.RUNNING, downloaded=2048)).endswith("2.0 Ko")
    assert status_text(item(state=dl.State.PAUSED, progress=0.4)) == "En pause · 40 %"
    assert status_text(item(state=dl.State.DONE, filepath=str(f))) == "Terminé · 2.0 Ko"
    assert status_text(item(state=dl.State.DONE, archived=True)).startswith("Déjà téléchargé")
    assert status_text(item(state=dl.State.DONE, filepath="/introuvable.mp4")) == "Terminé"
    assert status_text(item(state=dl.State.ERROR, error="Video unavailable")) == "Erreur : Video unavailable"
    assert status_text(item(state=dl.State.CANCELLED)) == "Annulé"


def test_summary_text_counts_states_and_total_speed():
    assert summary_text([]) == "Aucun téléchargement"
    items = [item(id="1", state=dl.State.RUNNING, speed=1024 * 1024), item(id="2", state=dl.State.RUNNING, speed=1024 * 1024),
             item(id="3", state=dl.State.QUEUED), item(id="4", state=dl.State.DONE), item(id="5", state=dl.State.ERROR)]
    assert summary_text(items) == "2 en cours · 1 en attente · 1 terminé(s) · 1 en erreur · 2.0 Mo/s"


# ----------------------------------------------------------------- panneau et moteur
@pytest.fixture
def fake_downloads(window):
    """Remplace yt-dlp par de faux processus : on pilote la progression à la main."""
    processes = []

    def factory(args):
        process = FakeProcess([progress(40, 100)], hold=True)
        process.args = args
        processes.append(process)
        return process
    window.downloads._command_provider = lambda: ["fake-ytdlp"]
    window.downloads._process_factory = factory
    window.downloads._playlist = None
    return processes


def test_downloads_tab_exists_and_ctrl_shift_d_focuses_the_input(window, qapp):
    tabs = window.dock_widget.tab_widget
    assert tabs.tabText(tabs.count() - 1) == "TÉLÉCHARGEMENTS" and tabs.widget(tabs.count() - 1) is window.downloads_panel
    QtGui.QGuiApplication.clipboard().setText("")
    window.menubar_widget.act_download.trigger()
    assert tabs.currentWidget() is window.downloads_panel and window.dock_widget.isVisible()


def test_submitting_a_link_queues_it_with_the_chosen_quality_and_shows_progress(window, qapp, fake_downloads, tmp_path):
    panel = window.downloads_panel
    window.settings.set("download_dir", str(tmp_path / "dl"))
    panel.combo_quality.setCurrentIndex(panel.combo_quality.findData("720p"))
    panel.edit_url.setText(URL)
    panel.btn_add.click()
    assert panel.edit_url.text() == ""
    assert wait_until(qapp, lambda: panel.model.rowCount() == 1 and panel.model.rows[0].downloaded == 40, 5)
    args = fake_downloads[0].args
    assert "--format=bv*[height<=720]+ba/b[height<=720]" in args and args[-2:] == ["--", URL]
    assert f"--paths=home:{tmp_path / 'dl'}" in args
    assert window.settings.get("download_preset") == "720p"                    # la qualité est mémorisée
    assert "40 %" in status_text(panel.model.rows[0]) and "en cours" in panel.lbl_summary.text()


def test_submitting_garbage_reports_a_message_and_adds_nothing(window, qapp, fake_downloads):
    panel = window.downloads_panel
    panel.edit_url.setText("pas un lien du tout")
    panel.btn_add.click()
    assert "Aucun lien valide" in window.osd.currentMessage() and panel.model.rowCount() == 0


def test_several_links_in_one_paste_are_all_queued(window, qapp, fake_downloads):
    window.downloads_panel.add_text(f"{URL}\nhttps://vimeo.com/123456\ndu bruit {URL}")
    assert wait_until(qapp, lambda: window.downloads_panel.model.rowCount() == 2, 5)


def test_pause_resume_cancel_and_remove_from_the_context_actions(window, qapp, fake_downloads):
    panel = window.downloads_panel
    panel.add_text(URL)
    assert wait_until(qapp, lambda: panel.model.rowCount() == 1 and panel.model.rows[0].state == dl.State.RUNNING, 5)
    current = panel.model.rows[0]
    labels = [label for label, _ in panel.actions_for([current])]
    assert "Mettre en pause" in labels and "Annuler" in labels and "Lire en ligne maintenant" in labels
    actions = dict(panel.actions_for([current]))
    actions["Mettre en pause"]()
    assert wait_until(qapp, lambda: panel.model.rows[0].state == dl.State.PAUSED, 5)
    assert "Reprendre" in [label for label, _ in panel.actions_for([panel.model.rows[0]])]
    dict(panel.actions_for([panel.model.rows[0]]))["Reprendre"]()
    assert wait_until(qapp, lambda: panel.model.rows[0].state == dl.State.RUNNING, 5)
    dict(panel.actions_for([panel.model.rows[0]]))["Annuler"]()
    assert wait_until(qapp, lambda: panel.model.rows[0].state == dl.State.CANCELLED, 5)
    dict(panel.actions_for([panel.model.rows[0]]))["Retirer de la liste"]()
    assert wait_until(qapp, lambda: panel.model.rowCount() == 0, 5)
    assert panel.actions_for([]) == []


def test_playing_an_unfinished_item_streams_it_and_a_finished_one_opens_the_file(window, qapp, fake_downloads, tmp_path):
    panel = window.downloads_panel
    streamed, opened = [], []
    panel.stream_requested.connect(streamed.append)
    panel.play_requested.connect(opened.append)
    panel.play_item(item(state=dl.State.RUNNING))
    assert streamed == [URL]
    real = tmp_path / "film.mp4"
    real.write_bytes(b"x")
    panel.play_item(item(state=dl.State.DONE, filepath=str(real)))
    panel.play_item(item(state=dl.State.DONE, filepath=str(tmp_path / "absent.mp4")))     # fichier supprimé : rien
    panel.play_item(None)
    assert opened == [str(real)] and streamed == [URL]


def test_playlist_links_are_expanded_automatically(window, qapp, fake_downloads, monkeypatch):
    entries = [dl.PlaylistEntry(f"https://www.youtube.com/watch?v=v{i}", f"Vidéo {i}", i) for i in range(1, 4)]
    window.downloads._expander = lambda url, opts: ("Ma liste", entries)
    window.downloads_panel.add_text("https://www.youtube.com/playlist?list=PL123")
    assert wait_until(qapp, lambda: window.downloads_panel.model.rowCount() == 3, 5)
    assert all(row.group == "Ma liste" for row in window.downloads_panel.model.rows)
    assert "3 vidéo(s)" in window.osd.currentMessage() or wait_until(
        qapp, lambda: "3 vidéo(s)" in window.osd.currentMessage(), 3)


def test_finished_download_is_announced_added_to_the_downloads_playlist_and_keeps_the_file(window, qapp, tmp_path):
    file = tmp_path / "Sortie.mp4"
    file.write_bytes(b"x")
    window._on_download_finished(item(state=dl.State.DONE, filepath=str(file), title="Sortie"))
    assert "Téléchargement terminé : Sortie" in window.osd.currentMessage()
    playlist = next(p for p in window.manager.playlists if p.name == "Téléchargements")
    assert [v.path for v in playlist] == [file]
    window._on_download_finished(item(state=dl.State.DONE, filepath=str(file), title="Sortie"))    # pas de doublon
    assert len(playlist) == 1
    window.settings.set("downloads_to_playlist", False)
    other = tmp_path / "Autre.mp4"
    other.write_bytes(b"x")
    window._on_download_finished(item(id="b2", state=dl.State.DONE, filepath=str(other)))
    assert len(playlist) == 1


def test_streaming_switches_to_the_local_file_at_the_same_position_when_it_arrives(window, qapp, tmp_path, monkeypatch):
    file = tmp_path / "Local.mp4"
    file.write_bytes(b"x")
    opened, saved = [], []
    monkeypatch.setattr(window, "open_paths", lambda paths, **kw: opened.append(paths))
    monkeypatch.setattr(window.resume, "update", lambda path, position, duration: saved.append((path, position, duration)))
    monkeypatch.setattr(window.player, "position", lambda: 125_000)
    monkeypatch.setattr(window.player, "duration", lambda: 600_000)
    window._streaming_origin = URL
    window._on_download_finished(item(state=dl.State.DONE, filepath=str(file)))
    assert opened == [[str(file)]] and saved == [(file, 125_000, 600_000)]
    opened.clear()
    window._streaming_origin = "https://autre.exemple/watch?v=zzz"                 # un autre flux : pas de bascule
    window._on_download_finished(item(state=dl.State.DONE, filepath=str(file)))
    assert opened == []


def test_loading_a_local_file_ends_the_streaming_state(window, qapp, tmp_path):
    window._streaming_origin = URL
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    window.open_paths([str(f)])
    assert window._streaming_origin == ""


def test_closing_the_window_stops_downloads_and_keeps_them_for_the_next_start(tmp_path, qapp, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "userhome"))
    from pyplayer.ui.main_window import MainWindow
    first = MainWindow()
    first.show()
    process = FakeProcess([progress(10, 100)], hold=True)
    first.downloads._command_provider = lambda: ["fake"]
    first.downloads._process_factory = lambda args: process
    first.downloads_panel.add_text(URL)
    assert until(lambda: any(i.downloaded == 10 for i in first.downloads.items()))
    first.close()
    assert process.terminated
    saved = json.loads((tmp_path / "home" / "downloads.json").read_text(encoding="utf-8"))
    assert saved["items"][0]["state"] == "queued" and saved["items"][0]["url"] == URL      # reprise automatique plus tard
    first.deleteLater()
    second = MainWindow()
    assert [i.url for i in second.downloads.items()] == [URL]
    assert second.downloads_panel.model.rowCount() == 1                                     # la liste est restaurée à l'écran
    second.downloads.shutdown(save=False)
    second.close()
    second.deleteLater()


# ----------------------------------------------------------------- bulle de lien et presse-papiers
def test_copying_a_video_link_offers_it_once_and_ignores_other_text(window, qapp):
    toast = window.player_widget.toast
    clipboard = QtGui.QGuiApplication.clipboard()
    clipboard.setText("juste une phrase, rien à télécharger")
    pump(qapp, 50)
    assert not toast.isVisible()
    clipboard.setText(f"Regarde ça : {URL}")
    assert wait_until(qapp, toast.isVisible, 3)
    assert toast.link.url == URL and toast.btn_play.isVisible() and toast.title.text() == "Lien détecté"
    toast.dismiss()
    clipboard.setText(URL)                                    # même lien recopié : déjà proposé, on ne harcèle pas
    pump(qapp, 100)
    assert not toast.isVisible()


def test_clipboard_watching_can_be_turned_off(window, qapp):
    window.menubar_widget.act_watch_clipboard.setChecked(False)
    assert window.settings.get("watch_clipboard") is False
    QtGui.QGuiApplication.clipboard().setText("https://vimeo.com/987654")
    pump(qapp, 100)
    assert not window.player_widget.toast.isVisible()


def test_toast_buttons_download_play_or_ignore(window, qapp, fake_downloads, monkeypatch):
    toast = window.player_widget.toast
    played = []
    monkeypatch.setattr(window, "open_url", lambda url: played.append(url))
    toast.offer(Link(URL, "youtube.com", "page", "youtube.com/watch"))
    toast.btn_play.click()
    assert played == [URL] and not toast.isVisible()
    toast.offer(Link(URL, "youtube.com", "page", "youtube.com/watch"))
    toast.btn_download.click()
    assert wait_until(qapp, lambda: window.downloads_panel.model.rowCount() == 1, 5)
    assert "Ajouté aux téléchargements" in window.osd.currentMessage()
    dismissed = []
    toast.dismissed.connect(lambda: dismissed.append(1))
    toast.offer(Link(URL, "youtube.com", "page", "x"))
    toast.btn_ignore.click()
    assert dismissed == [1] and not toast.isVisible()


def test_playlist_toast_hides_the_play_button_and_relabels_download(window, qapp):
    toast = window.player_widget.toast
    toast.offer(Link("https://www.youtube.com/playlist?list=PL1", "youtube.com", "playlist", "x"))
    assert toast.title.text() == "Playlist détectée" and toast.btn_download.text() == "Télécharger la playlist"
    assert not toast.btn_play.isVisible()
    toast.dismiss()


def test_toast_hides_itself_after_the_delay(window, qapp, monkeypatch):
    toast = window.player_widget.toast
    toast.offer(Link(URL, "youtube.com", "page", "x"))
    toast._timer.setInterval(30)
    toast._timer.start()
    assert wait_until(qapp, lambda: not toast.isVisible(), 2)


# ----------------------------------------------------------------- options avancées
def test_options_dialog_roundtrip_and_validation(qapp, tmp_path):
    options = dl.DownloadOptions(preset="720p", subtitles=True, sponsorblock="mark", rate_limit="2M",
                                 playlist_items="1-3", container="mkv")
    dialog = DownloadOptionsDialog(options, str(tmp_path), None)
    assert dialog.result_options() == dataclasses.replace(options, sub_langs="fr,en")
    assert dialog.result_folder() == str(tmp_path)
    dialog.edit_rate.setText("beaucoup")
    dialog.btn_ok.click()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted and "Limite de débit" in dialog.lbl_error.text()
    dialog.edit_rate.setText("500K")
    dialog.edit_items.setText("1;2")
    dialog.btn_ok.click()
    assert "Sélection de playlist" in dialog.lbl_error.text()
    dialog.edit_items.setText("2-4")
    dialog.btn_ok.click()
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert dialog.result_options().rate_limit == "500K" and dialog.result_options().playlist_items == "2-4"
    dialog.deleteLater()


def test_options_dialog_is_saved_by_the_window_and_used_for_new_downloads(window, qapp, fake_downloads, tmp_path, monkeypatch):
    from pyplayer.ui import main_window as mw

    class Fake(DownloadOptionsDialog):
        def exec(self):
            self.combo_preset.setCurrentIndex(self.combo_preset.findData("audio_mp3"))
            self.edit_rate.setText("1M")
            self.edit_folder.setText(str(tmp_path / "musique"))
            self.check_playlist.setChecked(False)
            return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(mw, "DownloadOptionsDialog", Fake)
    window.edit_download_options()
    assert window.settings.get("download_dir") == str(tmp_path / "musique")
    assert window.settings.get("download_options")["rate_limit"] == "1M"
    assert window.downloads_panel.combo_quality.currentData() == "audio_mp3"
    window.downloads_panel.add_text(URL)
    assert wait_until(qapp, lambda: len(fake_downloads) == 1, 5)
    args = fake_downloads[0].args
    assert "--extract-audio" in args and "--limit-rate=1M" in args and f"--paths=home:{tmp_path / 'musique'}" in args


def test_rows_are_painted_in_every_state_without_errors(window, qapp):
    panel = window.downloads_panel
    states = [dl.State.QUEUED, dl.State.RUNNING, dl.State.PAUSED, dl.State.DONE, dl.State.ERROR, dl.State.CANCELLED]
    panel.model.set_items([item(id=str(i), state=s, progress=0.3 * (i % 4), title="Titre " + "très long " * 20, group="Liste",
                                index=i, error="ça a échoué " * 10) for i, s in enumerate(states)])
    panel.resize(320, 500)
    panel.show()
    pump(qapp, 50)
    assert not panel.view.viewport().grab().toImage().isNull()
    panel.model.set_items([])
    assert panel.model.rowCount() == 0
    panel.hide()


def test_reset_includes_the_downloads_list_but_never_the_downloaded_files(tmp_path):
    from pyplayer.api import reset
    (tmp_path / "downloads.json").write_text("{}", encoding="utf-8")
    media = tmp_path / "Film téléchargé.mp4"
    media.write_bytes(b"x")
    assert reset.reset_data(tmp_path, [reset.DOWNLOADS]).deleted_files == 1
    assert not (tmp_path / "downloads.json").exists() and media.exists()


def test_threads_never_touch_the_interface_directly(window, qapp, fake_downloads):
    """Les événements du moteur arrivent d'un fil de travail ; le modèle ne doit être modifié que dans le fil de l'UI."""
    seen = []
    original = window.downloads_panel.model.upsert

    def spy(item):
        seen.append(threading.current_thread() is threading.main_thread())
        original(item)
    window.downloads_panel.model.upsert = spy
    window.downloads_panel.add_text(URL)
    assert wait_until(qapp, lambda: len(seen) >= 2, 5)
    assert all(seen)
