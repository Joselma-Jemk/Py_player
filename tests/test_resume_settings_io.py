import json

import pytest

from pyplayer.api import io_utils
from pyplayer.api.resume import MAX_ENTRIES, ResumeStore
from pyplayer.api.settings import RECENT_LIMIT, Settings


# ----------------------------------------------------------------- reprise
def test_resume_returns_position_only_in_the_meaningful_window(tmp_path):
    store = ResumeStore(tmp_path / "r.json")
    f = tmp_path / "a.mp4"
    store.update(f, 2_000, 100_000)
    assert store.position(f) == 0  # trop tôt : on repart du début
    store.update(f, 40_000, 100_000)
    assert store.position(f) == 40_000
    store.update(f, 99_000, 100_000)
    assert store.position(f) == 0 and store.is_finished(f)  # audit 2.9 : plus de reprise à 99 %
    short = tmp_path / "short.mp4"
    store.update(short, 6_000, 10_000)   # média court : 60 % n'est pas « terminé »
    assert store.position(short) == 6_000
    store.update(short, 9_800, 10_000)
    assert store.is_finished(short)


def test_resume_forgets_when_user_goes_back_to_start(tmp_path):
    store = ResumeStore()
    f = tmp_path / "a.mp4"
    store.update(f, 50_000, 100_000)
    store.update(f, 1_000, 100_000)
    assert store.position(f) == 0


def test_resume_progress_and_finished(tmp_path):
    store = ResumeStore()
    f = tmp_path / "a.mp4"
    assert store.progress(f) == 0.0
    store.update(f, 25_000, 100_000)
    assert store.progress(f) == pytest.approx(0.25)
    store.mark_finished(f)
    assert store.progress(f) == 1.0 and store.position(f) == 0
    store.forget(f)
    assert store.progress(f) == 0.0


def test_resume_persists_and_ignores_corrupt_file(tmp_path):
    path = tmp_path / "r.json"
    store = ResumeStore(path)
    store.update(tmp_path / "a.mp4", 30_000, 100_000)
    assert store.save() and ResumeStore(path).position(tmp_path / "a.mp4") == 30_000
    path.write_text("{broken", encoding="utf-8")
    assert len(ResumeStore(path)) == 0


def test_resume_is_bounded(tmp_path):
    store = ResumeStore()
    for i in range(MAX_ENTRIES + 50):
        store.update(tmp_path / f"{i}.mp4", 10_000, 100_000)
    assert len(store) == MAX_ENTRIES


def test_resume_import_never_overwrites(tmp_path):
    store = ResumeStore()
    f = tmp_path / "a.mp4"
    store.update(f, 30_000, 100_000)
    from pyplayer.api.media import path_key
    store.import_position(path_key(f), 77_000)
    assert store.position(f) == 30_000


# ----------------------------------------------------------------- réglages
def test_settings_defaults_roundtrip_and_validation(tmp_path):
    path = tmp_path / "s.json"
    settings = Settings(path)
    assert settings.get("volume") == pytest.approx(0.45)
    settings.set("volume", 3.2)
    assert settings.get("volume") == 1.0
    settings.set("muted", True)
    assert settings.save() and Settings(path).get("muted") is True
    path.write_text(json.dumps({"volume": "fort", "muted": "oui", "open_siblings": False}), encoding="utf-8")
    loaded = Settings(path)
    assert loaded.get("volume") == pytest.approx(0.45)  # type invalide → défaut
    assert loaded.get("muted") is False and loaded.get("open_siblings") is False
    with pytest.raises(KeyError):
        loaded.set("inconnu", 1)


def test_settings_recent_files(tmp_path):
    settings = Settings()
    for i in range(RECENT_LIMIT + 5):
        settings.add_recent(f"/m/{i}.mp4")
    settings.add_recent("/m/10.mp4")
    recent = settings.get("recent_files")
    assert recent[0] == "/m/10.mp4" and len(recent) == RECENT_LIMIT and len(set(recent)) == RECENT_LIMIT
    settings.clear_recent()
    assert settings.get("recent_files") == []


# ----------------------------------------------------------------- écriture atomique
def test_atomic_write_creates_and_replaces(tmp_path):
    target = tmp_path / "sub" / "f.json"
    io_utils.write_json_atomic(target, {"a": 1})
    io_utils.write_json_atomic(target, {"a": 2})
    assert io_utils.read_json(target) == {"a": 2}
    assert [p.name for p in target.parent.iterdir()] == ["f.json"]


def test_atomic_write_keeps_previous_content_when_dump_fails(tmp_path):
    target = tmp_path / "f.json"
    io_utils.write_json_atomic(target, {"stable": True})

    class Boom:
        pass

    with pytest.raises(TypeError):
        io_utils.write_json_atomic(target, {"bad": Boom()})
    assert io_utils.read_json(target) == {"stable": True}
    assert [p.name for p in tmp_path.iterdir()] == ["f.json"]  # pas de fichier temporaire orphelin
