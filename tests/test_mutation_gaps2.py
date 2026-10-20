"""Deuxième lot de cas limites, ajoutés après la campagne de mutation n°2 (chaque test vise un survivant précis)."""

import json
import logging
import os
from pathlib import Path

import pytest

from pyplayer.api import media
from pyplayer.api.manager import PlaylistManager
from pyplayer.api.playlist import HISTORY_LIMIT, Playlist
from pyplayer.api.resume import ResumeStore
from pyplayer.api.settings import Settings
from pyplayer.api.video import Video, _as_int
from tests.test_mutation_gaps import LogCapture


# ----------------------------------------------------------------- manager
def test_contains_and_active_recreate_a_playlist_when_none_exist(isolated_home):
    manager = PlaylistManager(isolated_home)
    existing = manager.playlists[0]
    assert existing.id in manager and "inconnu" not in manager and 5 not in manager
    manager._playlists.clear()
    manager._active_id = None
    recreated = manager.active                                   # jamais d'exception : une playlist vide est recréée
    assert len(manager) == 1 and recreated is manager.playlists[0]


def test_create_playlist_from_a_single_file_adds_it_without_a_source_folder(isolated_home, tmp_path):
    video = tmp_path / "solo.mp4"
    video.write_bytes(b"x")
    manager = PlaylistManager(isolated_home)
    playlist = manager.create_playlist("Solo", video)
    assert [v.name for v in playlist] == ["solo.mp4"] and playlist.source is None
    missing = manager.create_playlist("Rien", tmp_path / "absent")
    assert len(missing) == 0 and missing.source is None


def test_rename_marks_dirty_and_is_persisted_by_flush(isolated_home):
    manager = PlaylistManager(isolated_home)
    playlist = manager.create_playlist("Avant")
    manager.flush()
    assert playlist.dirty is False
    manager.rename(playlist.id, "Après")
    assert playlist.dirty is True
    manager.flush()
    assert any(p.name == "Après" for p in PlaylistManager(isolated_home))


def test_restore_uses_the_newest_valid_backup(isolated_home):
    manager = PlaylistManager(isolated_home)
    playlist = manager.create_playlist("Hist")
    manager.flush()
    backups = isolated_home / "playlists" / "backups"
    old_data, new_data = playlist.to_dict(), playlist.to_dict()
    old_data["description"], new_data["description"] = "ancienne", "récente"
    old, new = backups / f"{playlist.file_path.stem}.20200101.json", backups / f"{playlist.file_path.stem}.20300101.json"
    old.write_text(json.dumps(old_data), encoding="utf-8")
    new.write_text(json.dumps(new_data), encoding="utf-8")
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))                        # le plus récent d'après la date de modification
    playlist.file_path.write_text('{"cassé":', encoding="utf-8")
    restored = next(p for p in PlaylistManager(isolated_home) if p.name == "Hist")
    assert restored.description == "récente"


def test_snapshot_default_is_a_timestamped_backup_not_a_v1_label(isolated_home):
    manager = PlaylistManager(isolated_home)
    playlist = manager.create_playlist("Snap")
    manager.flush()
    backups = isolated_home / "playlists" / "backups"
    for old in backups.glob("Snap-*.json"):
        old.unlink()
    manager._snapshot(playlist.file_path)                        # legacy omis → instantané horodaté
    names = [p.name for p in backups.glob("Snap-*.json")]
    assert len(names) == 1 and not names[0].endswith(".v1.json")
    manager._snapshot(playlist.file_path, legacy=True)
    assert any(n.endswith(".v1.json") for n in (p.name for p in backups.glob("Snap-*.json")))


