"""Robustesse face aux pannes : coupure en pleine écriture, disque plein, fichiers corrompus, dossiers illisibles."""

import errno
import json
import os
import random
import signal
import subprocess
import sys
import textwrap
import time
import uuid
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from pyplayer.api import io_utils, paths
from pyplayer.api.manager import PlaylistManager
from pyplayer.api.playlist import Playlist

SRC = str(Path(__file__).resolve().parent.parent / "src")


# ----------------------------------------------------------------- écriture atomique : injection de pannes
@pytest.mark.parametrize("failure", ["dump", "fsync", "replace"])
def test_atomic_write_survives_failure_at_every_stage(tmp_path, monkeypatch, failure):
    target = tmp_path / "data.json"
    io_utils.write_json_atomic(target, {"version": "stable"})
    before = target.read_bytes()

    if failure == "dump":
        monkeypatch.setattr(io_utils.json, "dump", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    elif failure == "fsync":
        monkeypatch.setattr(io_utils.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(errno.EIO, "disque")))
    else:
        monkeypatch.setattr(Path, "replace", lambda self, other: (_ for _ in ()).throw(PermissionError("verrouillé")))
        monkeypatch.setattr(io_utils.time, "sleep", lambda s: None)

    with pytest.raises((RuntimeError, OSError)):
        io_utils.write_json_atomic(target, {"version": "new"})
    assert target.read_bytes() == before                            # l'ancien contenu est intact, octet pour octet
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]     # aucun fichier temporaire orphelin


def test_atomic_write_retries_transient_permission_errors(tmp_path, monkeypatch):
    target = tmp_path / "d.json"
    real_replace, calls = Path.replace, {"n": 0}

    def flaky(self, other):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise PermissionError("antivirus")
        return real_replace(self, other)

    monkeypatch.setattr(Path, "replace", flaky)
    monkeypatch.setattr(io_utils.time, "sleep", lambda s: None)
    io_utils.write_json_atomic(target, {"ok": True})
    assert json.loads(target.read_text()) == {"ok": True} and calls["n"] == 4


def test_atomic_write_unserializable_payload_leaves_everything_clean(tmp_path):
    target = tmp_path / "d.json"
    with pytest.raises(TypeError):
        io_utils.write_json_atomic(target, {"x": object()})
    assert list(tmp_path.iterdir()) == []


