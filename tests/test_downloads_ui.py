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
def fake_downloads(window, monkeypatch):
    """Remplace yt-dlp par de faux processus : on pilote la progression à la main. FFmpeg est supposé présent (les
    runners Windows n'en ont pas : sans lui le moteur choisit des fichiers uniques)."""
    monkeypatch.setattr(dl, "ffmpeg_dir", lambda: "/opt/ffmpeg")
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


# ----------------------------------------------------------------- outils (yt-dlp, ffmpeg) et mises à jour
def test_missing_ytdlp_offers_to_install_then_replays_the_link(window, qapp, fake_downloads, monkeypatch):
    window.downloads._command_provider = lambda: None                   # yt-dlp absent
    asked, installed = [], []
    monkeypatch.setattr(window, "confirm", lambda title, message, informative="": asked.append(title) or True)

    def fake_install(progress=None, cancelled=None, **kw):
        installed.append(1)
        window.downloads._command_provider = lambda: ["fake-ytdlp"]       # ... et le voilà installé
        return Path("/tmp/yt-dlp")
    monkeypatch.setattr("pyplayer.api.tools.install_ytdlp", fake_install)
    monkeypatch.setattr(window, "run_task", lambda title, label, work: (True, work(lambda *a: None, lambda: False)))
    window.downloads_panel.add_text(URL)
    assert asked == ["yt-dlp est nécessaire"] and installed == [1]
    assert wait_until(qapp, lambda: window.downloads_panel.model.rowCount() == 1, 5)    # le lien a été rejoué


def test_declining_the_ytdlp_install_changes_nothing(window, qapp, monkeypatch):
    window.downloads._command_provider = lambda: None
    ran = []
    monkeypatch.setattr(window, "confirm", lambda *a, **k: False)
    monkeypatch.setattr(window, "run_task", lambda *a: ran.append(1) or (True, None))
    window.downloads_panel.add_text(URL)
    assert ran == [] and window.downloads_panel.model.rowCount() == 0


def test_a_failed_install_is_reported_without_crashing(window, qapp, monkeypatch):
    shown = []
    monkeypatch.setattr(window, "inform", lambda title, message: shown.append((title, message)))
    monkeypatch.setattr(window, "run_task", lambda *a: (False, "Somme de contrôle incorrecte"))
    window._install_ytdlp()
    assert shown == [("Installation impossible", "Somme de contrôle incorrecte")]
    shown.clear()
    monkeypatch.setattr(window, "run_task", lambda *a: (False, "Téléchargement annulé."))
    window._install_ytdlp()
    assert shown == []                                                   # une annulation n'est pas une erreur à afficher


def test_online_playback_without_ytdlp_offers_the_install_and_resumes(window, qapp, monkeypatch):
    from pyplayer.api import online
    calls, offered = [], []
    monkeypatch.setattr(online, "resolve", lambda page: (_ for _ in ()).throw(online.OnlineError(
        "yt-dlp n'est pas installé : Support → Mettre à jour yt-dlp")))
    monkeypatch.setattr(window, "offer_install_ytdlp", lambda then=None: offered.append(then))
    window.open_url("https://site.exemple/watch?v=1")
    assert wait_until(qapp, lambda: len(offered) == 1, 5)
    monkeypatch.setattr(window, "open_url", lambda url: calls.append(url))
    offered[0]()                                                         # « then » rejoue l'ouverture
    assert calls == ["https://site.exemple/watch?v=1"]


def test_ffmpeg_absence_is_announced_once(window, qapp, fake_downloads, monkeypatch):
    monkeypatch.setattr(dl, "ffmpeg_dir", lambda: None)
    window.downloads_panel.add_text(URL)
    assert "FFmpeg absent" in window.osd.currentMessage()
    window.osd.clear()
    window.downloads_panel.add_text("https://vimeo.com/55555")
    assert "FFmpeg absent" not in window.osd.currentMessage()


def test_ytdlp_menu_action_updates_only_when_needed(window, qapp, monkeypatch):
    from pyplayer.api.tools import ToolStatus
    installs = []
    monkeypatch.setattr(window, "_install_ytdlp", lambda then=None: installs.append(1))
    monkeypatch.setattr(window, "offer_install_ytdlp", lambda then=None: installs.append("offre"))
    monkeypatch.setattr(window, "run_task", lambda *a: (True, ToolStatus("yt-dlp_linux", True, True)))
    window.install_ytdlp_action()
    assert installs == [] and "à jour" in window.osd.currentMessage()
    monkeypatch.setattr(window, "run_task", lambda *a: (True, ToolStatus("yt-dlp_linux", True, False)))
    window.install_ytdlp_action()
    assert installs == [1]                                               # installé mais périmé : mise à jour directe
    monkeypatch.setattr(window, "run_task", lambda *a: (True, ToolStatus("yt-dlp_linux", False, False)))
    window.install_ytdlp_action()
    assert installs == [1, "offre"]                                      # absent : on propose l'installation