def test_unreadable_settings_file_is_logged_and_defaults_are_used(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{pas du json", encoding="utf-8")
    with LogCapture("pyplayer.api.settings") as capture:
        settings = Settings(path)
    assert settings.get("volume") == pytest.approx(0.45)
    assert any(r.levelno == logging.WARNING and "illisible" in r.getMessage() for r in capture.records)


# ----------------------------------------------------------------- media
def test_natural_path_key_is_relative_to_the_root_when_given():
    root = Path("/r")
    with_root = media.natural_path_key(Path("/r/a/b2.mp4"), root)
    assert with_root == (media.natural_key("a"), media.natural_key("b2.mp4"))
    without_root = media.natural_path_key(Path("/r/a/b2.mp4"))
    assert len(without_root) == len(Path("/r/a/b2.mp4").parts) and without_root[-2:] == with_root
    assert media.natural_path_key(Path("/autre/x.mp4"), root)[-1] == media.natural_key("x.mp4")   # hors racine : chemin complet


def test_iter_media_defaults_are_recursive_and_skip_hidden(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.mp4").write_bytes(b"x")
    (tmp_path / "top.mp4").write_bytes(b"x")
    (tmp_path / ".hidden.mp4").write_bytes(b"x")
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "inside.mp4").write_bytes(b"x")
    default = sorted(p.name for p in media.iter_media(tmp_path))
    assert default == ["deep.mp4", "top.mp4"]                    # récursif par défaut, caché ignoré par défaut
    assert sorted(p.name for p in media.iter_media(tmp_path, recursive=False)) == ["top.mp4"]
    assert ".hidden.mp4" in {p.name for p in media.iter_media(tmp_path, include_hidden=True)}


# ----------------------------------------------------------------- playlist
def test_total_duration_sums_positive_durations_only(media_dir):
    playlist = Playlist("t")
    playlist.add_folder(media_dir("lib", 3))
    playlist[0].duration, playlist[1].duration, playlist[2].duration = 1000, 0, 2500
    assert playlist.total_duration == 3500
    assert Playlist("vide").total_duration == 0


def test_internal_attach_uses_the_given_key_and_ensure_current_keeps_existing(media_dir):
    playlist = Playlist("t")
    playlist.add_folder(media_dir("lib", 2))
    extra = Video(Path("/x/extra.mp4"))
    playlist._attach(extra, "clé-personnalisée")
    assert playlist._by_key["clé-personnalisée"] is extra
    playlist.set_current(1)
    assert playlist.ensure_current() is playlist[1]              # déjà une courante : inchangée


def test_previous_does_not_record_history_and_history_is_bounded(media_dir, tmp_path):
    playlist = Playlist("t")
    playlist.add_folder(media_dir("lib", 4))
    playlist.set_current(2)
    playlist.previous()
    assert playlist._history == []                               # reculer n'ajoute rien à l'historique
    big = Playlist("grand")
    folder = tmp_path / "many"
    folder.mkdir()
    for i in range(HISTORY_LIMIT + 60):
        (folder / f"f{i}.mp4").write_bytes(b"x")
    big.add_folder(folder)
    for i in range(len(big)):
        big.set_current(i)
    assert len(big._history) == HISTORY_LIMIT                    # borné
    assert big._history[-1] is big[len(big) - 2]                 # et ce sont les plus récentes qui restent


# ----------------------------------------------------------------- resume
def test_resume_save_failure_and_forget_flags(tmp_path, monkeypatch):
    store = ResumeStore(tmp_path / "r.json")
    f = tmp_path / "a.mp4"
    store.update(f, 30_000, 100_000)
    assert store.save() is True and store.dirty is False
    store.forget(f)
    assert store.dirty is True and store.position(f) == 0        # oublier = modifié, à sauvegarder
    store.save()
    store.forget(f)                                              # déjà oublié : rien à sauvegarder
    assert store.dirty is False
    store.update(f, 30_000, 100_000)
    store.save()
    store.update(f, 1_000, 100_000)                              # retour au début : l'entrée disparaît → dirty
    assert store.dirty is True
    monkeypatch.setattr("pyplayer.api.resume.write_json_atomic", lambda *a, **k: (_ for _ in ()).throw(OSError("disque plein")))
    assert store.save() is False and store.dirty is True         # échec signalé, état conservé pour un nouvel essai


# ----------------------------------------------------------------- settings
def test_settings_validation_by_type_and_numbers(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"last_playlist_id": 5, "volume": 0.9, "recent_files": ["a"], "muted": True}), encoding="utf-8")
    s = Settings(path)
    assert s.get("last_playlist_id") is None                     # un entier n'est pas un identifiant
    assert s.get("volume") == pytest.approx(0.9) and s.get("recent_files") == ["a"] and s.get("muted") is True
    path.write_text(json.dumps({"last_playlist_id": "abc", "volume": 1}), encoding="utf-8")
    again = Settings(path)
    assert again.get("last_playlist_id") == "abc" and again.get("volume") == 1.0   # entier accepté comme nombre
    path.write_text(json.dumps({"last_playlist_id": None}), encoding="utf-8")
    assert Settings(path).get("last_playlist_id") is None


