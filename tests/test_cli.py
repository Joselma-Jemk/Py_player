"""Ligne de commande « pyplayer download / tools / update / self-install » : options, sorties, codes, sans Qt."""

import argparse
import functools
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from pyplayer import cli
from pyplayer.api import downloads as dl
from pyplayer.api import fetch, online, tools, updater
from pyplayer.api.settings import Settings
from tests.test_downloads import FakeProcess, progress, until  # noqa: F401

URL = "https://www.youtube.com/watch?v=abc123"
ROOT = Path(__file__).resolve().parent.parent


def parse(*argv):
    return cli.parse_args(list(argv))


def fake_manager(lines=None, code=0, expander=None, available=True):
    """Fabrique de gestionnaire : faux yt-dlp, mêmes paramètres que ``DownloadManager``."""
    created = []
    seen = []

    def factory(state_file, **kwargs):
        def process(args):
            seen.append(args)
            folder = next(a for a in args if a.startswith("--paths=home:")).split("home:", 1)[1]
            title = "Titre " + args[-1][-6:]
            output = lines if lines is not None else [
                'PYPINFO:{"title": "%s"}' % title, progress(10, 100), progress(100, 100, "finished"),
                'PYPDONE:' + json.dumps(str(Path(folder) / (title + ".mp4")))]
            return FakeProcess(output, code)
        manager = dl.DownloadManager(state_file, command_provider=(lambda: ["fake"]) if available else (lambda: None),
                                     process_factory=process, retry_base_s=0.01, playlist_expander=expander, **kwargs)
        created.append(manager)
        return manager
    factory.created = created
    factory.seen = seen
    return factory


def run(*argv, stdin="", factory=None, settings=None, sleep=lambda s: __import__("time").sleep(0.01)):
    args = parse(*argv)
    out, err = io.StringIO(), io.StringIO()
    code = cli.cmd_download(args, out=out, err=err, stdin=io.StringIO(stdin), manager_factory=factory or fake_manager(),
                            sleep=sleep, settings=settings or Settings(None))
    return code, out.getvalue(), err.getvalue()


# ----------------------------------------------------------------- sous-commandes
def test_is_cli_recognises_exact_subcommands_only():
    for word in ("download", "dl", "tools", "update", "self-install"):
        assert cli.is_cli([word, "x"])
    for other in ([], ["film.mp4"], ["--version"], ["downloads"], ["Download"], ["https://youtu.be/x"], ["-a", "download"]):
        assert not cli.is_cli(other)


def test_a_folder_named_like_a_subcommand_does_not_hide_the_command(tmp_path, monkeypatch):
    (tmp_path / "tools").mkdir()
    monkeypatch.chdir(tmp_path)
    assert cli.is_cli(["tools", "status"])                                  # la commande l'emporte ; « ./tools » ouvre le dossier


# ----------------------------------------------------------------- options
def test_options_follow_the_application_settings_and_cli_flags_override_them(tmp_path):
    settings = Settings(tmp_path / "s.json")
    settings.set("download_preset", "720p")
    settings.set("download_options", {"rate_limit": "1M", "subtitles": True, "container": "mkv"})
    base = cli.options_from_args(parse("dl", URL), settings)
    assert base.preset == "720p" and base.rate_limit == "1M" and base.subtitles and base.container == "mkv"
    over = cli.options_from_args(parse("dl", URL, "-q", "audio-m4a", "--rate-limit", "3M", "--container", "mp4",
                                       "--proxy", "http://h:3128", "--no-archive", "--no-embed"), settings)
    assert over.preset == "audio_m4a" and over.rate_limit == "3M" and over.container == "mp4"
    assert over.proxy == "http://h:3128" and not over.archive
    assert not (over.embed_thumbnail or over.embed_metadata or over.embed_chapters)


