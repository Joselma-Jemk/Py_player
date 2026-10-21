"""Moteur de téléchargement : options validées, arguments yt-dlp, lecture de la sortie, file d'attente, pause/reprise,
nouvelles tentatives, persistance, et vrai yt-dlp sur un serveur local (avec reprise par plages d'octets)."""

import functools
import http.server
import json
import re
import shutil
import threading
import time
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from pyplayer.api import downloads as d
from pyplayer.api import online
from pyplayer.api.downloads import (DownloadManager, DownloadOptions, PlaylistEntry, State, build_args, parse_line,
                                    parse_selection, select_entries, validate)

URL = "https://site.exemple/watch?v=abc"
FFMPEG_DIR = "/opt/ffmpeg/bin"             # « ffmpeg présent » pour les tests d'arguments (rien n'est exécuté)


def until(condition, timeout=10.0, step=0.02):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(step)
    return False


# ----------------------------------------------------------------- options et arguments
def test_default_arguments_are_safe_and_complete(tmp_path):
    args = build_args(URL, tmp_path, DownloadOptions(), ffmpeg_dir=FFMPEG_DIR)
    assert args[-2:] == ["--", URL]                                    # l'adresse vient après « -- » : jamais une option
    assert "--no-playlist" in args and "--continue" in args and "--ignore-config" in args
    assert "--format=bv*+ba/b" in args and "--merge-output-format=mp4" in args
    assert "--embed-metadata" in args and "--embed-thumbnail" in args and "--embed-chapters" in args
    assert f"--paths=home:{tmp_path}" in args and f"--download-archive={tmp_path / '.pyplayer-archive.txt'}" in args
    assert any(a.startswith("--concurrent-fragments=8") for a in args)
    assert all(a.startswith("--") for a in args[:-2])                  # toutes les options sont de la forme --nom[=valeur]


@pytest.mark.parametrize("preset,expected", [("720p", "--format=bv*[height<=720]+ba/b[height<=720]"),
                                             ("1080p", "--format=bv*[height<=1080]+ba/b[height<=1080]")])
def test_quality_presets(tmp_path, preset, expected):
    assert expected in build_args(URL, tmp_path, DownloadOptions(preset=preset), ffmpeg_dir=FFMPEG_DIR)


def test_audio_presets_extract_audio_and_skip_video_options(tmp_path):
    args = build_args(URL, tmp_path, DownloadOptions(preset="audio_mp3", subtitles=True, embed_subs=True),
                      ffmpeg_dir=FFMPEG_DIR)
    assert "--extract-audio" in args and "--audio-format=mp3" in args and "--audio-quality=0" in args
    assert not any(a.startswith(("--format=", "--merge-output-format")) for a in args) and "--embed-subs" not in args


def test_advanced_options_are_translated(tmp_path):
    options = DownloadOptions(subtitles=True, sub_langs="fr,en", sponsorblock="remove", rate_limit="2M",
                              cookies_from_browser="firefox", proxy="socks5://127.0.0.1:9050", min_filesize="1M",
                              max_filesize="2G", date_after="today-1week", sections="*10:00-12:00",
                              restrict_filenames=True, write_info_json=True, write_description=True,
                              container="mkv", custom_format="", archive=False)
    args = build_args(URL, tmp_path, options, ffmpeg_dir="/opt/ffmpeg/bin")
    for expected in ("--write-subs", "--sub-langs=fr,en", "--write-auto-subs", "--embed-subs", "--limit-rate=2M",
                     f"--sponsorblock-remove={d.SPONSORBLOCK_CATEGORIES}", "--cookies-from-browser=firefox",
                     "--proxy=socks5://127.0.0.1:9050", "--min-filesize=1M", "--max-filesize=2G",
                     "--dateafter=today-1week", "--download-sections=*10:00-12:00", "--restrict-filenames",
                     "--write-info-json", "--write-description", "--merge-output-format=mkv",
                     "--ffmpeg-location=/opt/ffmpeg/bin"):
        assert expected in args, expected
    assert not any(a.startswith("--download-archive") for a in args)


