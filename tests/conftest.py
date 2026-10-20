import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.*=false;qt.qpa.*=false")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hypothesis import HealthCheck, settings  # noqa: E402

# Profils Hypothesis : « ci » (par défaut, rapide) et « thorough » (PYPLAYER_THOROUGH=1, ~10× plus d'exemples).
settings.register_profile("ci", max_examples=120, deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("thorough", max_examples=1500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("thorough" if os.environ.get("PYPLAYER_THOROUGH") else "ci")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Aucun test ne doit jamais lire ni écrire le vrai ~/.pyplayer de l'utilisateur."""
    home = tmp_path / "_isolated_home"
    monkeypatch.setenv("PYPLAYER_HOME", str(home))
    monkeypatch.setenv("HOME", str(tmp_path / "_userhome"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "_userhome"))
    yield home


@pytest.fixture
def media_dir(tmp_path):
    """Dossier avec des faux fichiers média (le contenu n'est pas décodé par l'API)."""
    def make(subdir: str, count: int, prefix: str = "v", ext: str = ".mp4") -> Path:
        folder = tmp_path / subdir
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            (folder / f"{prefix}{i}{ext}").write_bytes(b"x")
        return folder
    return make


@pytest.fixture
def data_home(isolated_home):
    return isolated_home