# ----------------------------------------------------------------- video
def test_resolution_and_aspect_need_both_dimensions():
    v = Video(Path("/x/a.mp4"))
    v.width, v.height = 10, 0
    assert v.resolution == "" and v.aspect_ratio == 0.0          # hauteur nulle : pas de division par zéro
    v.width, v.height = 0, 10
    assert v.resolution == "" and v.aspect_ratio == 0.0
    v.width, v.height = 1920, 1080
    assert v.resolution == "1920x1080" and v.aspect_ratio == pytest.approx(1.778, abs=0.001)


def test_as_int_never_raises():
    assert _as_int(float("inf")) == 0 and _as_int("x") == 0 and _as_int(None) == 0 and _as_int(-5) == 0
    assert _as_int("42") == 42 and _as_int(7.9) == 7 and _as_int(10 ** 400) == 10 ** 400


# ----------------------------------------------------------------- campagne n°3 : survivants restants
def test_aspect_ratio_never_divides_by_zero():
    assert Video(path=Path("a.mp4"), width=640, height=0).aspect_ratio == 0.0
    assert Video(path=Path("a.mp4"), width=0, height=480).aspect_ratio == 0.0
    assert Video(path=Path("a.mp4"), width=1920, height=1080).aspect_ratio == 1.778


def test_video_parent_is_the_containing_folder(tmp_path):
    assert Video(path=tmp_path / "a.mp4").parent == tmp_path


def test_register_marks_a_playlist_dirty_after_changing_a_colliding_id(isolated_home):
    manager = PlaylistManager(isolated_home)
    clone = Playlist("copie")
    clone.id = manager.playlists[0].id
    clone.dirty = False
    manager._register(clone)
    assert clone.id != manager.playlists[0].id and clone.dirty


def test_import_playlist_file_writes_the_playlist_immediately(isolated_home, tmp_path):
    media_file = tmp_path / "a.mp3"
    media_file.write_bytes(b"x")
    m3u = tmp_path / "liste.m3u"
    m3u.write_text(f"#EXTM3U\n{media_file}\n", encoding="utf-8")
    manager = PlaylistManager(isolated_home)
    imported = manager.import_playlist_file(m3u)
    assert imported.file_path is not None and imported.file_path.is_file() and not imported.dirty


def test_legacy_current_index_zero_selects_the_first_video(tmp_path):
    files = []
    for name in ("a.mp4", "b.mp4"):
        (tmp_path / name).write_bytes(b"x")
        files.append({"path": str(tmp_path / name), "name": name})
    data = {"name": "Ancienne", "videos": files, "current_index": 0}
    playlist = Playlist.from_dict(data)
    assert playlist.current is not None and playlist.current.name == "a.mp4"


def test_set_current_with_an_unknown_target_keeps_the_current_video(tmp_path):
    playlist = Playlist("p")
    (tmp_path / "a.mp4").write_bytes(b"x")
    playlist.add(tmp_path / "a.mp4")
    first = playlist.set_current(0)
    assert playlist.set_current("inconnu.mp4") is first and playlist.current is first