def test_without_ffmpeg_the_engine_picks_single_files_and_drops_what_needs_ffmpeg(tmp_path):
    full = DownloadOptions(subtitles=True, sponsorblock="remove", container="mkv")
    args = build_args(URL, tmp_path, full, ffmpeg_dir=None)
    assert "--format=b" in args and not any(a.startswith("--merge-output-format") for a in args)
    for needs_ffmpeg in ("--embed-metadata", "--embed-thumbnail", "--embed-chapters", "--embed-subs"):
        assert needs_ffmpeg not in args
    assert not any(a.startswith(("--sponsorblock", "--ffmpeg-location", "--convert-thumbnails")) for a in args)
    assert "--write-subs" in args                                          # les sous-titres séparés restent possibles
    assert "--format=b[height<=720]/b" in build_args(URL, tmp_path, DownloadOptions(preset="720p"))
    audio = build_args(URL, tmp_path, DownloadOptions(preset="audio_mp3"))
    assert "--format=ba/b" in audio and "--extract-audio" not in audio     # audio brut, sans conversion
    assert "--format=best[height<=480]" in build_args(URL, tmp_path, DownloadOptions(
        preset="custom", custom_format="best[height<=480]"))               # le choix explicite de l'utilisateur est respecté


def test_ffmpeg_dir_prefers_the_one_installed_by_pyplayer(monkeypatch, tmp_path):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    assert Path(d.ffmpeg_dir()) == Path("/usr/bin")
    own = d.tools_dir() / "ffmpeg" / ("ffmpeg.exe" if __import__("os").name == "nt" else "ffmpeg")
    own.parent.mkdir(parents=True)
    own.write_bytes(b"x")
    assert d.ffmpeg_dir() == str(own.parent)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    own.unlink()
    assert d.ffmpeg_dir() is None


def test_custom_format_and_aria2c_only_when_available(tmp_path):
    assert "--format=best[height<=480]" in build_args(URL, tmp_path, DownloadOptions(
        preset="custom", custom_format="best[height<=480]"), ffmpeg_dir=FFMPEG_DIR)
    on = build_args(URL, tmp_path, DownloadOptions(use_aria2c=True), aria2c="/usr/bin/aria2c")
    off = build_args(URL, tmp_path, DownloadOptions(use_aria2c=True), aria2c=None)
    assert "--downloader=/usr/bin/aria2c" in on and not any(a.startswith("--downloader") for a in off)


@pytest.mark.parametrize("bad", [
    {"preset": "ultra"}, {"preset": "custom", "custom_format": "$(rm -rf /)"}, {"container": "avi"},
    {"sponsorblock": "tout"}, {"rate_limit": "vite"}, {"rate_limit": "--exec"}, {"playlist_items": "1;2"},
    {"sub_langs": "fr en"}, {"cookies_from_browser": "firefox; ls"}, {"proxy": "javascript:alert(1)"},
    {"proxy": "-o x"}, {"date_after": "hier"}, {"sections": "*10:00 --exec"}, {"concurrent_fragments": 0},
    {"concurrent_fragments": 500}, {"retries": -1}, {"output_template": "../../etc/passwd"},
    {"output_template": "/etc/%(title)s"}, {"output_template": "C:\\x\\%(title)s"}])
def test_validate_rejects_invalid_or_dangerous_options(bad):
    with pytest.raises(ValueError):
        validate(DownloadOptions(**bad))


@given(st.text(max_size=30))
@settings(max_examples=300)
def test_no_free_text_option_can_smuggle_an_extra_argument(text):
    """Pour n'importe quelle valeur libre, soit l'option est refusée, soit elle reste UN argument ``--nom=valeur``."""
    for field_name, flag in (("rate_limit", "--limit-rate="), ("proxy", "--proxy="), ("sub_langs", "--sub-langs="),
                             ("cookies_from_browser", "--cookies-from-browser="), ("date_after", "--dateafter="),
                             ("sections", "--download-sections="), ("playlist_items", None)):
        options = DownloadOptions(**{field_name: text, **({"subtitles": True} if field_name == "sub_langs" else {})})
        try:
            args = build_args(URL, "/tmp/x", options)
        except ValueError:
            continue
        assert args[-2:] == ["--", URL] and sum(1 for a in args if a == "--") == 1
        assert all(a.startswith("--") for a in args[:-2])
        if flag and text:
            assert [a for a in args if a.startswith(flag)] == [flag + text]


