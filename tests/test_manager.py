import json
import time
from pathlib import Path

import pytest

from pyplayer.api.manager import PlaylistManager
from pyplayer.api.playlist import PlayMode


def test_first_launch_creates_default_playlist(tmp_path):
    manager = PlaylistManager(tmp_path)
    assert len(manager) == 1 and manager.active.name == "PLAYLIST"


def test_empty_playlists_do_not_overwrite_each_other(tmp_path):
    manager = PlaylistManager(tmp_path)
    manager.create_playlist("A")
    manager.create_playlist("B")
    assert len(manager) == 3  # audit 1.1
    assert len(PlaylistManager(tmp_path)) == 3  # et après redémarrage


def test_two_playlists_from_same_folder_coexist(tmp_path, media_dir):
    folder = media_dir("movies", 3)
    manager = PlaylistManager(tmp_path / "home")
    first = manager.create_playlist("X", folder)
    second = manager.create_playlist("Y", folder)
    assert first.id != second.id and len(first) == len(second) == 3
    reloaded = PlaylistManager(tmp_path / "home")
    assert sorted(p.name for p in reloaded) == ["PLAYLIST", "X", "Y"]


def test_duplicate_names_are_made_unique(tmp_path):
    manager = PlaylistManager(tmp_path)
    assert manager.create_playlist("Rock").name == "Rock"
    assert manager.create_playlist("rock").name == "rock (2)"


def test_backups_are_never_reloaded_as_playlists(tmp_path, media_dir):
    folder = media_dir("movies", 2)
    home = tmp_path / "home"
    manager = PlaylistManager(home)
    playlist = manager.create_playlist("Films", folder)
    manager.flush()
    PlaylistManager(home)  # crée un instantané
    PlaylistManager(home)
    reloaded = PlaylistManager(home)
    films = [p for p in reloaded if p.name == "Films"]
    assert len(films) == 1 and films[0].file_path == playlist.file_path  # audit 1.2
    assert all(not p.file_path.name.count(".backup.") for p in reloaded)
    assert list((home / "playlists" / "backups").glob("*.json"))


def test_stray_legacy_backups_are_moved_out_of_playlist_dir(tmp_path):
    home = tmp_path / "home"
    (home / "playlists").mkdir(parents=True)
    legacy = home / "playlists" / "PLAYLIST.backup.20250101_120000.json"
    legacy.write_text("{}", encoding="utf-8")
    manager = PlaylistManager(home)
    assert not legacy.exists()
    assert len(manager) == 1
    assert list((home / "playlists" / "backups").glob("PLAYLIST.*.json"))


def test_backups_are_rotated(tmp_path):
    home = tmp_path / "home"
    manager = PlaylistManager(home)
    playlist = manager.create_playlist("Rot")
    backups = home / "playlists" / "backups"
    for i in range(9):
        playlist.description = f"v{i}"
        playlist.mark_dirty()
        manager.flush()
        time.sleep(0.01)
        PlaylistManager(home)
        # force un contenu différent à chaque démarrage
    assert len(list(backups.glob("Rot-*.json"))) <= 5


def test_remove_playlist_picks_new_active_and_never_leaves_none(tmp_path):
    manager = PlaylistManager(tmp_path)
    other = manager.create_playlist("Other")
    manager.set_active(other.id)
    assert manager.remove_playlist(other.id)
    assert manager.active is not None and manager.active.id != other.id  # audit 2.3
    only = manager.active
    assert manager.remove_playlist(only.id)
    assert len(manager) == 1 and manager.active is not None  # une playlist vide est recréée
    assert manager.remove_playlist("inconnue") is False


def test_remove_playlist_deletes_file_and_backups(tmp_path):
    home = tmp_path / "home"
    manager = PlaylistManager(home)
    playlist = manager.create_playlist("Tmp")
    manager.flush()
    PlaylistManager(home)
    path = playlist.file_path
    manager.remove_playlist(playlist.id)
    assert not path.exists()
    assert not list((home / "playlists" / "backups").glob("Tmp-*.json"))
    assert "Tmp" not in [p.name for p in PlaylistManager(home)]


