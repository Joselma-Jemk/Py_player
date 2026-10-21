"""Chasse aux liens : extraction, classement, prudence."""

import time

from hypothesis import given, strategies as st

from pyplayer.api.links import KNOWN_HOSTS, classify, extract_urls, hunt


def test_extract_urls_cleans_punctuation_dedupes_and_keeps_order():
    text = ("Regarde https://youtu.be/abc, puis (https://vimeo.com/123) et https://youtu.be/abc. "
            "Aussi <https://x.org/a.mp4> « https://x.org/b » ?")
    assert extract_urls(text) == ["https://youtu.be/abc", "https://vimeo.com/123", "https://x.org/a.mp4", "https://x.org/b"]


def test_balanced_closing_parenthesis_is_kept():
    assert extract_urls("voir https://fr.wikipedia.org/wiki/Fonction_(mathématiques)") == \
        ["https://fr.wikipedia.org/wiki/Fonction_(mathématiques)"]


def test_extract_urls_ignores_other_schemes_and_garbage():
    assert extract_urls("ftp://x/y file:///etc/passwd javascript:alert(1) mailto:a@b.c rien du tout") == []
    assert extract_urls("") == [] and extract_urls(None) == []                         # type: ignore[arg-type]
    assert extract_urls("https://" + "a" * 5000) == []                                 # trop long


def test_extract_urls_is_bounded():
    many = " ".join(f"https://site.exemple/v{i}" for i in range(500))
    assert len(extract_urls(many)) == 50
    started = time.time()
    extract_urls("http://" * 5000)
    extract_urls("a" * 1_000_000)
    assert time.time() - started < 2


def test_classify_video_pages_playlists_and_files():
    assert classify("https://www.youtube.com/watch?v=abc").kind == "page"
    assert classify("https://youtu.be/abc").kind == "page"
    assert classify("https://www.youtube.com/playlist?list=PL123").kind == "playlist"
    assert classify("https://www.youtube.com/watch?v=abc&list=PL123").kind == "page"        # une vidéo dans une liste
    assert classify("https://soundcloud.com/artiste/titre").kind == "page"
    assert classify("https://exemple.org/dossier/film.mkv?token=1").kind == "file"
    assert classify("https://exemple.org/dossier/film.mkv").label == "film.mkv"
    assert classify("https://m.youtube.com/watch?v=x").host == "m.youtube.com"


def test_classify_is_cautious():
    for ignored in ("https://www.google.com/search?q=chat", "https://exemple.org/page.html", "https://youtube.com/",
                    "https://www.youtube.com/results?search_query=x", "https://youtube.com/feed/subscriptions",
                    "https://x.com/login", "https://evilyoutube.com/watch?v=1", "https://youtube.com.evil.io/watch?v=1",
                    "ftp://x/y.mp4", "pas une url", ""):
        assert classify(ignored) is None, ignored


def test_hunt_skips_already_seen_links():
    text = "https://youtu.be/a https://vimeo.com/2 https://news.site/article"
    assert [link.url for link in hunt(text)] == ["https://youtu.be/a", "https://vimeo.com/2"]
    assert [link.url for link in hunt(text, ignore={"https://youtu.be/a"})] == ["https://vimeo.com/2"]


@given(st.text(max_size=300))
def test_hunt_never_raises_and_only_returns_web_links(text):
    for link in hunt(text):
        assert link.url.startswith(("http://", "https://")) and link.kind in ("page", "file", "playlist")


def test_known_hosts_are_lowercase_and_unique():
    assert all(h == h.lower() and "/" not in h for h in KNOWN_HOSTS) and len(set(KNOWN_HOSTS)) == len(KNOWN_HOSTS)
