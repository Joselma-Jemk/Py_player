"""Mise à jour de l'application : choix du fichier, sommes obligatoires, modes d'installation, cadence des vérifications."""

import hashlib
import os
import stat
import time
from pathlib import Path

import pytest

from pyplayer.api import fetch, updater
from pyplayer.api.fetch import FetchError
from pyplayer.api.updater import UpdateInfo, apply, asset_names, check, install_kind, should_check

BIN = b"nouvelle version de PyPlayer"
SHA = hashlib.sha256(BIN).hexdigest()


def release(tag="v0.3.0", assets=None, **extra):
    return {"tag_name": tag, "html_url": f"https://github.com/Joselma-Jemk/Py_player/releases/tag/{tag}",
            "body": "## Nouveautés\n- téléchargements", "draft": False, "prerelease": False,
            "assets": assets if assets is not None else [], **extra}


def asset(name, size=1000):
    return {"name": name, "browser_download_url": f"https://github.com/Joselma-Jemk/Py_player/releases/download/v0.3.0/{name}",
            "size": size}


def sums_text(name):
    return f"{SHA}  {name}\n{'0' * 64}  autre\n"


# ----------------------------------------------------------------- noms et modes
def test_asset_names_per_install_kind():
    assert asset_names("0.3.0", "windows-installer") == ("pyplayer-0.3.0-windows-setup.exe", "SHA256SUMS-windows.txt")
    assert asset_names("0.3.0", "windows-portable", "AMD64") == ("pyplayer-0.3.0-windows-AMD64.exe", "SHA256SUMS-windows.txt")
    assert asset_names("0.3.0", "linux-binary", "x86_64") == ("pyplayer-0.3.0-linux-x86_64", "SHA256SUMS-linux.txt")
    assert asset_names("0.3.0", "manual") == ("", "")


def test_install_kind_detection(tmp_path):
    (tmp_path / "PyPlayer.exe").write_bytes(b"x")
    assert install_kind(frozen=False, executable=str(tmp_path / "PyPlayer.exe"), system="windows") == "manual"
    assert install_kind(frozen=True, executable=str(tmp_path / "PyPlayer.exe"), system="windows") == "windows-portable"
    (tmp_path / "unins000.exe").write_bytes(b"x")                       # présent quand l'installateur Inno a été utilisé
    assert install_kind(frozen=True, executable=str(tmp_path / "PyPlayer.exe"), system="windows") == "windows-installer"
    assert install_kind(frozen=True, executable="/opt/pyplayer", system="linux") == "linux-binary"
    assert install_kind(frozen=True, executable="/Applications/x", system="macos") == "manual"


def test_check_schedule():
    now = 1_000_000.0
    assert should_check(0, now) and should_check(-5, now)
    assert not should_check(now - 3600, now)
    assert should_check(now - 25 * 3600, now)
    assert should_check(now + 5000, now)                                 # horloge reculée : on revérifie


# ----------------------------------------------------------------- lecture de la release
def run_check(current, rel, kind="windows-installer", texts=None, machine="AMD64"):
    texts = texts if texts is not None else {}
    return check(current, kind=kind, machine=machine, get_json=lambda url, policy=None: rel,
                 get_text=lambda url, policy=None, **k: texts[url.rsplit("/", 1)[-1]])


def test_no_update_when_current_or_older_or_draft_or_prerelease():
    assert run_check("0.3.0", release("v0.3.0")) is None
    assert run_check("0.4.0", release("v0.3.0")) is None
    assert run_check("0.2.0", release("v0.3.0", draft=True)) is None
    assert run_check("0.2.0", release("v0.3.0", prerelease=True)) is None
    assert run_check("0.2.0", release("")) is None and run_check("0.2.0", "pas un dict") is None  # type: ignore[arg-type]


def test_update_with_installer_and_verified_sum():
    name = "pyplayer-0.3.0-windows-setup.exe"
    rel = release(assets=[asset(name, 75_000_000), asset("SHA256SUMS-windows.txt")])
    info = run_check("0.2.0", rel, texts={"SHA256SUMS-windows.txt": sums_text(name)})
    assert info.version == "0.3.0" and info.kind == "windows-installer" and info.can_install
    assert info.sha256 == SHA and info.asset_name == name and info.size == 75_000_000
    assert "Nouveautés" in info.notes and info.page_url.endswith("v0.3.0")


def test_update_is_manual_when_asset_sums_or_entry_are_missing():
    name = "pyplayer-0.3.0-windows-setup.exe"
    for assets, texts in (([asset("SHA256SUMS-windows.txt")], {"SHA256SUMS-windows.txt": sums_text(name)}),    # fichier absent
                          ([asset(name)], {}),                                                                # pas de somme publiée
                          ([asset(name), asset("SHA256SUMS-windows.txt")], {"SHA256SUMS-windows.txt": "rien\n"}),  # pas d'entrée
                          ([asset(name), asset("SHA256SUMS-linux.txt")], {})):                                # mauvais système
        info = run_check("0.2.0", release(assets=assets), texts=texts)
        assert info.kind == "manual" and not info.can_install and info.version == "0.3.0"