# ----------------------------------------------------------------- kill -9 en pleine écriture
WRITER = textwrap.dedent("""
    import sys, json
    sys.path.insert(0, {src!r})
    from pathlib import Path
    from pyplayer.api.io_utils import write_json_atomic
    target = Path(sys.argv[1])
    payload = "x" * 400_000
    i = 0
    while True:
        i += 1
        write_json_atomic(target, {{"n": i, "pad": payload, "tail": i}}, indent=None)
""")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="SIGKILL POSIX")
def test_file_is_always_valid_after_repeated_kill_9(tmp_path):
    """Un processus qui écrit en boucle est tué (SIGKILL) à des instants aléatoires : le fichier doit toujours être complet."""
    target = tmp_path / "state.json"
    script = tmp_path / "writer.py"
    script.write_text(WRITER.format(src=SRC), encoding="utf-8")
    rng = random.Random(42)
    last_n = 0
    for _ in range(30):
        process = subprocess.Popen([sys.executable, str(script), str(target)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 10
        while not target.exists() and time.time() < deadline:
            time.sleep(0.005)
        time.sleep(rng.uniform(0.0, 0.08))
        process.send_signal(signal.SIGKILL)
        process.wait()
        data = json.loads(target.read_text(encoding="utf-8"))        # jamais de JSON tronqué
        assert len(data["pad"]) == 400_000 and data["n"] == data["tail"]
        assert data["n"] >= 1
        last_n = data["n"]
    orphans = [p for p in tmp_path.iterdir() if p.name not in ("state.json", "writer.py")]
    assert all(p.name.startswith(".state.json.tmp-") for p in orphans)  # au pire des temporaires, jamais ignorés ni rechargés
    assert last_n >= 1


def test_orphan_temp_files_from_a_crash_are_ignored_by_the_manager(isolated_home):
    manager = PlaylistManager(isolated_home)
    manager.create_playlist("Vivante")
    manager.flush()
    playlists = isolated_home / "playlists"
    (playlists / ".Vivante.json.tmp-deadbeef").write_text('{"truncated":', encoding="utf-8")
    (playlists / "x.json.tmp").write_text("{", encoding="utf-8")
    reloaded = PlaylistManager(isolated_home)
    assert sorted(p.name for p in reloaded) == ["PLAYLIST", "Vivante"]


# ----------------------------------------------------------------- disque plein / dossier en lecture seule
def test_disk_full_keeps_memory_state_and_recovers_when_space_returns(isolated_home, monkeypatch, media_dir):
    folder = media_dir("m", 3)
    manager = PlaylistManager(isolated_home)
    playlist = manager.create_playlist("P", folder)
    manager.flush()
    on_disk = playlist.file_path.read_bytes()

    playlist.add(folder / "v0.mp4")  # doublon : rien
    (folder / "new.mp4").write_bytes(b"x")
    playlist.add(folder / "new.mp4")
    real_write = io_utils.write_json_atomic
    monkeypatch.setattr("pyplayer.api.manager.write_json_atomic",
                        lambda *a, **k: (_ for _ in ()).throw(OSError(errno.ENOSPC, "No space left on device")))
    assert manager.flush() is False
    assert playlist.dirty and len(playlist) == 4                      # rien n'est perdu en mémoire
    assert playlist.file_path.read_bytes() == on_disk                 # et le fichier précédent est intact

    monkeypatch.setattr("pyplayer.api.manager.write_json_atomic", real_write)
    assert manager.flush() is True and not playlist.dirty
    assert len(next(p for p in PlaylistManager(isolated_home) if p.name == "P")) == 4


def test_unwritable_data_dir_falls_back_to_temp(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.HOME_ENV_VAR, str(tmp_path / "ro"))
    real_touch = Path.touch

    def deny(self, *a, **k):
        if self.name == ".write_probe" and "ro" in self.parts:
            raise PermissionError("lecture seule")
        return real_touch(self, *a, **k)

    monkeypatch.setattr(Path, "touch", deny)
    fallback = paths.data_dir()
    assert fallback.name == "pyplayer" and "ro" not in fallback.parts and fallback.is_dir()


# ----------------------------------------------------------------- corruption chaotique des fichiers
def corrupt(data: bytes, mode: str, seed: int) -> bytes:
    rng = random.Random(seed)
    if mode == "truncate":
        return data[: rng.randint(0, max(0, len(data) - 1))]
    if mode == "flip":
        out = bytearray(data)
        for _ in range(rng.randint(1, 20)):
            if out:
                out[rng.randrange(len(out))] = rng.randrange(256)
        return bytes(out)
    if mode == "garbage":
        return bytes(rng.randrange(256) for _ in range(rng.randint(0, 600)))
    if mode == "empty":
        return b""
    if mode == "wrongtype":
        return json.dumps(rng.choice([[], 12, "text", None, {"videos": 5}, {"videos": [1, 2, None]}])).encode()
    return data


@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(mode=st.sampled_from(["truncate", "flip", "garbage", "empty", "wrongtype"]), seed=st.integers(0, 10**6),
       with_backup=st.booleans())
def test_manager_survives_any_corruption_of_any_playlist_file(tmp_path, mode, seed, with_backup):
    home = tmp_path / uuid.uuid4().hex
    folder = tmp_path / ("media" + uuid.uuid4().hex)
    folder.mkdir()
    for i in range(4):
        (folder / f"v{i}.mp4").write_bytes(b"x")
    manager = PlaylistManager(home)
    for name in ("Alpha", "Beta"):
        manager.create_playlist(name, folder)
    manager.flush()
    if with_backup:
        PlaylistManager(home)                       # prend un instantané de chaque playlist
    victims = [p.file_path for p in manager if p.name in ("Alpha", "Beta")]
    for victim in victims:
        victim.write_bytes(corrupt(victim.read_bytes(), mode, seed))

    reloaded = PlaylistManager(home)                # ne doit jamais lever
    assert len(reloaded) >= 1 and reloaded.active is not None
    for playlist in reloaded:
        assert len({v.key for v in playlist}) == len(playlist)
    names = {p.name for p in reloaded}
    for victim in victims:
        # soit la playlist est lisible/restaurée, soit le fichier est mis en quarantaine : jamais ignoré en silence
        still_there = victim.exists() and any(p.file_path == victim for p in reloaded)
        quarantined = victim.with_suffix(".corrupt").exists()
        assert still_there or quarantined or victim.exists() is False
    if with_backup:
        assert {"Alpha", "Beta"} <= names           # la sauvegarde permet de tout restaurer
    reloaded.flush()                                # et le résultat est de nouveau sauvegardable
    assert len(PlaylistManager(home)) == len(reloaded)


def test_manager_handles_a_playlist_directory_full_of_junk(isolated_home):
    playlists = isolated_home / "playlists"
    playlists.mkdir(parents=True)
    (playlists / "dir.json").mkdir()                        # un dossier qui s'appelle .json
    (playlists / "bin.json").write_bytes(os.urandom(512))
    (playlists / "emoji-😀.json").write_text("{}", encoding="utf-8")
    (playlists / "notes.txt").write_text("hello")
    manager = PlaylistManager(isolated_home)
    assert len(manager) >= 1 and manager.active is not None


def test_two_managers_on_same_dir_dont_corrupt_each_other(isolated_home, media_dir):
    folder = media_dir("m", 3)
    a = PlaylistManager(isolated_home)
    a.create_playlist("Shared", folder)
    a.flush()
    b = PlaylistManager(isolated_home)
    pa = next(p for p in a if p.name == "Shared")
    pb = next(p for p in b if p.name == "Shared")
    assert pa.id == pb.id
    pa.set_current(0)
    pb.set_current(2)
    a.flush()
    b.flush()
    final = next(p for p in PlaylistManager(isolated_home) if p.name == "Shared")
    assert final.current_index in (0, 2) and len(final) == 3         # dernier écrivain gagne, fichier valide
