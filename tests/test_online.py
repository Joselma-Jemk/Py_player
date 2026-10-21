"""Lecture en ligne : validation des adresses, lecture du résultat de yt-dlp, résolution réelle sur un serveur local."""

import functools
import http.server
import shutil
import subprocess
import threading

import pytest
from hypothesis import given, strategies as st

from pyplayer.api import online
from pyplayer.api.online import OnlineError, clean_url, is_direct_stream, is_web_url, parse_info

FFMPEG = shutil.which("ffmpeg")


# ----------------------------------------------------------------- adresses
@pytest.mark.parametrize("url", ["https://www.youtube.com/watch?v=abc", "http://exemple.fr/p?x=1&y=2", "  https://a.b/c  "])
def test_clean_url_accepts_web_addresses(url):
    assert clean_url(url) == url.strip()


@pytest.mark.parametrize("url", ["", "   ", "ftp://x/y", "file:///etc/passwd", "javascript:alert(1)", "--exec=rm",
                                 "-o /tmp/x", "https://", "https://a.b/c\nhttps://d.e", "https://a.b/\x00", "x" * 3000,
                                 "https://a.b/" + "y" * 3000])
def test_clean_url_rejects_dangerous_or_invalid_input(url):
    with pytest.raises(OnlineError):
        clean_url(url)


@given(st.text(max_size=60))
def test_clean_url_never_returns_something_that_could_be_an_option(text):
    try:
        result = clean_url(text)
    except OnlineError:
        return
    assert not result.startswith("-") and result.split(":", 1)[0].lower() in {"http", "https"}
    assert all(32 <= ord(c) != 127 for c in result)


def test_direct_streams_are_recognised_and_pages_are_not():
    for direct in ("https://x.org/film.mp4", "http://x.org/a/b.MKV?token=1", "https://x.org/live/index.m3u8",
                   "https://x.org/manifest.mpd", "rtsp://cam/1", "rtmp://x/y", "https://x.org/song.mp3"):
        assert is_direct_stream(direct), direct
    for page in ("https://www.youtube.com/watch?v=abc", "https://vimeo.com/123", "https://x.org/video/42", ""):
        assert not is_direct_stream(page), page
    assert is_web_url("https://vimeo.com/1") and not is_web_url("rtsp://cam/1") and not is_web_url("pas une url")


# ----------------------------------------------------------------- lecture du JSON de yt-dlp
COMBINED = {"title": "Mon film", "duration": 125.4, "uploader": "Moi", "extractor_key": "Youtube",
            "url": "https://cdn.example/v.mp4", "vcodec": "avc1", "acodec": "mp4a", "webpage_url": "https://y/watch",
            "http_headers": {"User-Agent": "UA"}}


def test_parse_info_reads_a_combined_format():
    media = parse_info(COMBINED, "https://y/watch?v=1")
    assert media.stream_url == "https://cdn.example/v.mp4" and media.title == "Mon film"
    assert media.duration_ms == 125_400 and media.uploader == "Moi" and media.has_video and not media.is_live
    assert media.extractor == "Youtube" and media.headers == {"User-Agent": "UA"} and media.page_url.endswith("v=1")


def test_parse_info_rejects_separate_streams_and_picks_a_combined_one_instead():
    info = {"title": "T", "requested_formats": [{"url": "https://v", "vcodec": "vp9", "acodec": "none"},
                                                {"url": "https://a", "vcodec": "none", "acodec": "opus"}],
            "formats": [{"url": "https://c360", "vcodec": "avc1", "acodec": "mp4a", "height": 360, "tbr": 500},
                        {"url": "https://c720", "vcodec": "avc1", "acodec": "mp4a", "height": 720, "tbr": 1500},
                        {"url": "https://v1080", "vcodec": "vp9", "acodec": "none", "height": 1080}]}
    assert parse_info(info).stream_url == "https://c720"


def test_parse_info_audio_only_and_nothing_playable():
    audio = parse_info({"title": "Podcast", "formats": [{"url": "https://a64", "vcodec": "none", "acodec": "mp3", "abr": 64},
                                                        {"url": "https://a128", "vcodec": "none", "acodec": "mp3", "abr": 128}]})
    assert audio.stream_url == "https://a128" and not audio.has_video
    with pytest.raises(OnlineError):
        parse_info({"title": "X", "formats": [{"url": "https://v", "vcodec": "vp9", "acodec": "none"}]})
    with pytest.raises(OnlineError):
        parse_info({"title": "X"})


def test_parse_info_takes_the_first_entry_of_a_playlist_and_rejects_empty_or_unsafe():
    playlist = {"_type": "playlist", "entries": [dict(COMBINED, title="Premier"), dict(COMBINED, title="Second")]}
    assert parse_info(playlist).title == "Premier"
    with pytest.raises(OnlineError):
        parse_info({"_type": "playlist", "entries": []})
    with pytest.raises(OnlineError):
        parse_info(dict(COMBINED, url="file:///etc/passwd"))              # jamais un flux non http(s)
    with pytest.raises(OnlineError):
        parse_info("pas un dict")                                           # type: ignore[arg-type]


@given(st.dictionaries(st.text(max_size=8), st.one_of(st.none(), st.integers(), st.text(max_size=10), st.floats(),
                                                      st.lists(st.integers(), max_size=2)), max_size=6))
def test_parse_info_never_crashes_with_anything_but_online_error(info):
    try:
        parse_info(info)
    except OnlineError:
        pass


def test_friendly_error_keeps_the_useful_line():
    text = "[youtube] abc: Downloading\nWARNING: x\nERROR: [youtube] abc: Video unavailable\n"
    assert online._friendly_error(text) == "[youtube] abc: Video unavailable"
    assert online._friendly_error("") == "yt-dlp n'a pas pu lire cette adresse."


def test_resolve_with_injected_extractor_and_without_any_backend(monkeypatch):
    assert online.resolve("https://x.org/p", extractor=lambda url: COMBINED).title == "Mon film"
    monkeypatch.setattr(online, "find_binary", lambda: None)
    monkeypatch.setattr(online, "module_available", lambda: False)
    with pytest.raises(OnlineError, match="yt-dlp n'est pas installé"):
        online.resolve("https://x.org/p")
    with pytest.raises(OnlineError):
        online.resolve("rtsp://x/y")


def test_binary_path_preference_user_binary_then_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(online.shutil, "which", lambda name: "/usr/bin/yt-dlp")
    assert str(online.find_binary()) == "/usr/bin/yt-dlp"
    own = online.user_binary_path()
    own.parent.mkdir(parents=True)
    own.write_bytes(b"#!/bin/sh\n")
    assert online.find_binary() == own                                       # l'exécutable mis à jour par PyPlayer prime


# ----------------------------------------------------------------- vrai yt-dlp sur un serveur local
@pytest.fixture
def local_server(tmp_path):
    if FFMPEG is None or not online.available():
        pytest.skip("ffmpeg ou yt-dlp absent")
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x90:rate=10",
                    "-f", "lavfi", "-i", "sine=duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", str(tmp_path / "clip.mp4")], check=True, timeout=60)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_real_ytdlp_resolves_a_direct_file_served_locally(local_server):
    media = online.resolve(f"{local_server}/clip.mp4")
    assert media.stream_url == f"{local_server}/clip.mp4" and media.title == "clip" and media.has_video


def test_real_ytdlp_reports_a_readable_error_for_a_missing_page(local_server):
    with pytest.raises(OnlineError) as error:
        online.resolve(f"{local_server}/n-existe-pas")
    assert str(error.value) and "Traceback" not in str(error.value)
