"""Construit un binaire autonome (un seul fichier) avec Nuitka pour le système courant.

    python tools/build_nuitka.py            # -> dist/pyplayer-<version>-<linux|windows|macos>-<arch>[.exe]

Nuitka ne sait pas compiler d'un système vers un autre : le binaire Windows se construit sous Windows
(voir `.github/workflows/release.yml`, qui fait les deux).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def version() -> str:
    namespace: dict[str, str] = {}
    exec((SRC / "pyplayer" / "__init__.py").read_text(encoding="utf-8"), namespace)
    return namespace["__version__"]


def main() -> int:
    system = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}.get(platform.system(), platform.system().lower())
    arch = platform.machine().lower().replace("amd64", "x86_64")
    name = f"pyplayer-{version()}-{system}-{arch}"
    out_dir = ROOT / "dist"
    out_dir.mkdir(exist_ok=True)

    command = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--include-qt-plugins=multimedia,platforms,iconengines,imageformats,platformthemes,xcbglintegrations,tls",
        "--include-package=pyplayer",
        f"--include-data-dir={SRC / 'pyplayer' / 'resources'}=pyplayer/resources",
        "--nofollow-import-to=pytest,hypothesis,tests",
        "--output-dir=" + str(ROOT / "build" / "nuitka"),
        "--output-filename=" + name,
        "--company-name=PyPlayer",
        "--product-name=PyPlayer",
        f"--product-version={version()}",
        "--file-description=Lecteur vidéo et audio",
    ]
    if system == "windows":
        command += ["--windows-console-mode=disable",
                    f"--windows-icon-from-ico={SRC / 'pyplayer' / 'resources' / 'icons' / 'pyplayer_1.png'}"]
    elif system == "macos":
        command += ["--macos-create-app-bundle"]
    command.append(str(ROOT / "packaging" / "entry.py"))

    env = dict(os.environ, PYTHONPATH=str(SRC))
    print("→", " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env, cwd=ROOT)

    produced = ROOT / "build" / "nuitka" / (name + (".exe" if system == "windows" else ""))
    if not produced.exists():
        print(f"binaire introuvable : {produced}", file=sys.stderr)
        return 1
    target = out_dir / produced.name
    shutil.copy2(produced, target)
    print(f"OK : {target} ({target.stat().st_size / 1e6:.1f} Mo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