def test_each_flag_maps_to_its_option():
    opts = cli.options_from_args(parse("dl", URL, "-a", "--format", "best[height<=480]", "-p", "--items", "2-4", "--reverse",
                                       "--subs", "fr", "--sponsorblock", "mark", "--sections", "*1:00-2:00",
                                       "--fragments", "16", "--cookies-from-browser", "firefox", "--template",
                                       "%(title)s.%(ext)s", "--restrict-filenames", "--info-json", "--aria2c"), Settings(None))
    assert opts.preset == "custom" and opts.custom_format == "best[height<=480]"          # --format l'emporte sur -a
    assert opts.playlist and opts.playlist_items == "2-4" and opts.playlist_reverse
    assert opts.subtitles and opts.sub_langs == "fr" and opts.sponsorblock == "mark" and opts.sections == "*1:00-2:00"
    assert opts.concurrent_fragments == 16 and opts.cookies_from_browser == "firefox"
    assert opts.output_template == "%(title)s.%(ext)s" and opts.restrict_filenames and opts.write_info_json and opts.use_aria2c
    assert cli.options_from_args(parse("dl", URL, "-a"), Settings(None)).preset == "audio_mp3"
    assert cli.options_from_args(parse("dl", URL, "-a", "opus"), Settings(None)).preset == "audio_opus"


# ----------------------------------------------------------------- collecte des liens
def test_links_come_from_arguments_files_and_stdin_with_hunting_and_dedup(tmp_path):
    note = tmp_path / "liens.txt"
    note.write_text("Voir https://vimeo.com/123 et (https://youtu.be/zzz).\npas un lien\nhttps://vimeo.com/123\n", encoding="utf-8")
    args = parse("dl", URL, "-", "-f", str(note), "-f", str(tmp_path / "absent.txt"), "pas-un-lien")
    urls, ignored = cli.collect_urls(args, io.StringIO("copié : https://soundcloud.com/a/b https://youtu.be/zzz"))
    assert urls == [URL, "https://soundcloud.com/a/b", "https://youtu.be/zzz", "https://vimeo.com/123"]
    assert any("pas-un-lien" in i for i in ignored) and any("absent.txt" in i for i in ignored)


# ----------------------------------------------------------------- téléchargement
def test_successful_download_prints_progress_summary_and_exits_zero(tmp_path):
    code, out, err = run("dl", URL, "-o", str(tmp_path / "out"), "--no-archive")
    assert code == cli.EXIT_OK and err == "" or "FFmpeg" in err
    assert "> Titre" in out and "[OK] Titre" in out and "1 terminé(s), 0 en erreur." in out
    assert str(tmp_path / "out") in out


def test_no_link_or_invalid_options_exit_with_usage_code(tmp_path):
    assert run("dl")[0] == cli.EXIT_USAGE and "Aucun lien" in run("dl")[2]
    code, _, err = run("dl", URL, "--rate-limit", "beaucoup")
    assert code == cli.EXIT_USAGE and "Limite de débit" in err
    code, _, err = run("dl", URL, "-j", "99")
    assert code == cli.EXIT_USAGE and "-j" in err
    code, _, err = run("dl", "pas-un-lien")
    assert code == cli.EXIT_USAGE and "pas un lien valide" in err


def test_failed_download_exits_one_with_a_readable_message():
    factory = fake_manager(lines=["ERROR: [youtube] abc: Video unavailable"], code=1)
    code, out, err = run("dl", URL, factory=factory)
    assert code == cli.EXIT_FAILED and "[ERREUR]" in err and "Video unavailable" in err and "1 en erreur" in out


def test_one_failure_among_several_still_downloads_the_rest():
    calls = []

    def factory(state_file, **kwargs):
        def process(args):
            calls.append(args[-1])
            if args[-1].endswith("bad"):
                return FakeProcess(["ERROR: Private video"], 1)
            return FakeProcess([progress(1, 1, "finished"), 'PYPDONE:"/tmp/ok.mp4"'], 0)
        return dl.DownloadManager(state_file, command_provider=lambda: ["fake"], process_factory=process, **kwargs)
    code, out, err = run("dl", "https://site.exemple/ok1", "https://site.exemple/bad", "https://site.exemple/ok2",
                         factory=factory)
    assert code == cli.EXIT_FAILED and "2 terminé(s), 1 en erreur." in out and len(calls) == 3


