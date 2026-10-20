import random

import pytest

from pyplayer.api.playlist import PlayMode, Playlist


def make(media_dir, n=5, **kwargs):
    folder = media_dir("lib", n)
    playlist = Playlist("t", source=folder, **kwargs)
    playlist.add_folder(folder)
    return playlist


# ----------------------------------------------------------------- ajout / identité
def test_each_playlist_has_unique_id_even_when_empty_or_same_source(media_dir):
    folder = media_dir("lib", 2)
    ids = {Playlist("a").id, Playlist("b").id, Playlist("c", source=folder).id, Playlist("d", source=folder).id}
    assert len(ids) == 4  # audit 1.1


def test_add_rejects_duplicates_missing_and_non_media(media_dir, tmp_path):
    playlist = make(media_dir, 2)
    first = playlist[0].path
    assert playlist.add(first) is None
    assert playlist.add(tmp_path / "absent.mp4") is None
    note = tmp_path / "note.txt"
    note.write_text("x")
    assert playlist.add(note) is None
    assert len(playlist) == 2


def test_folder_is_loaded_in_natural_order(tmp_path):
    for n in (10, 2, 1):
        (tmp_path / f"ep{n}.mp4").write_bytes(b"x")
    playlist = Playlist("t")
    playlist.add_folder(tmp_path)
    assert [v.name for v in playlist] == ["ep1.mp4", "ep2.mp4", "ep10.mp4"]


def test_same_file_name_in_two_folders_are_distinct_videos(tmp_path):
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "ep1.mp4").write_bytes(b"x")
    playlist = Playlist("t")
    playlist.add_folder(tmp_path)
    assert len(playlist) == 2 and playlist[0].path != playlist[1].path  # audit 2.8


def test_add_many_marks_dirty_once_and_is_fast(media_dir):
    folder = media_dir("big", 800)
    playlist = Playlist("t")
    import time
    start = time.perf_counter()
    added = playlist.add_folder(folder)
    assert len(added) == 800 and time.perf_counter() - start < 2.0  # audit 3.2 (5 s pour 300 avant)
    assert playlist.dirty


# ----------------------------------------------------------------- navigation
def test_normal_mode_stops_at_end_and_keeps_current(media_dir):
    playlist = make(media_dir, 3)
    playlist.set_current(2)
    assert playlist.next() is None  # audit 2.4 : pas de rejeu silencieux
    assert playlist.current is playlist[2]
    assert playlist.previous() is playlist[1]
    playlist.set_current(0)
    assert playlist.previous() is None


def test_loop_all_wraps_both_ways(media_dir):
    playlist = make(media_dir, 3)
    playlist.set_mode(PlayMode.LOOP_ALL)
    playlist.set_current(2)
    assert playlist.next() is playlist[0]
    assert playlist.previous() is playlist[2]


def test_loop_one_auto_replays_but_manual_next_advances(media_dir):
    playlist = make(media_dir, 3)
    playlist.set_mode(PlayMode.LOOP_ONE)
    playlist.set_current(0)
    assert playlist.next(auto=True) is playlist[0]
    assert playlist.next() is playlist[1]


def test_next_without_current_activates_first(media_dir):
    playlist = make(media_dir, 3)
    assert playlist.next() is playlist[0]
    assert Playlist("empty").next() is None and Playlist("empty").previous() is None


def test_ensure_current_empty_and_filled(media_dir):
    assert Playlist("e").ensure_current() is None
    playlist = make(media_dir, 2)
    assert playlist.ensure_current() is playlist[0]


# ----------------------------------------------------------------- aléatoire
def test_shuffle_plays_every_video_once_per_cycle(media_dir):
    random.seed(1)
    playlist = make(media_dir, 6)
    playlist.set_mode(PlayMode.SHUFFLE)
    playlist.set_current(0)
    seen = [playlist.current] + [playlist.next() for _ in range(5)]
    assert {id(v) for v in seen} == {id(v) for v in playlist}


def test_shuffle_never_repeats_across_cycle_boundary(media_dir):
    random.seed(7)
    playlist = make(media_dir, 4)
    playlist.set_mode(PlayMode.SHUFFLE)
    playlist.ensure_current()
    previous = playlist.current
    for _ in range(60):
        current = playlist.next()
        assert current is not previous
        previous = current


def test_shuffle_previous_walks_back_through_history(media_dir):
    random.seed(3)
    playlist = make(media_dir, 6)
    playlist.set_mode(PlayMode.SHUFFLE)
    first = playlist.ensure_current()
    second = playlist.next()
    third = playlist.next()
    assert playlist.previous() is second
    assert playlist.previous() is first


def test_remove_other_video_in_shuffle_keeps_current(media_dir):
    random.seed(5)
    playlist = make(media_dir, 6)
    playlist.set_mode(PlayMode.SHUFFLE)
    playlist.ensure_current()
    playlist.next(); playlist.next()
    current = playlist.current
    victim = next(v for v in playlist if v is not current)
    playlist.remove(victim)
    assert playlist.current is current  # audit 2.1 : la vidéo courante ne bouge plus


def test_shuffle_history_never_points_to_removed_or_wrong_video(media_dir):
    random.seed(11)
    playlist = make(media_dir, 6)
    playlist.set_mode(PlayMode.SHUFFLE)
    playlist.ensure_current()
    visited = [playlist.current, playlist.next(), playlist.next()]
    playlist.remove(visited[1])
    assert playlist.previous() is visited[0]  # audit 2.2