def test_manual_update_check_with_a_new_version_shows_the_dialog_and_installs(window, qapp, monkeypatch):
    from pyplayer.api import updater
    info = updater.UpdateInfo("9.9.9", "v9.9.9", "## Nouveautés\n- tout", "https://github.com/x/y/releases/tag/v9.9.9",
                              "linux-binary", "pyplayer-9.9.9-linux-x86_64", "https://github.com/x/y/a", "a" * 64, 1000)
    monkeypatch.setattr(updater, "check", lambda version: info)
    chosen = {}

    class FakeDialog:
        INSTALL, PAGE, LATER = 1, 2, 0

        def __init__(self, shown_info, current, parent=None):
            chosen["info"], chosen["current"] = shown_info, current
            self.choice = 1

        def exec(self):
            return 1
    from pyplayer.ui import main_window as mw
    monkeypatch.setattr(mw, "UpdateDialog", FakeDialog)
    applied = []
    monkeypatch.setattr(window, "install_update", lambda i: applied.append(i))
    window.check_for_updates(manual=True)
    assert wait_until(qapp, lambda: bool(applied), 5)
    assert applied == [info] and chosen["info"] is info and window._pending_update is info
    assert "9.9.9" in window.menubar_widget.act_check_update.text()
    assert window.settings.get("last_update_check") > 0


def test_automatic_check_is_silent_when_up_to_date_and_discreet_when_not(window, qapp, monkeypatch):
    from pyplayer.api import updater
    monkeypatch.setattr(updater, "check", lambda version: None)
    window.check_for_updates(manual=False)
    pump(qapp, 200)
    assert window._pending_update is None and "à jour" not in window.osd.currentMessage()
    info = updater.UpdateInfo("9.9.9", "v9.9.9", "", "https://x", "manual")
    monkeypatch.setattr(updater, "check", lambda version: info)
    window.check_for_updates(manual=False)
    assert wait_until(qapp, lambda: window._pending_update is info, 5)
    assert "9.9.9 est disponible" in window.osd.currentMessage()


def test_update_check_errors_are_silent_in_background_and_explained_when_manual(window, qapp, monkeypatch):
    from pyplayer.api import updater
    monkeypatch.setattr(updater, "check", lambda version: (_ for _ in ()).throw(fetch_error("Connexion impossible")))
    shown = []
    monkeypatch.setattr(window, "inform", lambda title, message: shown.append(message))
    window.check_for_updates(manual=False)
    pump(qapp, 300)
    assert shown == []
    window.check_for_updates(manual=True)
    assert wait_until(qapp, lambda: bool(shown), 5) and "Connexion impossible" in shown[0]
    assert window.settings.get("last_update_check") == 0.0              # un échec ne repousse pas la prochaine vérification


def fetch_error(message):
    from pyplayer.api.fetch import FetchError
    return FetchError(message)


def test_startup_check_respects_the_setting_the_environment_and_the_daily_schedule(window, qapp, monkeypatch):
    checks = []
    monkeypatch.setattr(window, "check_for_updates", lambda manual=True: checks.append(manual))
    window._auto_check_updates()                                         # variable d'environnement des tests : rien
    assert checks == []
    monkeypatch.delenv("PYPLAYER_NO_UPDATE_CHECK")
    window.settings.set("auto_update_check", False)
    window._auto_check_updates()
    assert checks == []
    window.settings.set("auto_update_check", True)
    window.settings.set("last_update_check", __import__("time").time() - 100)      # vérifié il y a 100 s : trop tôt
    window._auto_check_updates()
    assert checks == []
    window.settings.set("last_update_check", 0.0)
    window._auto_check_updates()
    assert checks == [False]