def test_json_mode_emits_one_json_object_per_line_and_nothing_else():
    code, out, err = run("dl", URL, "--json", "--no-archive")
    events = [json.loads(line) for line in out.splitlines()]
    kinds = [e["event"] for e in events]
    assert code == 0 and kinds[0] == "start" and "done" in kinds and kinds[-1] == "summary"
    assert events[-1] == {"event": "summary", "done": 1, "failed": 0}
    assert all(set(e) >= {"event"} for e in events) and "progress" in kinds


def test_json_mode_reports_errors_as_events():
    code, out, err = run("dl", URL, "--json", factory=fake_manager(lines=["ERROR: Sign in to confirm"], code=1))
    events = [json.loads(line) for line in out.splitlines()]
    assert code == 1 and any(e["event"] == "error" and "Sign in" in e["message"] for e in events)


def test_quiet_mode_prints_only_errors():
    code, out, err = run("dl", URL, "--quiet")
    assert code == 0 and out == ""
    code, out, err = run("dl", URL, "--quiet", factory=fake_manager(lines=["ERROR: boom"], code=1))
    assert code == 1 and out == "" and "boom" in err


def test_playlist_links_are_expanded_and_every_video_downloaded(tmp_path):
    entries = [dl.PlaylistEntry(f"https://www.youtube.com/watch?v=v{i}", f"Vidéo {i}", i) for i in range(1, 4)]
    factory = fake_manager(expander=lambda url, opts: ("Ma liste", dl.select_entries(entries, opts.playlist_items, opts.playlist_reverse)))
    code, out, err = run("dl", "https://www.youtube.com/playlist?list=PL1", "--items", "2-3", "-o", str(tmp_path), factory=factory)
    assert code == 0 and "2 terminé(s)" in out
    assert len(factory.seen) == 2                                                   # --items 2-3 : deux vidéos seulement
    assert all(any(a.startswith("--output=") and "%(playlist_title|)s" in a for a in args) for args in factory.seen)
    assert [args[-1] for args in factory.seen] == ["https://www.youtube.com/watch?v=v2",
                                                   "https://www.youtube.com/watch?v=v3"]


def test_playlist_expansion_failure_exits_one():
    def broken(url, opts):
        raise online.OnlineError("Playlist privée")
    code, out, err = run("dl", "https://www.youtube.com/playlist?list=PL1", factory=fake_manager(expander=broken))
    assert code == cli.EXIT_FAILED and "Playlist privée" in err


def test_ctrl_c_stops_cleanly_keeps_the_queue_and_resume_continues_it(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    hold = fake_manager(lines=[progress(10, 100)])

    def hanging(state_file, **kwargs):
        manager = dl.DownloadManager(state_file, command_provider=lambda: ["fake"],
                                     process_factory=lambda args: FakeProcess([progress(10, 100)], hold=True), **kwargs)
        return manager
    calls = {"n": 0}

    def interrupt(seconds):
        calls["n"] += 1
        if calls["n"] > 5:
            raise KeyboardInterrupt
    code, out, err = run("dl", URL, factory=hanging, sleep=interrupt)
    assert code == cli.EXIT_INTERRUPTED and "--resume" in err
    saved = json.loads((tmp_path / "home" / "downloads-cli.json").read_text(encoding="utf-8"))
    assert [i["state"] for i in saved["items"]] == ["queued"] and saved["items"][0]["url"] == URL
    code, out, err = run("dl", "--resume", factory=fake_manager())             # sans lien : reprend la file mémorisée
    assert code == cli.EXIT_OK and "1 terminé(s)" in out
    saved = json.loads((tmp_path / "home" / "downloads-cli.json").read_text(encoding="utf-8"))
    assert saved["items"] == []                                                # ce qui est fini ne reste pas en file
    assert hold is not None


def test_without_resume_the_previous_queue_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "downloads-cli.json").write_text(json.dumps({"version": 1, "items": [{
        "id": "old", "url": "https://site.exemple/ancien", "out_dir": str(tmp_path), "options": {}, "state": "queued"}]}),
        encoding="utf-8")
    factory = fake_manager()
    code, out, err = run("dl", URL, factory=factory)
    assert code == 0 and "ancien" not in out and len(factory.created[0].items()) <= 1


