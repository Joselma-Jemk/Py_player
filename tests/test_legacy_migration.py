"""Migration depuis les vrais fichiers produits par l'ancienne version (v1) de PyPlayer.

Les fixtures de ``tests/fixtures/legacy_v1`` ont été générées en exécutant le code d'origine
(commit bfd030c) : playlists en mode boucle et aléatoire, positions, backups au mauvais endroit, etc.
"""

import json
import shutil
from pathlib import Path

import pytest

from pyplayer.api.manager import PlaylistManager
from pyplayer.api.media import path_key
from pyplayer.api.playlist import PlayMode

FIXTURES = Path(__file__).parent / "fixtures" / "legacy_v1"
MEDIA_FILES = ["shows/ep10.mkv", "shows/ep2.mp4", "shows/ep1.mp4", "shows/s2/a.avi", "shows/s2/b.webm",
               "music/t1.mp3", "music/t2.flac"]


@pytest.fixture
def legacy_home(tmp_path):
    media = tmp_path / "media"
    for relative in MEDIA_FILES:
        target = media / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x" * 128)
    home = tmp_path / "home"
    playlists = home / "playlists"
    playlists.mkdir(parents=True)
    for fixture in FIXTURES.glob("*.json"):
        text = fixture.read_text(encoding="utf-8").replace("{{MEDIA}}", str(media).replace("\\", "\\\\"))
        (playlists / fixture.name).write_text(text, encoding="utf-8")
    return home, media


def by_name(manager, name):
    return next(p for p in manager if p.name == name)


def test_legacy_playlists_are_migrated_without_loss(legacy_home):
    home, media = legacy_home
    manager = PlaylistManager(home)
    assert {p.name for p in manager} == {"PLAYLIST", "Musique", "Séries"} and len(manager) == 3  # les 3 backups ne sont PAS des playlists
    shows = by_name(manager, "Séries")
    assert len(shows) == 5 and shows.play_mode is PlayMode.LOOP_ALL
    assert shows.current.name == "ep2.mp4"                                         # current_index 1 d'origine
    assert shows.source == media / "shows"
    assert len({p.id for p in manager}) == 3 and all(len(p.id) == 32 for p in manager)
    # L'ancienne version ignorait les fichiers audio : la playlist « Musique » v1 est vide, et reste cohérente.
    music = by_name(manager, "Musique")
    assert music.play_mode is PlayMode.SHUFFLE and len(music) == 0
    assert len(music.refresh_from_source()) == 2          # la nouvelle version, elle, lit l'audio


def test_legacy_positions_become_resume_entries_but_ends_and_starts_are_ignored(legacy_home):
    home, media = legacy_home
    manager = PlaylistManager(home)
    assert manager.resume.position(media / "shows/ep10.mkv") == 65_000      # 65 s sur 120 s : repris
    assert manager.resume.position(media / "shows/ep2.mp4") == 0             # 1 s : on repart du début
    assert manager.resume.position(media / "shows/ep1.mp4") == 0             # 89 s sur 90 s : terminé (audit 2.9)


def test_legacy_volume_and_last_active_playlist_are_preserved(legacy_home):
    home, _ = legacy_home
    manager = PlaylistManager(home)
    assert manager.volume == pytest.approx(0.42)
    assert manager.active.name == "Séries"                                   # « dernière playlist jouée » retrouvée


def test_legacy_backups_are_moved_and_originals_snapshotted(legacy_home):
    home, _ = legacy_home
    PlaylistManager(home)
    playlists = home / "playlists"
    assert not list(playlists.glob("*.backup.*"))
    backups = {p.name for p in (playlists / "backups").glob("*.json")}
    assert any(name.startswith("shows.") and name.endswith(".v1.json") for name in backups)   # copie du v1 avant réécriture
    assert any(name.startswith("music.20261020") or name.startswith("music.") for name in backups)


def test_migrated_files_are_rewritten_as_v2_and_migration_is_idempotent(legacy_home):
    home, media = legacy_home
    first = PlaylistManager(home)
    ids = {p.name: p.id for p in first}
    order = [v.name for v in by_name(first, "Séries")]
    for file in (home / "playlists").glob("*.json"):
        if file.name not in ("last_played.json", "manager_config.json"):
            assert json.loads(file.read_text(encoding="utf-8"))["version"] == 2, file.name
    first.flush()
    second = PlaylistManager(home)
    assert {p.name: p.id for p in second} == ids                              # mêmes IDs : aucune re-migration
    assert [v.name for v in by_name(second, "Séries")] == order
    assert second.active.name == "Séries"
    assert second.resume.position(media / "shows/ep10.mkv") == 65_000


def test_legacy_files_never_crash_when_media_is_gone(legacy_home):
    home, media = legacy_home
    shutil.rmtree(media)
    manager = PlaylistManager(home)
    shows = by_name(manager, "Séries")
    assert len(shows) == 5                                                    # les entrées sont conservées (disque démonté ?)
    assert len(shows.remove_missing()) == 5 and len(shows) == 0


def test_legacy_ids_do_not_collide_with_new_playlists(legacy_home):
    home, _ = legacy_home
    manager = PlaylistManager(home)
    created = [manager.create_playlist(f"new{i}") for i in range(5)]
    assert len({p.id for p in manager}) == len(manager) == 3 + 5
    assert all(path_key(p.file_path) for p in created)
