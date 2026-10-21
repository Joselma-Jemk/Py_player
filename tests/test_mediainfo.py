"""Informations détaillées sur un média : formats, lecture de ffprobe, fusion, empreinte, dialogue."""

import json
import shutil
import subprocess

import pytest
from hypothesis import given, strategies as st

from pyplayer.api import mediainfo
from pyplayer.api.mediainfo import (InfoSection, bitrate_text, file_section, fraction, merge, probe, qt_section,
                                    sections_from_probe, seconds_text, sha256_file, to_text)

from tests.test_ui import qapp, wait_until  # noqa: E402,F401 -- qapp est une fixture

FFMPEG, FFPROBE = shutil.which("ffmpeg"), shutil.which("ffprobe")

SAMPLE = {
    "format": {"format_name": "matroska,webm", "format_long_name": "Matroska / WebM", "duration": "125.5",
               "bit_rate": "2500000", "nb_streams": 4, "tags": {"TITLE": "Mon film", "ENCODER": "Lavf60"}},
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "codec_long_name": "H.264 / AVC", "profile": "High", "level": 41,
         "width": 1920, "height": 1080, "display_aspect_ratio": "16:9", "avg_frame_rate": "30000/1001",
         "pix_fmt": "yuv420p", "bits_per_raw_sample": "8", "color_space": "bt709", "bit_rate": "2200000",
         "tags": {"language": "und"}, "side_data_list": [{"rotation": -90}], "disposition": {}},
        {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
        {"codec_type": "audio", "codec_name": "aac", "channels": 2, "channel_layout": "stereo", "sample_rate": "48000",
         "bit_rate": "128000", "tags": {"language": "fra", "title": "Français"}, "disposition": {"default": 1}},
        {"codec_type": "audio", "codec_name": "opus", "channels": 6, "tags": {"language": "eng"}, "disposition": {}},
        {"codec_type": "subtitle", "codec_name": "subrip", "tags": {"language": "fra"}, "disposition": {"forced": 1}},
    ],
    "chapters": [{"start_time": "0.000000", "tags": {"title": "Intro"}},
                 {"start_time": "65.0", "tags": {}}],
}


def labels(section):
    return dict(section.rows)


# ----------------------------------------------------------------- formats
def test_bitrate_fraction_and_seconds_formats():
    assert bitrate_text(128000) == "128 kb/s" and bitrate_text("2500000") == "2.50 Mb/s"
    assert bitrate_text(0) == "" and bitrate_text(None) == "" and bitrate_text("abc") == ""
    assert abs(fraction("30000/1001") - 29.97) < 0.01 and fraction("25") == 25.0
    assert fraction("0/0") == 0.0 and fraction(None) == 0.0 and fraction("x/y") == 0.0
    assert seconds_text("125.5") == "2:05" and seconds_text("3725") == "1:02:05"
    assert seconds_text("-1") == "" and seconds_text(None) == ""


@given(st.one_of(st.none(), st.text(max_size=12), st.integers(), st.floats(allow_nan=True, allow_infinity=True)))
def test_formatters_never_raise_on_arbitrary_input(value):
    for function in (bitrate_text, fraction, seconds_text):
        try:
            function(value)
        except OverflowError:
            pytest.fail(f"{function.__name__} a levé OverflowError pour {value!r}")


# ----------------------------------------------------------------- ffprobe (JSON simulé)
def test_sections_from_probe_cover_container_streams_chapters_and_tags():
    sections = {s.title: s for s in sections_from_probe(SAMPLE)}
    assert labels(sections["Conteneur"])["Conteneur"] == "Matroska / WebM"
    assert labels(sections["Conteneur"])["Débit total"] == "2.50 Mb/s"
    video = labels(sections["Vidéo"])                          # la pochette (attached_pic) n'est pas comptée comme vidéo
    assert video["Résolution"] == "1920×1080" and video["Images par seconde"] == "29.97"
    assert video["Profil"] == "High" and video["Format de pixel"] == "yuv420p" and video["Rotation"] == "-90°"
    assert "Langue" not in video                               # « und » = inconnu : masqué
    assert labels(sections["Audio 1"])["Canaux"] == "2 (stereo)" and labels(sections["Audio 1"])["Langue"] == "fra"
    assert labels(sections["Audio 1"])["Par défaut"] == "oui" and labels(sections["Audio 2"])["Canaux"] == "6"
    assert labels(sections["Sous-titres"])["Forcés"] == "oui"
    assert sections["Chapitres"].rows == [("0:00", "Intro"), ("1:05", "Chapitre 2")]
    assert labels(sections["Métadonnées"])["Title"] == "Mon film"


def test_sections_from_probe_survives_garbage():
    assert sections_from_probe({}) == [] or all(isinstance(s, InfoSection) for s in sections_from_probe({}))
    garbage = {"format": "x", "streams": [1, None, {"codec_type": "audio", "tags": "oops", "disposition": None}],
               "chapters": ["a", {"start_time": "nope"}]}
    try:
        sections_from_probe(garbage)
    except Exception as error:  # noqa: BLE001
        pytest.fail(f"JSON inattendu : {error!r}")


