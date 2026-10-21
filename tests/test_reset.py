"""Réinitialisation des données : ne supprime que ce qui appartient à PyPlayer, rapporte les erreurs, jamais de levée."""

import os
import stat

import pytest

from pyplayer.api import reset
from pyplayer.api.manager import PlaylistManager
from pyplayer.api.reset import ALL_CATEGORIES, format_size, reset_data, summarize


def populated_home(isolated_home):
    manager = PlaylistManager(isolated_home)
    playlist = manager.create_playlist("Rock")
    playlist.mark_dirty()
    manager.flush()
    PlaylistManager(isolated_home)                       # crée un instantané
    (isolated_home / "resume.json").write_text("{}", encoding="utf-8")
    (isolated_home / "settings.json").write_text("{}", encoding="utf-8")
    (isolated_home / "pyplayer.log").write_text("ligne\n", encoding="utf-8")
    (isolated_home / "pyplayer.log.1").write_text("ancienne\n", encoding="utf-8")
    return manager


def test_summary_counts_every_category(isolated_home):
    populated_home(isolated_home)
    info = {i.key: i for i in summarize(isolated_home)}
    assert set(info) == set(ALL_CATEGORIES)
    assert info[reset.PLAYLISTS].files >= 1 and info[reset.BACKUPS].files >= 1
    assert info[reset.RESUME].files == 1 and info[reset.SETTINGS].files == 1 and info[reset.LOGS].files == 2
    assert all(i.size > 0 for i in info.values())


def test_reset_everything_empties_user_data_but_keeps_foreign_files(isolated_home, tmp_path):
    populated_home(isolated_home)
    foreign = isolated_home / "notes_perso.txt"
    foreign.write_text("à moi", encoding="utf-8")
    media = tmp_path / "film.mp4"
    media.write_bytes(b"x")
    report = reset_data(isolated_home)
    assert report.ok and report.deleted_files >= 6 and report.freed_bytes > 0
    assert not (isolated_home / "resume.json").exists() and not (isolated_home / "settings.json").exists()
    assert not (isolated_home / "pyplayer.log.1").exists()
    assert (isolated_home / "pyplayer.log").read_text(encoding="utf-8") == ""       # journal ouvert : vidé, pas supprimé
    assert not (isolated_home / "playlists").exists()                               # dossiers vides retirés
    assert foreign.read_text(encoding="utf-8") == "à moi" and media.read_bytes() == b"x"
    assert isolated_home.is_dir()                                                   # le dossier de données reste


def test_reset_only_the_selected_categories(isolated_home):
    populated_home(isolated_home)
    report = reset_data(isolated_home, [reset.RESUME])
    assert report.deleted_files == 1
    assert not (isolated_home / "resume.json").exists()
    assert (isolated_home / "settings.json").exists() and any((isolated_home / "playlists").glob("*.json"))


def test_reset_is_idempotent_and_works_on_an_empty_home(isolated_home):
    assert reset_data(isolated_home).deleted_files == 0
    populated_home(isolated_home)
    reset_data(isolated_home)
    assert reset_data(isolated_home).deleted_files == 0


def test_unknown_category_is_rejected_before_deleting_anything(isolated_home):
    populated_home(isolated_home)
    with pytest.raises(KeyError):
        reset_data(isolated_home, [reset.RESUME, "tout"])
    assert (isolated_home / "resume.json").exists()


@pytest.mark.skipif(os.name == "nt", reason="droits POSIX")
def test_errors_are_reported_not_raised_and_other_files_are_still_deleted(isolated_home):
    populated_home(isolated_home)
    folder = isolated_home / "playlists"
    original = folder.stat().st_mode
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)             # plus d'écriture : suppression des playlists impossible
    try:
        if os.access(folder, os.W_OK):
            pytest.skip("exécuté avec des droits qui ignorent les permissions (root)")
        report = reset_data(isolated_home)
        assert not report.ok and report.errors
        assert not (isolated_home / "resume.json").exists()                       # le reste a bien été supprimé
    finally:
        folder.chmod(original)


def test_a_playlist_folder_with_user_files_is_never_removed(isolated_home):
    populated_home(isolated_home)
    note = isolated_home / "playlists" / "a_garder.txt"
    note.write_text("x", encoding="utf-8")
    reset_data(isolated_home)
    assert note.exists()


def test_format_size():
    assert format_size(0) == "0 o" and format_size(1023) == "1023 o"
    assert format_size(1536) == "1.5 Ko" and format_size(5 * 1024 * 1024) == "5.0 Mo"
