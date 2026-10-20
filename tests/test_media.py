import pytest
from pathlib import Path

from pyplayer.api import media


def test_natural_sort_orders_numbers_numerically():
    names = ["ep10.mp4", "ep2.mp4", "ep1.mp4", "Ep3.mp4"]
    assert sorted(names, key=media.natural_key) == ["ep1.mp4", "ep2.mp4", "Ep3.mp4", "ep10.mp4"]


def test_natural_key_never_compares_int_with_str():
    # « 1a » / « a1 » / « 10 » : la clé alterne toujours str, int, str...
    sorted(["1a", "a1", "10", "", "a", "9z"], key=media.natural_key)


def test_scan_folder_sorted_recursive_and_ignores_non_media(tmp_path):
    (tmp_path / "s1").mkdir()
    (tmp_path / "s1" / "ep10.mkv").write_bytes(b"x")
    (tmp_path / "s1" / "ep2.mkv").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / ".hidden.mp4").write_bytes(b"x")
    found = [p.relative_to(tmp_path).as_posix() for p in media.scan_folder(tmp_path)]
    assert found == ["s1/ep2.mkv", "s1/ep10.mkv"]
    assert media.scan_folder(tmp_path, recursive=False) == []


def test_scan_folder_missing_dir_returns_empty(tmp_path):
    assert media.scan_folder(tmp_path / "absent") == []


def test_scan_folder_survives_symlink_loop(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.mp4").write_bytes(b"x")
    try:
        (tmp_path / "a" / "loop").symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    assert [p.name for p in media.scan_folder(tmp_path)] == ["x.mp4"]


def test_formatters():
    assert media.format_duration(65_000) == "1:05"
    assert media.format_duration(3_725_000) == "1:02:05"
    assert media.format_duration(-5) == "0:00"
    assert media.format_size(512) == "512 o"
    assert media.format_size(1536) == "1.5 Ko"


def test_extension_helpers():
    assert media.is_media("A.MKV") and media.is_media(Path("x.flac"))
    assert not media.is_media("x.txt")
    assert media.is_audio("x.mp3") and not media.is_audio("x.mp4")
    assert media.is_playlist_file("x.m3u8")


def test_subtitles_parse_srt_vtt_and_lookup(tmp_path):
    from pyplayer.api.subtitles import SubtitleTrack, find_sidecar, load_subtitle_file, parse_subtitles
    cues = parse_subtitles("1\n00:00:01,000 --> 00:00:03,500\nBonjour <i>toi</i>\n\n"
                           "WEBVTT-like\n00:01:00.000 --> 00:01:02.000\nSalut\nsuite\n\nbloc invalide\n")
    assert [c.text for c in cues] == ["Bonjour toi", "Salut\nsuite"]
    track = SubtitleTrack(cues)
    assert track.text_at(2000) == "Bonjour toi" and track.text_at(4000) == "" and track.text_at(61_000) == "Salut\nsuite"
    track.delay = 1000
    assert track.text_at(1500) == "" and track.text_at(2500) == "Bonjour toi"
    video = tmp_path / "film.mkv"
    video.write_bytes(b"x")
    assert find_sidecar(video) is None
    sub = tmp_path / "film.fr.srt"
    sub.write_bytes("1\n00:00:00,000 --> 00:00:01,000\néé\n".encode("cp1252"))
    assert find_sidecar(video) == sub and load_subtitle_file(sub)[0].text == "éé"


def test_count_media_is_capped(tmp_path):
    for i in range(12):
        (tmp_path / f"{i}.mp4").write_bytes(b"x")
    assert media.count_media(tmp_path) == (12, False)
    assert media.count_media(tmp_path, limit=5) == (5, True)
    assert media.count_media(tmp_path / "absent") == (0, False)


@pytest.mark.parametrize("name", ["²", "1²2", "film³.mp4", "٣", "Ⅻ.mp4", "ep½.mp4", "a١٢٣b"])
def test_natural_key_survives_unicode_digits_that_int_rejects(name):
    media.natural_key(name)  # régression : « ² ».isdigit() est vrai mais int("²") lève ValueError


def test_scan_folder_with_exotic_file_names(tmp_path):
    for name in ("²", "film³.mp4", "ep٣.mp4", "ep10.mp4", "ep2.mp4", "ⅫⅫ.mkv"):
        (tmp_path / name).write_bytes(b"x")
    # « ² » n'est pas un média ; le reste est trié naturellement (ep2 < ep٣=3 < ep10) sans planter
    assert [p.name for p in media.scan_folder(tmp_path)] == ["ep2.mp4", "ep٣.mp4", "ep10.mp4", "film³.mp4", "ⅫⅫ.mkv"]


def test_subtitle_lookup_does_not_miss_a_long_cue_hidden_behind_many_short_ones():
    """Contre-exemple trouvé par Hypothesis (profil approfondi) : 5 cues démarrant ensemble, une seule encore active."""
    from pyplayer.api.subtitles import Cue, SubtitleTrack
    track = SubtitleTrack([Cue(0, 2, "long")] + [Cue(0, 1, f"court{i}") for i in range(4)])
    assert track.text_at(1) == "long" and track.text_at(0) == "court3" and track.text_at(2) == ""
    nested = SubtitleTrack([Cue(0, 100, "fond")] + [Cue(10 * i, 10 * i + 5, f"x{i}") for i in range(1, 9)])
    assert nested.text_at(47) == "fond" and nested.text_at(42) == "x4"