def test_play_flag_opens_the_downloaded_files(tmp_path, monkeypatch):
    opened = []
    media = tmp_path / "Titre ac123.mp4"
    media.write_bytes(b"x")
    monkeypatch.setattr(subprocess, "Popen", lambda command, **kw: opened.append(command))
    factory = fake_manager(lines=[progress(1, 1, "finished"), "PYPDONE:" + json.dumps(str(media))])
    code, out, err = run("dl", URL, "--play", factory=factory)
    assert code == 0 and opened and opened[0][-1] == str(media)
    opened.clear()
    cli._play(["/introuvable.mp4"])
    assert opened == []


# ----------------------------------------------------------------- yt-dlp absent
def test_missing_ytdlp_exits_three_with_the_install_hint():
    code, out, err = run("dl", URL, factory=fake_manager(available=False))
    assert code == cli.EXIT_NO_YTDLP and "yt-dlp n'est pas installé" in err and "pyplayer tools install ytdlp" in err


def test_missing_ytdlp_is_installed_with_yes_then_the_download_runs(monkeypatch):
    factory = fake_manager(available=False)
    installed = []

    def install(progress=None, **kw):
        installed.append(1)
        progress(100, 100)
        manager = factory.created[0]
        manager._command_provider = lambda: ["fake"]
        return Path("/tmp/yt-dlp")
    monkeypatch.setattr(tools, "install_ytdlp", install)
    code, out, err = run("dl", URL, "--yes", factory=factory)
    assert code == 0 and installed == [1] and "[OK]" in out


def test_interactive_install_prompt_accepts_and_refuses_and_reports_failures():
    class Tty(io.StringIO):
        def isatty(self):
            return True
    manager = fake_manager(available=False)("x.json")
    out, err = io.StringIO(), io.StringIO()
    assert not cli.ensure_ytdlp(manager, assume_yes=False, out=out, err=err, stdin=Tty("n\n"))
    assert "[O/n]" in err.getvalue() and "pyplayer tools install ytdlp" in err.getvalue()

    def failing(progress=None, **kw):
        raise fetch.FetchError("Somme de contrôle incorrecte")
    err2 = io.StringIO()
    assert not cli.ensure_ytdlp(manager, assume_yes=False, out=out, err=err2, stdin=Tty("\n"), install=failing)
    assert "Somme de contrôle incorrecte" in err2.getvalue()
    assert not cli.ensure_ytdlp(manager, assume_yes=False, out=out, err=io.StringIO(), stdin=io.StringIO(""))   # non interactif


# ----------------------------------------------------------------- affichage
def test_printer_uses_a_single_updating_line_in_a_terminal_and_regular_lines_otherwise():
    class Tty(io.StringIO):
        def isatty(self):
            return True
    now = [0.0]
    item = dl.DownloadItem(id="1", url=URL, out_dir="/", options={}, title="Un titre", state=dl.State.RUNNING,
                           progress=0.42, speed=2 * 1024 * 1024, eta=75)
    tty, plain = Tty(), io.StringIO()
    p1, p2 = cli.Printer(tty, io.StringIO(), clock=lambda: now[0]), cli.Printer(plain, io.StringIO(), clock=lambda: now[0])
    for printer in (p1, p2):
        now[0] = 10.0
        printer.status([item])
        now[0] = 10.3
        printer.status([item])                                    # trop tôt : rien
        now[0] = 20.0
        printer.status([item])
    assert tty.getvalue().count("\r") == 2 and "\n" not in tty.getvalue()
    assert plain.getvalue().count("\n") == 2 and "42%" in plain.getvalue() and "2.0 Mo/s" in plain.getvalue()
    assert "reste 1:15" in plain.getvalue() and "Un titre" in plain.getvalue()
    p1.line("terminé")
    assert tty.getvalue().endswith("terminé\n")