def test_probe_uses_the_runner_and_rejects_invalid_output():
    assert probe("x.mkv", runner=lambda cmd: json.dumps(SAMPLE))["format"]["format_name"] == "matroska,webm"
    assert probe("x.mkv", runner=lambda cmd: "pas du json") is None
    assert probe("x.mkv", runner=lambda cmd: "[1, 2]") is None
    seen = []
    probe("-etrange.mkv", runner=lambda cmd: seen.append(cmd) or "{}")
    assert seen[0][-2:] == ["--", "-etrange.mkv"]               # un nom commençant par « - » n'est jamais une option


def test_probe_returns_none_when_ffprobe_is_missing(monkeypatch):
    monkeypatch.setattr(mediainfo, "find_ffprobe", lambda: None)
    assert probe("x.mkv") is None


@pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="ffmpeg/ffprobe absents")
def test_real_ffprobe_on_a_generated_file(tmp_path):
    path = tmp_path / "t.mkv"
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-metadata", "title=Essai", str(path)], check=True, timeout=60)
    data = probe(path)
    assert data is not None
    sections = {s.title: s for s in sections_from_probe(data)}
    assert labels(sections["Vidéo"])["Résolution"] == "320×180" and labels(sections["Audio"])["Fréquence"] == "44100 Hz"
    assert labels(sections["Métadonnées"])["Title"] == "Essai"


# ----------------------------------------------------------------- fichier, fusion, texte, empreinte
def test_file_section_and_missing_file(tmp_path):
    path = tmp_path / "Film é.mp4"
    path.write_bytes(b"x" * 2048)
    info = labels(file_section(path))
    assert info["Nom"] == "Film é.mp4" and info["Extension"] == "mp4" and "2.0 Ko" in info["Taille"]
    assert "Modifié le" in info
    assert labels(file_section(tmp_path / "absent.mkv"))["État"] == "fichier introuvable"


def test_merge_drops_values_already_shown_and_skips_empty_result():
    base = [InfoSection("A", [("Titre", "Mon film"), ("Débit", "2 Mb/s")])]
    extra = qt_section({"Title": "Mon film", "Author": "Moi", "Vide": "  "})
    merged = merge(base, extra)
    assert merged[1].rows == [("Author", "Moi")]
    assert merge(base, qt_section({"Title": "Mon film"})) == base


def test_to_text_report():
    text = to_text("Film", [InfoSection("Fichier", [("Nom", "a.mp4")]), InfoSection("Audio", [("Codec", "aac")])])
    assert text.startswith("Film\n====\n") and "[Fichier]\nNom: a.mp4" in text and "[Audio]\nCodec: aac" in text


def test_sha256_matches_hashlib_and_supports_cancel_and_progress(tmp_path):
    import hashlib
    path = tmp_path / "gros.bin"
    path.write_bytes(b"abc" * 3_000_000)                         # 9 Mo : plusieurs blocs
    seen = []
    assert sha256_file(path, progress=lambda done, total: seen.append((done, total))) == \
        hashlib.sha256(path.read_bytes()).hexdigest()
    assert seen[-1][0] == seen[-1][1] == 9_000_000 and len(seen) >= 2
    assert sha256_file(path, cancelled=lambda: True) is None
    assert sha256_file(tmp_path / "absent.bin") is None


# ----------------------------------------------------------------- dialogue
def test_dialog_renders_all_sections_and_keeps_the_heading_first(qapp, tmp_path):
    from PySide6 import QtGui, QtWidgets
    from pyplayer.ui.dialogs import MediaInfoDialog
    path = tmp_path / "v.mp4"
    path.write_bytes(b"x")
    cover = QtGui.QImage(120, 120, QtGui.QImage.Format.Format_RGB32)
    cover.fill(QtGui.QColor("blue"))
    dialog = MediaInfoDialog([("Fichier", "v.mp4"), ("Vide", "")], "v.mp4", None,
                             sections=sections_from_probe(SAMPLE), cover=cover, path=path)
    assert dialog.findChildren(QtWidgets.QLabel)[0].text() == "v.mp4"
    html = dialog.browser.toPlainText()
    for expected in ("Résumé", "Conteneur", "Matroska / WebM", "1920×1080", "Chapitres", "Intro", "Métadonnées"):
        assert expected in html
    assert "Vide" not in html and not dialog.cover_label.isHidden() and dialog.btn_hash.isEnabled()
    assert "[Résumé]" in dialog.as_text()
    dialog.deleteLater()


def test_dialog_hash_button_computes_and_displays_the_digest(qapp, tmp_path):
    import hashlib
    from pyplayer.ui.dialogs import MediaInfoDialog
    path = tmp_path / "v.bin"
    path.write_bytes(b"contenu")
    dialog = MediaInfoDialog([("Fichier", "v.bin")], "v.bin", None, path=path)
    dialog.btn_hash.click()
    expected = hashlib.sha256(b"contenu").hexdigest()
    assert wait_until(qapp, lambda: expected in dialog.hash_label.text(), 5)
    assert expected in dialog.browser.toPlainText()               # ajouté au rapport
    dialog.deleteLater()


def test_dialog_without_path_or_cover_disables_hash_and_hides_cover(qapp):
    from pyplayer.ui.dialogs import MediaInfoDialog
    dialog = MediaInfoDialog([("Fichier", "flux")], "flux", None)
    assert not dialog.btn_hash.isEnabled() and dialog.cover_label.isHidden()
    dialog.deleteLater()