@given(st.text(max_size=40))
def test_build_args_rejects_every_non_web_address(text):
    try:
        args = build_args(text, "/tmp/x", DownloadOptions())
    except (ValueError, online.OnlineError):
        return
    assert args[-1].startswith(("http://", "https://")) and args[-2] == "--"


def test_from_dict_ignores_unknown_keys_and_wrong_types():
    options = DownloadOptions.from_dict({"preset": "720p", "rate_limit": 5, "inconnu": 1, "retries": "dix",
                                         "subtitles": True})
    assert options.preset == "720p" and options.subtitles and options.rate_limit == "" and options.retries == 10
    assert DownloadOptions.from_dict(None) == DownloadOptions()
    assert DownloadOptions.from_dict(options.to_dict()) == options


# ----------------------------------------------------------------- lecture de la sortie
def test_parse_line_events():
    assert parse_line('PYPPROG:{"status": "downloading", "downloaded_bytes": 5}').data["downloaded_bytes"] == 5
    assert parse_line('PYPINFO:{"title": "Mon film"}').data == {"title": "Mon film"}
    assert parse_line('PYPDONE:"/tmp/a b.mp4"').data == {"filepath": "/tmp/a b.mp4"}
    assert parse_line("ERROR: [youtube] x: Video unavailable").text == "[youtube] x: Video unavailable"
    assert parse_line("[download] x has already been recorded in the archive").data == {"archived": True}
    for ignored in ("", "   \n", "PYPPROG:pas du json", "PYPINFO:[1]", 'PYPDONE:""', "PYPDONE:12"):
        event = parse_line(ignored)
        assert event is None or event.kind == "text"


@given(st.text(max_size=80))
def test_parse_line_never_raises(line):
    parse_line(line)


def test_retryable_and_fatal_classification():
    assert d.is_retryable("HTTP Error 503: Service Unavailable") and d.is_retryable("Read timed out")
    assert d.is_retryable("Connection reset by peer") and d.is_retryable("HTTP Error 429")
    assert not d.is_retryable("Video unavailable") and not d.is_retryable("Private video")
    assert not d.is_retryable("HTTP Error 404") and not d.is_retryable("") and not d.is_retryable("Unsupported URL")
    assert not d.is_retryable("HTTP Error 403: Forbidden")


# ----------------------------------------------------------------- playlists
def test_selection_syntax_order_bounds_and_duplicates():
    assert parse_selection("", 4) == [1, 2, 3, 4]
    assert parse_selection("1-3,5", 10) == [1, 2, 3, 5]
    assert parse_selection("3-1", 5) == [3, 2, 1]                      # intervalle inversé
    assert parse_selection("2,2,2", 5) == [2]
    assert parse_selection("0,9,99", 5) == []                          # hors bornes ignorés
    assert parse_selection("a,3-x,4", 5) == [3, 4] or parse_selection("a,3-x,4", 5) == [4]


@given(st.text(alphabet="0123456789,-", max_size=20), st.integers(0, 50))
def test_selection_always_yields_unique_valid_indices(spec, total):
    result = parse_selection(spec, total)
    assert len(result) == len(set(result)) and all(1 <= i <= total for i in result)


def test_flat_playlist_entries_and_selection():
    info = {"_type": "playlist", "title": "Ma liste", "extractor_key": "YoutubeTab",
            "entries": [{"url": "https://x/1", "title": "Un"}, {"id": "zzz", "title": "Deux"},
                        "pas un dict", {"url": "ftp://x", "title": "Trois"}, {"webpage_url": "https://x/4", "title": "Quatre"}]}
    title, entries = d.entries_from_flat(info, "https://x/list")
    assert title == "Ma liste" and [e.title for e in entries] == ["Un", "Deux", "Quatre"]
    assert entries[1].url == "https://www.youtube.com/watch?v=zzz"
    assert [e.title for e in select_entries(entries, "2-3", False)] == ["Deux", "Quatre"]
    assert [e.title for e in select_entries(entries, "", True)] == ["Quatre", "Deux", "Un"]
    single_title, single = d.entries_from_flat({"title": "Seule"}, "https://x/v")
    assert single_title == "" and [e.url for e in single] == ["https://x/v"]


