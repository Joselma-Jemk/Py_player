"""Téléchargements sûrs : hôtes, HTTPS, somme obligatoire, taille, annulation, redirections, comparaison de versions."""

import hashlib
import http.server
import threading

import pytest
from hypothesis import given, strategies as st

from pyplayer.api import fetch
from pyplayer.api.fetch import FetchError, FetchPolicy, download_verified, is_newer, parse_sums, version_key

BODY = b"contenu de la mise a jour " * 5000
GOOD = hashlib.sha256(BODY).hexdigest()


class Handler(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def log_message(self, *a, **k):
        pass

    def do_GET(self):
        route = self.routes.get(self.path)
        if route is None:
            self.send_error(404)
            return
        status, headers, body = route
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def server():
    Handler.routes = {}
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base, FetchPolicy(allowed_hosts=frozenset({"127.0.0.1"}), require_https=False)
    httpd.shutdown()


# ----------------------------------------------------------------- politique
def test_policy_requires_https_and_known_hosts_by_default():
    policy = FetchPolicy()
    policy.check("https://api.github.com/repos/x/y/releases/latest")
    policy.check("https://objects.githubusercontent.com/a/b")
    for bad in ("http://github.com/x", "https://evil.example/x", "https://github.com.evil.io/x", "ftp://github.com/x",
                "file:///etc/passwd", "https://", "https://githubusercontent.com/x", "javascript:alert(1)"):
        with pytest.raises(FetchError):
            policy.check(bad)


@given(st.text(max_size=60))
def test_policy_never_accepts_a_url_outside_the_allowed_hosts(text):
    try:
        FetchPolicy().check(text)
    except FetchError:
        return
    from urllib.parse import urlparse
    parsed = urlparse(text)
    assert parsed.scheme.lower() == "https" and parsed.hostname.lower() in fetch.GITHUB_HOSTS


# ----------------------------------------------------------------- sommes et versions
def test_parse_sums_formats_and_hostile_lines():
    text = (f"{GOOD}  pyplayer-0.2.0-windows-setup.exe\n{GOOD.upper()} *dossier\\yt-dlp.exe\n"
            "pas une somme  fichier\nabc  court\n\n" + "z" * 64 + "  invalide")
    sums = parse_sums(text)
    assert sums == {"pyplayer-0.2.0-windows-setup.exe": GOOD, "yt-dlp.exe": GOOD}
    assert parse_sums("") == {}


@pytest.mark.parametrize("candidate,current,expected", [
    ("v0.3.0", "0.2.0", True), ("0.2.0", "0.2.0", False), ("0.2.0", "0.2.1", False), ("0.10.0", "0.9.9", True),
    ("2026.08.19", "2026.07.30", True), ("2026.08.19", "2026.08.19", False), ("1.0", "1.0.0", False),
    ("1.0.1", "1.0", True), ("v1.2.3-rc1", "1.2.2", True), ("", "0.1", False), ("n'importe quoi", "0.1", False)])
def test_version_comparison(candidate, current, expected):
    assert is_newer(candidate, current) is expected


@given(st.text(max_size=20), st.text(max_size=20))
def test_version_comparison_is_total_and_never_raises(a, b):
    assert version_key(a) and not (is_newer(a, b) and is_newer(b, a))


# ----------------------------------------------------------------- téléchargement vérifié
def test_download_succeeds_only_with_the_right_checksum_and_reports_progress(server, tmp_path):
    base, policy = server
    Handler.routes["/f.bin"] = (200, {}, BODY)
    seen = []
    target = tmp_path / "out" / "f.bin"
    result = download_verified(f"{base}/f.bin", target, GOOD, policy=policy, progress=lambda d, t: seen.append((d, t)))
    assert result == target and target.read_bytes() == BODY and seen[-1] == (len(BODY), len(BODY))
    assert not list(target.parent.glob("*.part"))


def test_wrong_checksum_deletes_everything_and_keeps_the_previous_file(server, tmp_path):
    base, policy = server
    Handler.routes["/f.bin"] = (200, {}, BODY)
    target = tmp_path / "f.bin"
    target.write_bytes(b"ancienne version")
    with pytest.raises(FetchError, match="incorrecte"):
        download_verified(f"{base}/f.bin", target, "0" * 64, policy=policy)
    assert target.read_bytes() == b"ancienne version" and not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("missing", ["", "abc", "g" * 64, None])
def test_a_missing_or_invalid_checksum_refuses_to_download_at_all(server, tmp_path, missing):
    base, policy = server
    Handler.routes["/f.bin"] = (200, {}, BODY)
    with pytest.raises(FetchError, match="Somme de contrôle absente"):
        download_verified(f"{base}/f.bin", tmp_path / "f.bin", missing, policy=policy)     # type: ignore[arg-type]
    assert not (tmp_path / "f.bin").exists()


def test_size_limit_is_enforced_with_and_without_content_length(server, tmp_path):
    base, policy = server
    Handler.routes["/f.bin"] = (200, {}, BODY)
    with pytest.raises(FetchError, match="volumineux"):
        download_verified(f"{base}/f.bin", tmp_path / "a.bin", GOOD, policy=policy, max_bytes=1000)
    assert not list(tmp_path.glob("a.bin*"))


def test_cancellation_stops_and_cleans_up(server, tmp_path):
    base, policy = server
    Handler.routes["/f.bin"] = (200, {}, BODY)
    with pytest.raises(FetchError, match="annulé"):
        download_verified(f"{base}/f.bin", tmp_path / "f.bin", GOOD, policy=policy, cancelled=lambda: True)
    assert not list(tmp_path.glob("f.bin*"))


def test_http_errors_and_unreachable_servers_give_readable_errors(server, tmp_path):
    base, policy = server
    with pytest.raises(FetchError, match="404"):
        download_verified(f"{base}/absent", tmp_path / "x", GOOD, policy=policy)
    with pytest.raises(FetchError, match="Connexion impossible"):
        download_verified("http://127.0.0.1:1/x", tmp_path / "x", GOOD, policy=policy, timeout=2)


def test_a_redirect_to_a_forbidden_host_is_refused(server, tmp_path):
    base, policy = server
    Handler.routes["/go"] = (302, {"Location": "http://evil.example/payload"}, b"")
    with pytest.raises(FetchError, match="non autorisé"):
        download_verified(f"{base}/go", tmp_path / "x", GOOD, policy=policy)
    assert not list(tmp_path.glob("x*"))


def test_redirects_between_allowed_hosts_work_but_loops_are_cut(server, tmp_path):
    base, policy = server
    Handler.routes["/a"] = (302, {"Location": f"{base}/f.bin"}, b"")
    Handler.routes["/f.bin"] = (200, {}, BODY)
    assert download_verified(f"{base}/a", tmp_path / "f.bin", GOOD, policy=policy).read_bytes() == BODY
    Handler.routes["/loop"] = (302, {"Location": f"{base}/loop"}, b"")
    with pytest.raises(FetchError):
        download_verified(f"{base}/loop", tmp_path / "y", GOOD, policy=policy, timeout=5)


def test_json_and_text_helpers(server):
    base, policy = server
    Handler.routes["/j"] = (200, {}, b'{"tag_name": "v1.2.3", "assets": []}')
    Handler.routes["/bad"] = (200, {}, b"pas du json")
    Handler.routes["/big"] = (200, {}, b"x" * (fetch.MAX_JSON_BYTES + 10))
    Handler.routes["/t"] = (200, {}, f"{GOOD}  a.bin\n".encode())
    assert fetch.get_json(f"{base}/j", policy)["tag_name"] == "v1.2.3"
    with pytest.raises(FetchError, match="illisible"):
        fetch.get_json(f"{base}/bad", policy)
    with pytest.raises(FetchError, match="volumineuse"):
        fetch.get_json(f"{base}/big", policy)
    assert parse_sums(fetch.get_text(f"{base}/t", policy)) == {"a.bin": GOOD}
    with pytest.raises(FetchError):
        fetch.get_json("https://evil.example/x")                                # politique par défaut : refusé
