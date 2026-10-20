"""Tests ajoutés pour fermer les trous révélés par le test de mutation (chaque test vise des cas limites précis)."""

import json
import logging
import os
import time
from pathlib import Path

import pytest

from pyplayer.api import m3u, manager as manager_module, media
from pyplayer.api.manager import BACKUPS_PER_PLAYLIST, PlaylistManager
from pyplayer.api.playlist import PlayMode, Playlist
from pyplayer.api.resume import MIN_RESUME_MS, ResumeStore
from pyplayer.api.settings import Settings
from pyplayer.api.subtitles import load_subtitle_file
from pyplayer.api.video import Video, as_timestamp


class LogCapture(logging.Handler):
    """Capture les journaux sans dépendre du plugin de logging de pytest."""
    def __init__(self, name):
        super().__init__(logging.DEBUG)
        self.records = []
        self._logger = logging.getLogger(name)
        self._old_level = self._logger.level

    def emit(self, record):
        self.records.append(record)

    def __enter__(self):
        self._logger.addHandler(self)
        self._logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc):
        self._logger.removeHandler(self)
        self._logger.setLevel(self._old_level)


# ----------------------------------------------------------------- m3u
def test_m3u_windows_file_url_and_short_entries(tmp_path):
    drive = m3u._resolve("file:///C:/Music/a.mp3", tmp_path)                               # « /C:/ » → « C:/ »
    assert drive.as_posix().endswith("C:/Music/a.mp3") and not drive.as_posix().startswith("/C:")
    if os.name != "nt":                                                                   # « /a » est absolu seulement sous POSIX
        assert m3u._resolve("file:///a", tmp_path) == Path("/a")                          # 2 caractères : intact
        assert m3u._resolve("file:///ab", tmp_path) == Path("/ab")                        # pas de « : » en 3e position
        assert m3u._resolve("file:///:", tmp_path) == Path("/:")                          # len == 2 : jamais d'IndexError
    else:
        assert m3u._resolve("file:///:", tmp_path) is not None                            # jamais d'IndexError
    assert m3u._resolve("#EXTINF:1,x", tmp_path) is None and m3u._resolve("  ", tmp_path) is None
    assert m3u._resolve("http://x/y.mp4", tmp_path) is None


# ----------------------------------------------------------------- manager
def test_exactly_five_snapshots_are_kept_per_playlist(isolated_home):
    assert BACKUPS_PER_PLAYLIST == 5
    manager = PlaylistManager(isolated_home)
    playlist = manager.create_playlist("Rot")
    backups = isolated_home / "playlists" / "backups"
    for i in range(9):
        playlist.description = f"version {i}"
        playlist.mark_dirty()
        manager.flush()
        time.sleep(0.02)
        PlaylistManager(isolated_home)                           # un instantané par démarrage, contenu différent
    assert len(list(backups.glob("Rot-*.json"))) == 5


def test_active_playlist_defaults_to_a_user_playlist_not_the_quick_one(isolated_home):
    manager = PlaylistManager(isolated_home)
    manager.quick_playlist()
    user = manager.create_playlist("Zèbre")
    manager.settings.set("last_playlist_id", None)
    manager.flush()
    reloaded = PlaylistManager(isolated_home)
    assert reloaded.active.kind == "user"
    only_quick = PlaylistManager(isolated_home / "solo")
    for p in list(only_quick):
        only_quick.remove_playlist(p.id)
    only_quick.quick_playlist()
    only_quick._playlists = {p.id: p for p in only_quick if p.kind == "quick"}
    only_quick._restore_active()
    assert only_quick.active.kind == "quick"                      # à défaut de mieux, la rapide reste utilisable
    assert user.kind == "user"


def test_playlist_file_name_slug_is_truncated_and_safe(isolated_home):
    manager = PlaylistManager(isolated_home)
    long_name = "é" * 80
    playlist = manager.create_playlist(long_name)
    stem = playlist.file_path.stem
    slug, _, ident = stem.rpartition("-")
    assert len(slug) == 40 and ident == playlist.id[:8]
    weird = manager.create_playlist('///???***')
    assert weird.file_path.name.startswith("playlist-")           # nom vide après nettoyage → valeur par défaut