def test_printer_never_raises_on_broken_streams():
    class Broken:
        def write(self, text):
            raise OSError("tube fermé")

        def flush(self):
            raise OSError("tube fermé")
    printer = cli.Printer(Broken(), Broken())
    printer.line("x")
    printer.line("y", error=True)
    printer.status([dl.DownloadItem(id="1", url=URL, out_dir="/", options={}, state=dl.State.RUNNING)], force=True)


# ----------------------------------------------------------------- outils, mise à jour, auto-installation
def test_tools_status_and_install_paths():
    out, err = io.StringIO(), io.StringIO()
    assert cli.cmd_tools(parse("tools", "status"), out=out, err=err) == 0 and "yt-dlp" in out.getvalue() and "FFmpeg" in out.getvalue()
    out, err = io.StringIO(), io.StringIO()
    code = cli.cmd_tools(parse("tools", "install", "all"), out=out, err=err,
                         install_ytdlp=lambda progress=None: Path("/d/yt-dlp"), install_ffmpeg=lambda progress=None: Path("/d/ffmpeg"))
    assert code == 0 and "yt-dlp installé : /d/yt-dlp" in out.getvalue() and "FFmpeg installé" in out.getvalue()

    def failing(progress=None):
        raise fetch.FetchError("hors ligne")
    out, err = io.StringIO(), io.StringIO()
    code = cli.cmd_tools(parse("tools", "install", "ffmpeg"), out=out, err=err, install_ffmpeg=failing)
    assert code == 1 and "hors ligne" in err.getvalue()


def test_update_command_variants():
    info = updater.UpdateInfo("9.9.9", "v9.9.9", "", "https://github.com/x/y/releases/tag/v9.9.9", "linux-binary",
                              "pyplayer-9.9.9-linux-x86_64", "https://github.com/x/y/a", "a" * 64)
    out, err = io.StringIO(), io.StringIO()
    assert cli.cmd_update(parse("update"), out=out, err=err, check=lambda v: None) == 0 and "est à jour" in out.getvalue()
    out = io.StringIO()
    assert cli.cmd_update(parse("update"), out=out, err=err, check=lambda v: info) == 0 and "9.9.9 est disponible" in out.getvalue()
    assert "update --install" in out.getvalue()
    out = io.StringIO()
    result = updater.ApplyResult("restart", Path("/opt/pyplayer"))
    assert cli.cmd_update(parse("update", "--install"), out=out, err=err, check=lambda v: info, apply=lambda i, progress=None: result) == 0
    assert "relancez PyPlayer" in out.getvalue()
    manual = updater.UpdateInfo("9.9.9", "v9.9.9", "", "https://x", "manual")
    err = io.StringIO()
    assert cli.cmd_update(parse("update", "--install"), out=io.StringIO(), err=err, check=lambda v: manual) == 1
    assert "automatiquement" in err.getvalue()

    def offline(v):
        raise fetch.FetchError("Connexion impossible")
    err = io.StringIO()
    assert cli.cmd_update(parse("update"), out=io.StringIO(), err=err, check=offline) == 1 and "Connexion impossible" in err.getvalue()