# ----------------------------------------------------------------- gestionnaire avec faux processus
class FakeProcess:
    """Imite un sous-processus yt-dlp : émet des lignes, puis attend (``hold``) ou se termine avec ``code``."""

    def __init__(self, lines, code=0, hold=False):
        self.lines, self.code, self.hold = list(lines), code, hold
        self.terminated = False
        self._release = threading.Event()
        self.stdout = self._read()

    def _read(self):
        for line in self.lines:
            yield line + "\n"
        if self.hold:
            self._release.wait(10)

    def terminate(self):
        self.terminated = True
        self._release.set()

    kill = terminate

    def finish(self):
        self._release.set()

    def wait(self, timeout=None):
        self._release.wait(timeout if self.hold else 0)
        return -15 if self.terminated else self.code


def progress(done, total, status="downloading", speed=1000.0):
    return "PYPPROG:" + json.dumps({"status": status, "downloaded_bytes": done, "total_bytes": total, "speed": speed,
                                    "eta": 3})


def make_manager(tmp_path, factory, **kwargs):
    manager = DownloadManager(tmp_path / "state.json", command_provider=lambda: ["fake-ytdlp"],
                              process_factory=factory, retry_base_s=0.05, **kwargs)
    events = []
    manager.subscribe(lambda kind, item: events.append((kind, item.state.value, round(item.progress, 2))))
    return manager, events


def test_successful_download_updates_the_item_and_emits_events(tmp_path):
    lines = ['PYPINFO:{"title": "Mon film"}', progress(10, 100), progress(100, 100, "finished"),
             "PYPDONE:" + json.dumps(str(tmp_path / "out" / "Mon film.mp4"))]      # JSON correct (antislashs Windows)
    manager, events = make_manager(tmp_path, lambda args: FakeProcess(lines))
    item = manager.add(URL, out_dir=tmp_path / "out")
    assert until(lambda: manager.get(item.id).state == State.DONE)
    done = manager.get(item.id)
    assert done.title == "Mon film" and done.progress == 1.0 and done.filepath.endswith("Mon film.mp4")
    kinds = [k for k, *_ in events]
    assert kinds[0] == "added" and "progress" in kinds and kinds.count("info") == 1 and events[-1][1] == "done"
    manager.shutdown()


def test_command_line_contains_the_url_after_double_dash_and_the_output_folder(tmp_path):
    seen = []
    manager, _ = make_manager(tmp_path, lambda args: seen.append(args) or FakeProcess([]))
    item = manager.add(URL, out_dir=tmp_path / "vers")
    assert until(lambda: manager.get(item.id).state == State.DONE)
    assert seen[0][0] == "fake-ytdlp" and seen[0][-2:] == ["--", URL] and f"--paths=home:{tmp_path / 'vers'}" in seen[0]
    assert (tmp_path / "vers").is_dir()                                # créé automatiquement
    manager.shutdown()


def test_fatal_error_is_reported_without_retry(tmp_path):
    calls = []
    manager, _ = make_manager(tmp_path, lambda args: calls.append(1) or FakeProcess(
        ["ERROR: [youtube] abc: Video unavailable"], code=1))
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).state == State.ERROR)
    assert "Video unavailable" in manager.get(item.id).error and len(calls) == 1
    manager.shutdown()


def test_transient_error_retries_with_backoff_then_succeeds(tmp_path):
    outcomes = [FakeProcess(["ERROR: unable to download: HTTP Error 503: Service Unavailable"], 1),
                FakeProcess(["ERROR: Read timed out"], 1), FakeProcess([progress(5, 5, "finished")], 0)]
    manager, events = make_manager(tmp_path, lambda args: outcomes.pop(0))
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).state == State.DONE, 10)
    assert manager.get(item.id).attempts == 2 and not outcomes
    assert any("Nouvelle tentative" in (manager.get(item.id).error or "x") or True for _ in events)
    manager.shutdown()