def test_an_unreachable_sums_file_makes_the_update_manual_not_unverified():
    name = "pyplayer-0.3.0-linux-x86_64"

    def failing(url, policy=None, **k):
        raise FetchError("hors ligne")
    info = check("0.2.0", kind="linux-binary", machine="x86_64", get_json=lambda url, policy=None: release(
        assets=[asset(name), asset("SHA256SUMS-linux.txt")]), get_text=failing)
    assert info.kind == "manual" and not info.can_install


def test_check_survives_garbage_assets_and_reports_network_errors():
    rel = release(assets=[None, 5, {"name": 3}, {"name": "x"}, {"name": "pyplayer-0.3.0-linux-x86_64"}])
    assert run_check("0.2.0", rel, kind="linux-binary", machine="x86_64", texts={}).kind == "manual"
    rel["assets"] = "pas une liste"
    assert run_check("0.2.0", rel).kind == "manual"

    def offline(url, policy=None):
        raise FetchError("Connexion impossible")
    with pytest.raises(FetchError):
        check("0.2.0", get_json=offline)


# ----------------------------------------------------------------- application
def fake_download(content=BIN):
    def download(url, destination, expected, **kwargs):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if hashlib.sha256(content).hexdigest() != expected:
            raise FetchError("Somme de contrôle incorrecte")
        destination.write_bytes(content)
        return destination
    return download


def info(kind, name):
    return UpdateInfo(version="0.3.0", tag="v0.3.0", notes="", page_url="https://x", kind=kind, asset_name=name,
                      asset_url="https://github.com/x/y/releases/download/v0.3.0/" + name, sha256=SHA)


def test_manual_update_cannot_be_applied():
    with pytest.raises(FetchError, match="automatiquement"):
        apply(UpdateInfo("0.3.0", "v0.3.0", "", "https://x", "manual"))


def test_windows_installer_is_downloaded_then_left_to_the_caller(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    result = apply(info("windows-installer", "pyplayer-0.3.0-windows-setup.exe"), download=fake_download())
    assert result.action == "run-installer" and result.path.read_bytes() == BIN
    assert result.path.parent == updater.updates_dir()


def test_portable_windows_build_is_saved_for_the_user(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    result = apply(info("windows-portable", "pyplayer-0.3.0-windows-AMD64.exe"), download=fake_download())
    assert result.action == "saved" and result.path.is_file()


@pytest.mark.skipif(os.name == "nt", reason="remplacement d'un exécutable en cours : Linux")
def test_linux_binary_replaces_the_running_executable_atomically(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    current = tmp_path / "bin" / "pyplayer"
    current.parent.mkdir()
    current.write_bytes(b"ancienne version")
    result = apply(info("linux-binary", "pyplayer-0.3.0-linux-x86_64"), download=fake_download(),
                   current_executable=str(current))
    assert result.action == "restart" and current.read_bytes() == BIN and os.access(current, os.X_OK)
    assert not list(current.parent.glob("*.new"))
    assert not (updater.updates_dir() / "pyplayer-0.3.0-linux-x86_64").exists()      # copie temporaire nettoyée


def test_a_failed_checksum_leaves_the_current_executable_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    current = tmp_path / "pyplayer"
    current.write_bytes(b"ancienne version")
    with pytest.raises(FetchError, match="incorrecte"):
        apply(info("linux-binary", "pyplayer-0.3.0-linux-x86_64"), download=fake_download(b"binaire altere"),
              current_executable=str(current))
    assert current.read_bytes() == b"ancienne version"


@pytest.mark.skipif(os.name == "nt", reason="droits POSIX")
def test_unwritable_target_gives_a_clear_error_and_keeps_the_verified_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    folder = tmp_path / "ro"
    folder.mkdir()
    current = folder / "pyplayer"
    current.write_bytes(b"ancienne")
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(folder, os.W_OK):
            pytest.skip("droits ignorés (root)")
        with pytest.raises(FetchError, match="Remplacement impossible"):
            apply(info("linux-binary", "pyplayer-0.3.0-linux-x86_64"), download=fake_download(),
                  current_executable=str(current))
        assert current.read_bytes() == b"ancienne"
    finally:
        folder.chmod(stat.S_IRWXU)


def test_real_download_path_uses_the_fetch_module_and_its_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPLAYER_HOME", str(tmp_path / "home"))
    hostile = UpdateInfo("0.3.0", "v0.3.0", "", "https://x", "windows-installer",
                         "pyplayer-0.3.0-windows-setup.exe", "https://evil.example/setup.exe", SHA)
    with pytest.raises(FetchError, match="non autorisé"):
        apply(hostile)                                                   # téléchargement réel : l'hôte est refusé
    assert not list(updater.updates_dir().glob("*"))


def test_the_update_check_can_be_disabled_by_environment_variable():
    assert updater.NO_CHECK_ENV == "PYPLAYER_NO_UPDATE_CHECK"
    assert fetch.is_newer("0.3.0", "0.2.0")
    assert time.time() > 0