def test_active_playlist_is_restored(tmp_path):
    manager = PlaylistManager(tmp_path)
    other = manager.create_playlist("Other")
    manager.set_active(other.id)
    manager.flush()
    assert PlaylistManager(tmp_path).active.name == "Other"


def test_set_active_unknown_id(tmp_path):
    assert PlaylistManager(tmp_path).set_active("nope") is False


def test_quick_playlist_is_created_once(tmp_path):
    manager = PlaylistManager(tmp_path)
    assert manager.quick_playlist() is manager.quick_playlist()
    assert manager.quick_playlist().kind == "quick"
    assert manager.active.kind != "quick"


def test_flush_writes_only_dirty_playlists(tmp_path, media_dir):
    folder = media_dir("m", 3)
    manager = PlaylistManager(tmp_path / "h")
    playlist = manager.create_playlist("P", folder)
    manager.flush()
    before = playlist.file_path.stat().st_mtime_ns
    time.sleep(0.02)
    manager.flush()
    assert playlist.file_path.stat().st_mtime_ns == before
    playlist.set_current(1)
    assert playlist.dirty
    manager.flush()
    assert not playlist.dirty and playlist.file_path.stat().st_mtime_ns > before


def test_position_ticks_do_not_touch_playlists(tmp_path, media_dir):
    folder = media_dir("m", 500)
    manager = PlaylistManager(tmp_path / "h")
    playlist = manager.create_playlist("P", folder)
    manager.flush()
    start = time.perf_counter()
    for i in range(200):
        manager.resume.update(playlist[0].path, 10_000 + i * 100, 600_000)
    assert time.perf_counter() - start < 0.1  # audit 3.1 : 12,5 ms par tick avant
    assert not playlist.dirty


def test_corrupt_file_restored_from_backup(tmp_path, media_dir):
    folder = media_dir("m", 2)
    home = tmp_path / "h"
    manager = PlaylistManager(home)
    playlist = manager.create_playlist("Good", folder)
    manager.flush()
    PlaylistManager(home)  # instantané
    playlist.file_path.write_text('{"corrupt":', encoding="utf-8")
    restored = PlaylistManager(home)
    assert [p.name for p in restored if p.name == "Good"] == ["Good"]
    assert len(next(p for p in restored if p.name == "Good")) == 2


def test_corrupt_file_without_backup_is_quarantined(tmp_path):
    home = tmp_path / "h"
    (home / "playlists").mkdir(parents=True)
    bad = home / "playlists" / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    manager = PlaylistManager(home)
    assert len(manager) == 1  # la playlist par défaut
    assert (home / "playlists" / "bad.corrupt").exists() and not bad.exists()


def test_v1_files_migrated_with_positions_and_rewritten(tmp_path, media_dir):
    folder = media_dir("old", 2)
    home = tmp_path / "h"
    (home / "playlists").mkdir(parents=True)
    legacy = {
        "version": "1.0", "path": str(folder), "name": "Old", "unique_id": "DEADBEEF",
        "play_mode": "normal", "current_index": 0,
        "videos": [{"file_path": str(folder / "v0.mp4"), "duration": 100_000,
                    "state": {"position": 33_000}}],
    }
    legacy_file = home / "playlists" / "Old.json"
    legacy_file.write_text(json.dumps(legacy), encoding="utf-8")
    (home / "playlists" / "manager_config.json").write_text(json.dumps({"volume": 0.7}), encoding="utf-8")
    manager = PlaylistManager(home)
    old = next(p for p in manager if p.name == "Old")
    assert old.id != "DEADBEEF" and json.loads(legacy_file.read_text())["version"] == 2
    assert manager.resume.position(folder / "v0.mp4") == 33_000
    assert manager.volume == pytest.approx(0.7)
    assert list((home / "playlists" / "backups").glob("Old.v1.json"))