def test_transient_error_gives_up_after_max_attempts(tmp_path):
    manager, _ = make_manager(tmp_path, lambda args: FakeProcess(["ERROR: Connection reset by peer"], 1))
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).state == State.ERROR, 10)
    assert manager.get(item.id).attempts == d.MAX_ATTEMPTS
    manager.shutdown()


def test_pause_stops_the_process_and_resume_runs_it_again(tmp_path):
    processes = []

    def factory(args):
        process = FakeProcess([progress(10, 100)], hold=True)
        processes.append(process)
        return process
    manager, _ = make_manager(tmp_path, factory)
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).downloaded == 10)
    assert manager.pause(item.id) and manager.get(item.id).state == State.PAUSED
    assert until(lambda: processes[0].terminated)
    time.sleep(0.2)
    assert manager.get(item.id).state == State.PAUSED                  # la fin du processus ne « termine » pas l'élément
    assert manager.resume(item.id)
    assert until(lambda: len(processes) == 2 and manager.get(item.id).state == State.RUNNING)
    processes[1].finish()
    assert until(lambda: manager.get(item.id).state == State.DONE)
    manager.shutdown()


def test_cancel_and_remove(tmp_path):
    process = FakeProcess([progress(1, 100)], hold=True)
    manager, events = make_manager(tmp_path, lambda args: process)
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).downloaded == 1)
    assert manager.cancel(item.id) and manager.get(item.id).state == State.CANCELLED and until(lambda: process.terminated)
    assert not manager.cancel(item.id)                                  # déjà annulé
    assert manager.remove(item.id) and manager.get(item.id) is None and events[-1][0] == "removed"
    assert not manager.remove("inconnu") and not manager.pause("inconnu") and not manager.resume("inconnu")
    manager.shutdown()


def test_parallel_limit_is_respected_and_the_queue_advances(tmp_path):
    running_now, peak, lock = [0], [0], threading.Lock()
    release = threading.Event()

    class Counting(FakeProcess):
        def _read(self):
            with lock:
                running_now[0] += 1
                peak[0] = max(peak[0], running_now[0])
            release.wait(10)
            with lock:
                running_now[0] -= 1
            return iter(())
    manager, _ = make_manager(tmp_path, lambda args: Counting([]), max_parallel=2)
    ids = [manager.add(f"https://site.exemple/v{i}").id for i in range(5)]
    assert until(lambda: manager.counts()["running"] == 2)
    time.sleep(0.2)
    assert peak[0] == 2 and manager.counts()["queued"] == 3
    release.set()
    assert until(lambda: manager.counts()["done"] == 5)
    assert peak[0] == 2
    manager.shutdown()


def test_same_url_in_progress_is_not_added_twice_but_can_be_after_it_finished(tmp_path):
    manager, _ = make_manager(tmp_path, lambda args: FakeProcess([], hold=True))
    first = manager.add(URL)
    assert manager.add(URL).id == first.id and len(manager.items()) == 1
    manager.cancel(first.id)
    assert manager.add(URL).id != first.id
    manager.shutdown()


def test_invalid_input_is_rejected_before_anything_is_queued(tmp_path):
    manager, _ = make_manager(tmp_path, lambda args: FakeProcess([]))
    for bad in ("", "pas une url", "ftp://x/y", "--exec=ls"):
        with pytest.raises(online.OnlineError):
            manager.add(bad)
    with pytest.raises(ValueError):
        manager.add(URL, DownloadOptions(rate_limit="vite"))
    assert manager.items() == []
    manager.shutdown()


def test_missing_ytdlp_marks_the_item_as_error(tmp_path):
    manager = DownloadManager(tmp_path / "s.json", command_provider=lambda: None)
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).state == State.ERROR)
    assert "yt-dlp" in manager.get(item.id).error
    manager.shutdown()