def test_manager_logs_startup_and_stray_backup_move_failures(isolated_home, monkeypatch):
    with LogCapture("pyplayer.api.manager") as capture:
        PlaylistManager(isolated_home)
    assert any("playlist(s) chargée(s)" in r.getMessage() and r.levelno == logging.INFO for r in capture.records)
    stray = isolated_home / "playlists" / "X.backup.20250101_000000.json"
    stray.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(manager_module.shutil, "move", lambda *a, **k: (_ for _ in ()).throw(OSError("verrouillé")))
    with LogCapture("pyplayer.api.manager") as capture:
        PlaylistManager(isolated_home)
    assert any(r.levelno == logging.WARNING and "non déplacé" in r.getMessage() for r in capture.records)


# ----------------------------------------------------------------- media
def test_format_size_boundaries_and_unit_cap():
    assert media.format_size(1023) == "1023 o" and media.format_size(1024) == "1.0 Ko"
    assert media.format_size(1024 ** 2 - 1).endswith("Ko") and media.format_size(1024 ** 2) == "1.0 Mo"
    assert media.format_size(1024 ** 4 * 2048) == "2048.0 To"     # au-delà du dernier suffixe, on reste en « To »
    assert media.format_size(0) == "0 o"


def test_unique_paths_deduplicates_by_identity_key(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    assert list(media.unique_paths([a, b, a, tmp_path / "." / "a.mp4", b])) == [a, b]


# ----------------------------------------------------------------- playlist
def test_playlist_basic_accessors_and_defaults(media_dir):
    playlist = Playlist("t")
    assert playlist.dirty is False and str(PlayMode.LOOP_ALL) == "loop_all" and PlayMode.NORMAL.to_dict() == "normal"
    playlist.add_folder(media_dir("lib", 3))
    assert playlist.total == 3 and len(playlist) == 3
    assert playlist.index_of(None) == -1 and playlist.index_of("absent.mp4") == -1 and playlist.index_of(object.__new__(Video)) == -1
    assert playlist.index_of(playlist[2]) == 2 and playlist.index_of(playlist[1].path) == 1 and playlist.index_of(playlist[0].uid) == 0
    assert playlist.find("/pas/la.mp4") is None and playlist.get("inconnu") is None


def test_swap_rejects_out_of_range_on_either_side(media_dir):
    playlist = Playlist("t")
    playlist.add_folder(media_dir("lib", 3))
    names = [v.name for v in playlist]
    assert playlist.swap(0, 99) is False and playlist.swap(99, 0) is False
    assert playlist.swap(-1, 0) is False and playlist.swap(0, -1) is False
    assert [v.name for v in playlist] == names
    assert playlist.swap(0, 2) is True and playlist[0].name == names[2] and playlist.swap(1, 1) is True


def test_set_current_to_the_same_video_does_not_grow_history(media_dir):
    playlist = Playlist("t")
    playlist.add_folder(media_dir("lib", 3))
    playlist.set_current(0)
    playlist.set_current(0)
    assert playlist._history == []
    first = playlist[0]
    playlist.set_current(1)
    assert playlist._history == [first]
    playlist.set_current(1)
    assert playlist._history == [first]
    playlist.set_current(2, remember=False)
    assert playlist._history == [first]


def test_shuffle_with_a_single_video_keeps_returning_it_without_history(media_dir):
    playlist = Playlist("t")
    playlist.add_folder(media_dir("lib", 1))
    playlist.set_mode(PlayMode.SHUFFLE)
    only = playlist.ensure_current()
    for _ in range(4):
        assert playlist.next() is only
    assert playlist._history == []


def test_kind_and_shuffle_state_roundtrip_details(media_dir):
    playlist = Playlist("q", kind="quick")
    assert Playlist.from_dict(playlist.to_dict()).kind == "quick"
    data = playlist.to_dict()
    del data["kind"]
    assert Playlist.from_dict(data).kind == "user"                 # absent → « user »
    assert Playlist.from_dict({"version": 2, "id": "x", "name": "n", "videos": []}).total == 0   # vide mais valide
    filled = Playlist("n")
    filled.add_folder(media_dir("lib", 2))
    filled.set_current(1)
    restored = Playlist.from_dict(filled.to_dict())
    assert restored._played == set()                               # hors aléatoire : aucun « déjà joué »
    filled.set_mode(PlayMode.SHUFFLE)
    shuffled = Playlist.from_dict(filled.to_dict())
    assert shuffled._played == {id(shuffled.current)}              # aléatoire avec courante : elle compte comme jouée
    filled.set_current(None)
    filled.set_mode(PlayMode.SHUFFLE)
    nocurrent = Playlist.from_dict(filled.to_dict())
    assert nocurrent.current is None and nocurrent._played == set()


# ----------------------------------------------------------------- resume
def test_resume_minimum_position_boundary(tmp_path):
    store = ResumeStore()
    f = tmp_path / "a.mp4"
    store.update(f, MIN_RESUME_MS - 1, 600_000)
    assert store.position(f) == 0
    store.update(f, MIN_RESUME_MS, 600_000)
    assert store.position(f) == MIN_RESUME_MS                      # exactement 5 s : on reprend
    key = media.path_key(tmp_path / "b.mp4")
    store.import_position(key, MIN_RESUME_MS - 1, 600_000)
    assert len(store) == 1
    store.import_position(key, MIN_RESUME_MS, 600_000)
    assert len(store) == 2


# ----------------------------------------------------------------- settings
def test_settings_defaults_validation_and_save_format(tmp_path):
    path = tmp_path / "s.json"
    s = Settings(path)
    assert s.get("open_siblings") is True and s.get("resume_playback") is True and s.get("muted") is False
    path.write_text(json.dumps({"volume": True, "recent_files": "pas une liste", "last_open_dir": 5,
                                "audio_device": "abc", "aspect_mode": "fill", "open_siblings": False}), encoding="utf-8")
    loaded = Settings(path)
    assert loaded.get("volume") == pytest.approx(0.45)             # un booléen n'est pas un nombre
    assert loaded.get("recent_files") == [] and loaded.get("last_open_dir") == ""
    assert loaded.get("audio_device") == "abc" and loaded.get("aspect_mode") == "fill" and loaded.get("open_siblings") is False
    loaded.set("muted", True)
    assert loaded.dirty and loaded.save() is True and loaded.dirty is False
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1
    assert Settings(path).get("muted") is True
    assert Settings().save() is True                               # sans fichier : rien à écrire, pas d'erreur


# ----------------------------------------------------------------- sous-titres
def test_load_subtitle_file_handles_bom_cp1252_and_undecodable_bytes(tmp_path):
    body = "1\n00:00:00,000 --> 00:00:02,000\nÉté\n"
    bom = tmp_path / "bom.srt"
    bom.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    cp = tmp_path / "cp.srt"
    cp.write_bytes(body.encode("cp1252"))
    weird = tmp_path / "weird.srt"
    weird.write_bytes(b"1\n00:00:00,000 --> 00:00:02,000\nA\x81\x8d\x8f\x90\x9d\n")    # octets non définis en cp1252
    assert load_subtitle_file(bom)[0].text == "Été" and load_subtitle_file(cp)[0].text == "Été"
    cues = load_subtitle_file(weird)
    assert len(cues) == 1 and cues[0].text.startswith("A")


# ----------------------------------------------------------------- video
def test_video_helpers_edge_cases(tmp_path, monkeypatch):
    f = tmp_path / "x.mp4"
    f.write_bytes(b"x")
    v = Video.from_path(f)
    assert v.exists() is True and "x.mp4" in repr(v) and "?" in repr(v)
    v.update_metadata(width=640, height=360, duration=1000)
    assert "640x360" in repr(v) and "1000ms" in repr(v)
    monkeypatch.setattr(Path, "is_file", lambda self: (_ for _ in ()).throw(OSError("réseau coupé")))
    assert v.exists() is False                                     # une erreur d'accès n'est pas une exception


def test_update_metadata_reports_changes_precisely():
    v = Video(Path("/x/a.mp4"))
    assert v.update_metadata(duration=0) is False and v.duration == 0          # 0 = « inconnu » : ignoré
    assert v.update_metadata(duration=5000) is True and v.duration == 5000
    assert v.update_metadata(duration=5000) is False                           # inchangé
    assert v.update_metadata(duration=-5) is False and v.duration == 5000
    assert v.update_metadata(width=10, height=20) is True and v.update_metadata(width=10, height=20) is False


def test_as_timestamp_never_raises_and_falls_back():
    assert as_timestamp(True, 5.0) == 5.0 and as_timestamp(None, 4.0) == 4.0 and as_timestamp([], 3.0) == 3.0
    assert as_timestamp("12.5", 1.0) == 12.5 and as_timestamp(7, 1.0) == 7.0
    assert as_timestamp("pas une date", 3.0) == 3.0 and as_timestamp(float("nan"), 7.0) == 7.0
    assert as_timestamp(1e15, 9.0) == 9.0 and as_timestamp("9999999999999999-99-99", 2.0) == 2.0
    iso = as_timestamp("2026-10-20T16:44:56.929345", 0.0)
    assert iso > 1.7e9                                                         # date ISO de l'ancienne version
    assert as_timestamp(None) > 1.7e9                                          # sans défaut : maintenant