def test_m3u_export_import_roundtrip(tmp_path, media_dir):
    folder = media_dir("m", 3)
    manager = PlaylistManager(tmp_path / "h")
    playlist = manager.create_playlist("Src", folder)
    target = tmp_path / "out.m3u8"
    manager.export_playlist(playlist, target)
    imported = manager.import_playlist_file(target)
    assert imported.name == "out" and [v.name for v in imported] == [v.name for v in playlist]


def test_rename_and_find_by_source(tmp_path, media_dir):
    folder = media_dir("m", 1)
    manager = PlaylistManager(tmp_path / "h")
    playlist = manager.create_playlist("N", folder)
    assert manager.rename(playlist.id, "Nouveau") and playlist.name == "Nouveau"
    assert manager.rename(playlist.id, "  ") is False
    assert manager.find_by_source(folder) is playlist


def test_play_mode_and_current_persist(tmp_path, media_dir):
    folder = media_dir("m", 3)
    manager = PlaylistManager(tmp_path / "h")
    playlist = manager.create_playlist("P", folder)
    playlist.set_mode(PlayMode.LOOP_ALL)
    playlist.set_current(2)
    manager.flush()
    reloaded = next(p for p in PlaylistManager(tmp_path / "h") if p.name == "P")
    assert reloaded.play_mode is PlayMode.LOOP_ALL and reloaded.current_index == 2


def test_an_empty_playlist_is_still_a_playlist(tmp_path):
    """Régression : ``Playlist`` définit ``__len__`` ; une playlist vide était « fausse » et ne pouvait pas être renommée."""
    manager = PlaylistManager(tmp_path)
    empty = manager.create_playlist("Vide")
    assert len(empty) == 0 and bool(empty) is True
    assert manager.rename(empty.id, "Renommée") and empty.name == "Renommée"
    assert manager.get(empty.id) is empty
    assert manager.set_active(empty.id) and manager.active is empty


# ----------------------------------------------------------------- import M3U : pas de doublons
def _m3u(folder, names, title="Ma liste"):
    for name in names:
        (folder / name).write_bytes(b"x")
    playlist = folder / f"{title}.m3u"
    playlist.write_text("#EXTM3U\n" + "\n".join(str(folder / n) for n in names) + "\n", encoding="utf-8")
    return playlist


def test_importing_the_same_m3u_twice_returns_the_same_playlist(isolated_home, tmp_path):
    manager = PlaylistManager(isolated_home)
    m3u = _m3u(tmp_path, ["a.mp3", "b.mp3"])
    first = manager.import_playlist_file(m3u)
    count = len(manager)
    second = manager.import_playlist_file(m3u)
    assert second is first and len(manager) == count and [v.name for v in first] == ["a.mp3", "b.mp3"]


def test_a_reordered_playlist_is_still_recognised_but_a_changed_one_is_new(isolated_home, tmp_path):
    manager = PlaylistManager(isolated_home)
    m3u = _m3u(tmp_path, ["a.mp3", "b.mp3"])
    first = manager.import_playlist_file(m3u)
    first.reorder(list(reversed(first.videos)))                       # l'utilisateur a changé l'ordre
    assert manager.import_playlist_file(m3u) is first
    (tmp_path / "c.mp3").write_bytes(b"x")
    m3u.write_text(f"{tmp_path / 'a.mp3'}\n{tmp_path / 'b.mp3'}\n{tmp_path / 'c.mp3'}\n", encoding="utf-8")
    changed = manager.import_playlist_file(m3u)
    assert changed is not first and len(changed) == 3                  # contenu différent : nouvelle playlist


def test_the_quick_playlist_and_other_names_never_count_as_duplicates(isolated_home, tmp_path):
    manager = PlaylistManager(isolated_home)
    quick = manager.quick_playlist()
    (tmp_path / "a.mp3").write_bytes(b"x")
    quick.add(tmp_path / "a.mp3")
    one = manager.import_playlist_file(_m3u(tmp_path, ["a.mp3"], "Quick"))
    other = manager.import_playlist_file(_m3u(tmp_path, ["a.mp3"], "Autre nom"))
    assert one is not quick and other is not one