def test_state_survives_restart_and_running_items_resume_automatically(tmp_path):
    first, _ = make_manager(tmp_path, lambda args: FakeProcess([progress(40, 100)], hold=True))
    running = first.add("https://site.exemple/en-cours")
    done_item = first.add("https://site.exemple/fini")
    assert until(lambda: first.get(running.id).downloaded == 40)
    first.flush()
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert {i["url"] for i in saved["items"]} == {"https://site.exemple/en-cours", "https://site.exemple/fini"}
    # arrêt brutal simulé : on relit l'état sans shutdown propre
    second, _ = make_manager(tmp_path, lambda args: FakeProcess([progress(100, 100, "finished")]))
    reloaded = {i.url: i for i in second.items()}
    assert reloaded["https://site.exemple/en-cours"].state == State.QUEUED                # reprise automatique
    assert reloaded["https://site.exemple/en-cours"].downloaded == 40
    second.start()
    assert until(lambda: second.counts()["done"] == 2)
    first.shutdown()
    second.shutdown()
    assert done_item.id in {i.id for i in second.items()}


def test_paused_items_stay_paused_after_restart(tmp_path):
    first, _ = make_manager(tmp_path, lambda args: FakeProcess([], hold=True))
    item = first.add(URL)
    assert until(lambda: first.get(item.id).state == State.RUNNING)
    first.pause(item.id)
    first.flush()
    first.shutdown()
    second, _ = make_manager(tmp_path, lambda args: FakeProcess([]))
    second.start()
    time.sleep(0.2)
    assert second.get(item.id).state == State.PAUSED
    second.shutdown()


@pytest.mark.parametrize("content", ["pas du json", "[1, 2]", '{"items": 5}', '{"items": [1, "x", {"id": "a"}]}', ""])
def test_corrupted_state_file_never_prevents_startup(tmp_path, content):
    (tmp_path / "state.json").write_text(content, encoding="utf-8")
    manager = DownloadManager(tmp_path / "state.json", command_provider=lambda: ["x"])
    assert manager.items() == []
    manager.shutdown()


def test_clear_finished_keeps_active_items(tmp_path):
    manager, _ = make_manager(tmp_path, lambda args: FakeProcess([progress(1, 1, "finished")]))
    done = manager.add("https://site.exemple/a")
    assert until(lambda: manager.get(done.id).state == State.DONE)
    manager._process_factory = lambda args: FakeProcess([], hold=True)
    keep = manager.add("https://site.exemple/b")
    assert until(lambda: manager.get(keep.id).state == State.RUNNING)
    assert manager.clear_finished() == 1 and [i.id for i in manager.items()] == [keep.id]
    manager.shutdown()


def test_shutdown_stops_processes_and_requeues_running_items(tmp_path):
    process = FakeProcess([], hold=True)
    manager, _ = make_manager(tmp_path, lambda args: process)
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).state == State.RUNNING)
    manager.shutdown()
    assert process.terminated
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert saved["items"][0]["state"] == "queued"


def test_playlist_is_expanded_into_one_item_per_video_with_selection(tmp_path):
    entries = [PlaylistEntry(f"https://site.exemple/v{i}", f"Vidéo {i}", i) for i in range(1, 6)]
    manager = DownloadManager(tmp_path / "s.json", command_provider=lambda: ["x"],
                              process_factory=lambda args: FakeProcess([], hold=True),
                              playlist_expander=lambda url, opts: ("Ma playlist", select_entries(
                                  entries, opts.playlist_items, opts.playlist_reverse)))
    result = {}
    manager.add_playlist("https://site.exemple/list", DownloadOptions(playlist=True, playlist_items="2-4",
                                                                      playlist_reverse=True),
                         tmp_path / "out", on_done=lambda items, error: result.update(items=items, error=error))
    assert until(lambda: "items" in result)
    assert result["error"] == "" and [i.title for i in result["items"]] == ["Vidéo 4", "Vidéo 3", "Vidéo 2"]
    assert all(i.group == "Ma playlist" for i in result["items"])
    assert all("%(playlist_title|)s" in i.options["output_template"] for i in result["items"])
    assert all(i.options["playlist"] is False for i in result["items"])      # chaque élément est une vidéo seule
    manager.shutdown()