def test_install_update_branches(window, qapp, monkeypatch):
    from pyplayer.api import updater
    info = updater.UpdateInfo("9.9.9", "v9.9.9", "", "https://x", "windows-installer", "setup.exe", "https://github.com/a", "a" * 64)
    events = []
    monkeypatch.setattr(updater, "run_installer", lambda path: events.append(("installer", path)))
    monkeypatch.setattr(updater, "relaunch", lambda: events.append(("relaunch",)))
    monkeypatch.setattr(window, "close", lambda: events.append(("close",)) or True)
    monkeypatch.setattr(window, "inform", lambda title, message: events.append(("inform", title)))
    monkeypatch.setattr(window, "_reveal_path", lambda p: events.append(("reveal", p)))
    monkeypatch.setattr(window, "confirm", lambda *a, **k: True)
    monkeypatch.setattr(window, "run_task", lambda *a: (True, updater.ApplyResult("run-installer", Path("/tmp/setup.exe"))))
    window.install_update(info)
    assert events == [("installer", Path("/tmp/setup.exe")), ("close",)]
    events.clear()
    monkeypatch.setattr(window, "confirm", lambda *a, **k: False)            # l'utilisateur refuse au dernier moment
    window.install_update(info)
    assert events == []
    monkeypatch.setattr(window, "run_task", lambda *a: (True, updater.ApplyResult("restart", Path("/opt/pyplayer"))))
    window.install_update(info)
    assert events == [("inform", "Mise à jour installée"), ("relaunch",), ("close",)]
    events.clear()
    monkeypatch.setattr(window, "run_task", lambda *a: (True, updater.ApplyResult("saved", Path("/tmp/new.exe"))))
    window.install_update(info)
    assert events == [("inform", "Mise à jour téléchargée"), ("reveal", str(Path("/tmp/new.exe")))]
    events.clear()
    monkeypatch.setattr(window, "run_task", lambda *a: (False, "Somme de contrôle incorrecte"))
    window.install_update(info)
    assert events == [("inform", "Mise à jour impossible")]


# ----------------------------------------------------------------- fenêtres de progression et de mise à jour
def test_task_dialog_runs_in_a_thread_reports_progress_and_returns_the_result(qapp):
    from pyplayer.ui.dialogs import TaskProgressDialog
    seen = []

    def work(progress, cancelled):
        for step in (250, 500, 1000):
            progress(step, 1000)
            seen.append(threading.current_thread() is threading.main_thread())
        return "terminé"
    dialog = TaskProgressDialog("Tâche", "Travail…", work)
    QtCore.QTimer.singleShot(0, dialog.show)
    dialog.exec()
    assert dialog.ok and dialog.result == "terminé" and seen == [False, False, False]    # travail hors du fil de l'UI
    assert dialog.bar.value() == 1000
    dialog.deleteLater()


def test_task_dialog_reports_errors_and_supports_cancellation(qapp):
    from pyplayer.ui.dialogs import TaskProgressDialog

    def broken(progress, cancelled):
        raise RuntimeError("réseau coupé")
    failing = TaskProgressDialog("Tâche", "…", broken)
    QtCore.QTimer.singleShot(0, failing.show)
    failing.exec()
    assert not failing.ok and failing.error == "réseau coupé"
    failing.deleteLater()

    def waiting(progress, cancelled):
        while not cancelled():
            time.sleep(0.01)
        raise RuntimeError("Téléchargement annulé.")
    import time
    cancelling = TaskProgressDialog("Tâche", "…", waiting)
    QtCore.QTimer.singleShot(0, cancelling.show)
    QtCore.QTimer.singleShot(150, cancelling.btn_cancel.click)
    cancelling.exec()
    assert not cancelling.ok and "annulé" in cancelling.error
    cancelling.deleteLater()


def test_update_dialog_choices_and_manual_mode(qapp):
    from pyplayer.api import updater
    from pyplayer.ui.dialogs import UpdateDialog
    ok = updater.UpdateInfo("0.3.0", "v0.3.0", "## Nouveautés\n- tout", "https://x", "windows-installer", "s.exe",
                            "https://github.com/a", "a" * 64, 5_000_000)
    dialog = UpdateDialog(ok, "0.2.0")
    assert dialog.btn_install.isEnabled() and "SHA-256" in dialog.lbl_trust.text() and "Nouveautés" in dialog.notes.toPlainText()
    dialog.btn_install.click()
    assert dialog.choice == UpdateDialog.INSTALL
    manual = updater.UpdateInfo("0.3.0", "v0.3.0", "", "https://x", "manual")
    dialog2 = UpdateDialog(manual, "0.2.0")
    assert not dialog2.btn_install.isEnabled() and "automatiquement" in dialog2.lbl_trust.text()
    assert "Aucune note" in dialog2.notes.toPlainText()
    dialog2.btn_page.click()
    assert dialog2.choice == UpdateDialog.PAGE
    dialog.deleteLater()
    dialog2.deleteLater()