def test_added_video_enters_current_shuffle_cycle(media_dir, tmp_path):
    random.seed(2)
    playlist = make(media_dir, 3)
    playlist.set_mode(PlayMode.SHUFFLE)
    playlist.ensure_current()
    extra = tmp_path / "extra.mp4"
    extra.write_bytes(b"x")
    new = playlist.add(extra)
    seen = {id(playlist.next()) for _ in range(3)}
    assert id(new) in seen


# ----------------------------------------------------------------- réorganisation
def test_move_keeps_current_video(media_dir):
    playlist = make(media_dir, 5)
    playlist.set_current(1)
    current = playlist.current
    playlist.move(1, 4)
    assert playlist.current is current and playlist.current_index == 4
    assert playlist.move(0, 99) is False


def test_remove_current_clears_selection_and_removing_before_keeps_it(media_dir):
    playlist = make(media_dir, 4)
    playlist.set_current(2)
    current = playlist.current
    playlist.remove(0)
    assert playlist.current is current and playlist.current_index == 1
    playlist.remove(current)
    assert playlist.current is None


def test_remove_many_and_unknown_items(media_dir):
    playlist = make(media_dir, 5)
    assert playlist.remove_many([0, 1, playlist[2], 99, "inconnu"]) == 3
    assert len(playlist) == 2
    assert playlist.remove(object()) is False  # type: ignore[arg-type]


def test_sort_natural_and_invalid_key(media_dir, tmp_path):
    folder = tmp_path / "s"
    folder.mkdir()
    for n in (10, 9, 1):
        (folder / f"e{n}.mp4").write_bytes(b"x")
    playlist = Playlist("t")
    playlist.add_many(sorted(folder.iterdir()))
    playlist.sort("name")
    assert [v.name for v in playlist] == ["e1.mp4", "e9.mp4", "e10.mp4"]
    playlist.sort("name", reverse=True)
    assert playlist[0].name == "e10.mp4"
    with pytest.raises(ValueError):
        playlist.sort("couleur")


def test_clear_and_remove_missing(media_dir):
    playlist = make(media_dir, 3)
    playlist[0].path.unlink()
    missing = playlist.remove_missing()
    assert [m.name for m in missing] == ["v0.mp4"] and len(playlist) == 2
    playlist.clear()
    assert len(playlist) == 0 and playlist.current is None


def test_refresh_from_source_adds_only_new_files(media_dir):
    playlist = make(media_dir, 2)
    new = playlist.source / "zzz.mp4"
    new.write_bytes(b"x")
    assert [v.name for v in playlist.refresh_from_source()] == ["zzz.mp4"]


# ----------------------------------------------------------------- sérialisation
def test_roundtrip_preserves_everything(media_dir):
    playlist = make(media_dir, 3, description="d")
    playlist.set_mode(PlayMode.LOOP_ALL)
    playlist.set_current(1)
    playlist[1].update_metadata(width=1920, height=1080, duration=60_000)
    restored = Playlist.from_dict(playlist.to_dict())
    assert restored.id == playlist.id and restored.play_mode is PlayMode.LOOP_ALL
    assert restored.current_index == 1 and restored[1].resolution == "1920x1080"
    assert restored.description == "d" and not restored.dirty


def test_from_dict_skips_corrupt_entries_and_rejects_garbage(media_dir):
    data = make(media_dir, 2).to_dict()
    data["videos"].append({"nothing": 1})
    data["videos"].append("not a dict")
    assert len(Playlist.from_dict(data)) == 2
    with pytest.raises(ValueError):
        Playlist.from_dict("nope")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Playlist.from_dict({"name": "x"})
    with pytest.raises(ValueError):
        Playlist.from_dict({"videos": []})                              # pas de signature de format
    with pytest.raises(ValueError):
        Playlist.from_dict({"version": 2, "id": "x", "name": "n", "videos": [1, None, "x"]})  # tout est corrompu


def test_legacy_v1_format_is_migrated(media_dir):
    folder = media_dir("old", 2)
    legacy = {
        "version": "1.0", "path": str(folder), "name": "Films", "unique_id": "A5F09E27",
        "play_mode": "loop_all", "current_index": 1,
        "videos": [
            {"file_path": str(folder / "v0.mp4"), "size": 1, "duration": 90_000,
             "state": {"position": 42_000, "duration": 90_000}},
            {"file_path": str(folder / "v1.mp4"), "size": 1, "width": 640, "height": 360},
        ],
        "shuffle_state": None, "playlist_state": {},
    }
    playlist = Playlist.from_dict(legacy)
    assert playlist.id != "A5F09E27" and len(playlist.id) == 32
    assert playlist.name == "Films" and playlist.source == folder
    assert playlist.current_index == 1 and playlist.play_mode is PlayMode.LOOP_ALL
    assert playlist.dirty  # sera réécrite au nouveau format
    assert list(playlist._legacy_positions.values()) == [(42_000, 90_000)]


def test_mode_roundtrip_and_unknown_value():
    assert PlayMode.from_value("shuffle") is PlayMode.SHUFFLE
    assert PlayMode.from_value("???") is PlayMode.NORMAL


def test_reorder_applies_permutation_and_keeps_current(media_dir):
    playlist = make(media_dir, 4)
    playlist.set_current(1)
    current = playlist.current
    new = [playlist[3], playlist[1], playlist[0], playlist[2]]
    assert playlist.reorder(new) and list(playlist) == new and playlist.current is current
    assert playlist.reorder(new[:3]) is False and playlist.reorder(new + new[:1]) is False