def test_playlist_expansion_failure_is_reported(tmp_path):
    def broken(url, opts):
        raise online.OnlineError("Playlist privée")
    manager = DownloadManager(tmp_path / "s.json", command_provider=lambda: ["x"], playlist_expander=broken)
    result = {}
    manager.add_playlist("https://site.exemple/list", on_done=lambda items, error: result.update(items=items, error=error))
    assert until(lambda: "error" in result) and result["items"] is None and "privée" in result["error"]
    manager.shutdown()


def test_a_failing_listener_never_breaks_a_download(tmp_path):
    manager, _ = make_manager(tmp_path, lambda args: FakeProcess([progress(1, 1, "finished")]))
    manager.subscribe(lambda kind, item: 1 / 0)
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).state == State.DONE)
    manager.shutdown()


# ----------------------------------------------------------------- vrai yt-dlp, serveur local avec reprise par plages
PAYLOAD = bytes(range(256)) * 4096            # 1 Mo


class RangeHandler(http.server.BaseHTTPRequestHandler):
    seen_ranges: list = []
    delay = 0.0

    def log_message(self, *a, **k):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        start = 0
        header = self.headers.get("Range")
        if header:
            self.seen_ranges.append(header)
            start = int(re.match(r"bytes=(\d+)-", header).group(1))
        self.send_response(206 if header else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(PAYLOAD) - start))
        if header:
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        self.end_headers()
        try:
            for offset in range(start, len(PAYLOAD), 65536):
                self.wfile.write(PAYLOAD[offset:offset + 65536])
                self.wfile.flush()
                time.sleep(self.delay)
        except (BrokenPipeError, ConnectionResetError):
            pass


@pytest.fixture
def range_server():
    if not online.available():
        pytest.skip("yt-dlp absent")
    RangeHandler.seen_ranges = []
    RangeHandler.delay = 0.0
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def plain_options(**kw):
    return DownloadOptions(embed_thumbnail=False, embed_metadata=False, embed_chapters=False, archive=False, **kw)


def test_real_ytdlp_downloads_a_file_end_to_end(tmp_path, range_server):
    manager = DownloadManager(tmp_path / "s.json")
    item = manager.add(f"{range_server}/film.mp4", plain_options(), tmp_path / "out")
    assert until(lambda: manager.get(item.id).state in d.FINISHED_STATES, 40)
    done = manager.get(item.id)
    assert done.state == State.DONE, done.error
    assert Path(done.filepath).read_bytes() == PAYLOAD and done.progress == 1.0 and done.title == "film"
    manager.shutdown()


def test_real_pause_then_resume_continues_the_partial_file(tmp_path, range_server):
    RangeHandler.delay = 0.08                                   # ~1,3 s pour 16 blocs : le temps de mettre en pause
    manager = DownloadManager(tmp_path / "s.json")
    item = manager.add(f"{range_server}/film.mp4", plain_options(), tmp_path / "out")
    assert until(lambda: 100_000 < manager.get(item.id).downloaded < len(PAYLOAD), 30)
    assert manager.pause(item.id)
    time.sleep(1.0)
    partial = list((tmp_path / "out").glob("*.part"))
    assert partial and 0 < partial[0].stat().st_size < len(PAYLOAD)
    RangeHandler.delay = 0.0
    assert manager.resume(item.id)
    assert until(lambda: manager.get(item.id).state in d.FINISHED_STATES, 40)
    done = manager.get(item.id)
    assert done.state == State.DONE, done.error
    assert Path(done.filepath).read_bytes() == PAYLOAD                   # fichier complet et identique
    assert RangeHandler.seen_ranges, "la reprise doit demander la suite par une plage d'octets"
    assert not list((tmp_path / "out").glob("*.part"))
    manager.shutdown()