@pytest.mark.skipif(os.name == "nt", reason="Linux/macOS")
def test_self_install_copies_the_binary_or_writes_a_launcher_and_hints_at_the_path(tmp_path):
    binary = tmp_path / "pyplayer-0.2.0-linux-x86_64"
    binary.write_bytes(b"#!/bin/sh\necho ok\n")
    out, err = io.StringIO(), io.StringIO()
    code = cli.cmd_self_install(out=out, err=err, home=tmp_path / "home", executable=str(binary), frozen=True, env_path="/usr/bin")
    target = tmp_path / "home" / ".local" / "bin" / "pyplayer"
    assert code == 0 and target.read_bytes() == binary.read_bytes() and os.access(target, os.X_OK)
    assert "export PATH" in out.getvalue()
    out = io.StringIO()
    cli.cmd_self_install(out=out, err=err, home=tmp_path / "home", executable=str(binary), frozen=True,
                         env_path=str(tmp_path / "home" / ".local" / "bin"))
    assert "export PATH" not in out.getvalue()                           # déjà dans le PATH : pas de conseil superflu
    cli.cmd_self_install(out=io.StringIO(), err=err, home=tmp_path / "home2", executable=str(binary), frozen=False)
    script = (tmp_path / "home2" / ".local" / "bin" / "pyplayer").read_text(encoding="utf-8")
    assert script.startswith("#!/bin/sh") and "-m pyplayer" in script


# ----------------------------------------------------------------- vrai programme
def run_program(*argv, env_extra=None):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "QT_QPA_PLATFORM": "offscreen", **(env_extra or {})}
    return subprocess.run([sys.executable, "-m", "pyplayer", *argv], capture_output=True, text=True, env=env, timeout=60)


def test_real_program_help_and_exit_codes():
    helped = run_program("download", "--help")
    assert helped.returncode == 0 and "--playlist" in helped.stdout and "LIEN" in helped.stdout
    assert run_program("dl").returncode == cli.EXIT_USAGE
    assert run_program("download", "-q", "invalide").returncode == cli.EXIT_USAGE
    assert run_program("tools", "status").returncode == 0
    top = run_program("--help")
    assert top.returncode == 0 and "pyplayer" in top.stdout


def test_cli_commands_never_import_qt_and_start_fast(tmp_path):
    code = ("import sys, time; t=time.perf_counter(); from pyplayer.__main__ import main; "
            "rc = main(['tools','status']); print('QT', any(m.startswith('PySide6') for m in sys.modules)); "
            "print('SECONDS', round(time.perf_counter()-t, 2)); sys.exit(rc)")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYPLAYER_HOME": str(tmp_path / "h")}
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60)
    assert done.returncode == 0 and "QT False" in done.stdout
    assert float(done.stdout.split("SECONDS")[1].split()[0]) < 2.0


@pytest.mark.skipif(not online.available(), reason="yt-dlp absent")
def test_real_end_to_end_download_through_the_real_program(tmp_path):
    import http.server
    payload = b"fichier de test " * 5000
    handler = type("H", (http.server.BaseHTTPRequestHandler,), {
        "log_message": lambda *a, **k: None,
        "do_HEAD": lambda self: (self.send_response(200), self.send_header("Content-Length", str(len(payload))),
                                 self.send_header("Content-Type", "video/mp4"), self.end_headers()),
        "do_GET": lambda self: (self.send_response(200), self.send_header("Content-Length", str(len(payload))),
                                self.send_header("Content-Type", "video/mp4"), self.end_headers(), self.wfile.write(payload))})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/film.mp4"
        done = run_program("download", url, "-o", str(tmp_path / "out"), "--no-embed", "--no-archive", "--json",
                           env_extra={"PYPLAYER_HOME": str(tmp_path / "home")})
        events = [json.loads(line) for line in done.stdout.splitlines()]
        assert done.returncode == 0 and events[-1] == {"event": "summary", "done": 1, "failed": 0}
        written = [e for e in events if e["event"] == "done"][0]["path"]
        assert Path(written).read_bytes() == payload
    finally:
        server.shutdown()