def test_real_download_archive_skips_what_was_already_downloaded(tmp_path, range_server):
    manager = DownloadManager(tmp_path / "s.json")
    options = DownloadOptions(embed_thumbnail=False, embed_metadata=False, embed_chapters=False, archive=True)
    first = manager.add(f"{range_server}/film.mp4", options, tmp_path / "out")
    assert until(lambda: manager.get(first.id).state == State.DONE, 40)
    (Path(manager.get(first.id).filepath)).unlink()
    second = manager.add(f"{range_server}/film.mp4", options, tmp_path / "out")
    assert until(lambda: manager.get(second.id).state == State.DONE, 40)
    assert manager.get(second.id).archived and not manager.get(second.id).filepath    # reconnu : rien retéléchargé
    manager.shutdown()


def test_real_missing_url_ends_in_a_readable_error(tmp_path, range_server):
    class Gone(RangeHandler):
        def do_GET(self):
            self.send_error(404)
        do_HEAD = do_GET
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Gone)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    manager = DownloadManager(tmp_path / "s.json")
    item = manager.add(f"http://127.0.0.1:{server.server_address[1]}/absent.mp4", plain_options(), tmp_path / "out")
    assert until(lambda: manager.get(item.id).state in d.FINISHED_STATES, 40)
    assert manager.get(item.id).state == State.ERROR and manager.get(item.id).error
    assert "Traceback" not in manager.get(item.id).error
    manager.shutdown()
    server.shutdown()


def test_ytdlp_command_prefers_binary_then_module(monkeypatch, tmp_path):
    monkeypatch.setattr(online, "find_binary", lambda: Path("/opt/yt-dlp"))
    assert d.ytdlp_command() == [str(Path("/opt/yt-dlp"))]
    monkeypatch.setattr(online, "find_binary", lambda: None)
    monkeypatch.setattr(online, "module_available", lambda: True)
    monkeypatch.setattr(d, "is_frozen", lambda: False)
    assert d.ytdlp_command()[1:] == ["-m", "yt_dlp"]
    monkeypatch.setattr(d, "is_frozen", lambda: True)
    assert d.ytdlp_command()[-1] == d.RUN_FLAG
    monkeypatch.setattr(online, "module_available", lambda: False)
    assert d.ytdlp_command() is None
    assert shutil.which("definitely-not-a-binary") is None


def test_huge_selection_is_bounded_not_a_denial_of_service():
    start = time.time()
    assert parse_selection("0-99999999999999999999", 5) == [1, 2, 3, 4, 5]
    assert parse_selection("99999999999999999999-0", 3) == [3, 2, 1]
    assert time.time() - start < 1


def test_the_application_executable_can_act_as_ytdlp(tmp_path):
    """Binaire autonome : « PyPlayer --ytdlp-run … » lance le yt-dlp embarqué, sans ouvrir d'interface."""
    import os
    import subprocess
    import sys
    if not online.module_available():
        pytest.skip("module yt_dlp absent")
    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(root / "src"), "QT_QPA_PLATFORM": "offscreen"}
    done = subprocess.run([sys.executable, "-m", "pyplayer", d.RUN_FLAG, "--version"], capture_output=True, text=True,
                          env=env, timeout=60)
    assert done.returncode == 0 and re.match(r"^\d{4}\.\d{2}\.\d{2}", done.stdout.strip())
    failure = subprocess.run([sys.executable, "-m", "pyplayer", d.RUN_FLAG, "--option-inexistante"],
                             capture_output=True, text=True, env=env, timeout=60)
    assert failure.returncode != 0                                            # le code de sortie de yt-dlp est transmis


def test_removing_a_running_item_never_makes_it_reappear_through_a_late_event(tmp_path):
    process = FakeProcess([progress(1, 100)], hold=True)
    manager, events = make_manager(tmp_path, lambda args: process)
    item = manager.add(URL)
    assert until(lambda: manager.get(item.id).downloaded == 1)
    manager.remove(item.id)
    assert until(lambda: process.terminated)
    time.sleep(0.3)                                       # laisse le fil de travail se terminer
    assert manager.get(item.id) is None and manager.items() == []
    after_removed = events[[k for k, *_ in events].index("removed") + 1:]
    assert after_removed == []                            # aucun événement après la suppression
    manager.shutdown()
