"""Test de mutation maison : modifie le code de ``pyplayer.api`` (opérateurs, constantes, retours, instructions)
et vérifie que la suite de tests ÉCHOUE. Un mutant « survivant » = un comportement que les tests ne protègent pas.

    python tools/mutation_check.py --sample 60 --seed 1 [--files playlist.py resume.py]

Résultat : score de mutation (mutants tués / mutants testés) et liste des survivants.
"""

from __future__ import annotations

import argparse
import ast
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DEFAULT_FILES = ["playlist.py", "resume.py", "media.py", "settings.py", "manager.py", "m3u.py", "subtitles.py", "video.py"]
FAST_TESTS = ["tests/test_media.py", "tests/test_playlist.py", "tests/test_manager.py", "tests/test_resume_settings_io.py",
              "tests/test_m3u.py", "tests/test_property_playlist.py", "tests/test_property_misc.py",
              "tests/test_legacy_migration.py", "tests/test_crash_safety.py", "tests/test_mutation_gaps.py"]

CMP_SWAP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE,
            ast.GtE: ast.Gt, ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In}
BIN_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult}


class Site:
    def __init__(self, kind: str, lineno: int, apply):
        self.kind, self.lineno, self.apply = kind, lineno, apply


def collect_sites(tree: ast.Module) -> list[Site]:
    sites: list[Site] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in CMP_SWAP:
                    sites.append(Site(f"cmp {type(op).__name__}->{CMP_SWAP[type(op)].__name__}", line,
                                      lambda n=node, i=i: n.ops.__setitem__(i, CMP_SWAP[type(n.ops[i])]())))
        elif isinstance(node, ast.BoolOp):
            sites.append(Site("and<->or", line, lambda n=node: setattr(n, "op", ast.Or() if isinstance(n.op, ast.And) else ast.And())))
        elif isinstance(node, ast.BinOp) and type(node.op) in BIN_SWAP:
            sites.append(Site(f"arith {type(node.op).__name__}", line, lambda n=node: setattr(n, "op", BIN_SWAP[type(n.op)]())))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            sites.append(Site("not removed", line, lambda n=node: _replace(tree, n, n.operand)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append(Site("bool flip", line, lambda n=node: setattr(n, "value", not n.value)))
        elif isinstance(node, ast.Constant) and type(node.value) is int and node.value not in (0,):
            sites.append(Site("int +1", line, lambda n=node: setattr(n, "value", n.value + 1)))
        elif isinstance(node, ast.If):
            sites.append(Site("if negated", line, lambda n=node: setattr(n, "test", ast.UnaryOp(op=ast.Not(), operand=n.test))))
        elif isinstance(node, ast.Return) and node.value is not None and not (
                isinstance(node.value, ast.Constant) and node.value.value is None):
            sites.append(Site("return None", line, lambda n=node: setattr(n, "value", ast.Constant(value=None))))
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and not isinstance(node.value.func, ast.Name):
            sites.append(Site("statement removed", line, lambda n=node: _replace_stmt(tree, n)))
    return sites


def _replace(tree, old, new):
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if value is old:
                setattr(parent, field, new)
                return
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if item is old:
                        value[i] = new
                        return


def _replace_stmt(tree, stmt):
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if isinstance(value, list) and stmt in value:
                i = value.index(stmt)
                value[i] = ast.Pass()
                return


def run_tests(mutated_src: Path, workdir: Path, timeout: int) -> tuple[bool, str]:
    """Lance la suite rapide contre ``mutated_src``. Retourne (réussie ?, sortie)."""
    env = {"PYTHONPATH": str(mutated_src), "PATH": "/usr/bin:/usr/local/bin", "HOME": str(workdir),
           "QT_QPA_PLATFORM": "offscreen", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:logging", "-p", "no:cacheprovider",
             "-k", "not kill_9", "--no-header", "-o", "pythonpath=", *FAST_TESTS],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "timeout"


def imported_from(mutated_src: Path, workdir: Path) -> str:
    """Chemin réellement utilisé par pytest pour ``pyplayer`` (conftest compris) : doit être la copie mutée."""
    env = {"PYTHONPATH": str(mutated_src), "PATH": "/usr/bin:/usr/local/bin", "HOME": str(workdir),
           "QT_QPA_PLATFORM": "offscreen"}
    probe = ROOT / "tests" / "_probe_import_test.py"
    probe.write_text("def test_where():\n    import pyplayer\n    print('PYPLAYER_FILE=' + pyplayer.__file__)\n", encoding="utf-8")
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-s", "-p", "no:logging", "-p", "no:cacheprovider",
                                 "-o", "pythonpath=", str(probe)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    finally:
        probe.unlink(missing_ok=True)
    for line in result.stdout.splitlines():
        if line.startswith("PYPLAYER_FILE="):
            return line.split("=", 1)[1]
    return ""


def self_check(workdir: Path, timeout: int) -> None:
    """Le harnais doit : (1) importer la copie mutée, (2) réussir sur le code intact, (3) échouer sur un mutant évident."""
    mutated_src = workdir / "src"
    shutil.copytree(SRC, mutated_src, ignore=shutil.ignore_patterns("__pycache__", "resources"))
    (mutated_src / "pyplayer" / "resources").symlink_to(SRC / "pyplayer" / "resources")
    where = imported_from(mutated_src, workdir)
    if not where.startswith(str(mutated_src)):
        raise SystemExit(f"HARNAIS INVALIDE : pyplayer est importé depuis {where!r} et non depuis la copie mutée")
    ok, output = run_tests(mutated_src, workdir, timeout)
    if not ok:
        raise SystemExit("HARNAIS INVALIDE : la suite échoue sur le code NON muté :\n" + output[-1500:])
    canary = mutated_src / "pyplayer" / "api" / "playlist.py"
    canary.write_text(canary.read_text(encoding="utf-8").replace("return len(self.videos)", "return 0", 1), encoding="utf-8")
    ok, _ = run_tests(mutated_src, workdir, timeout)
    if ok:
        raise SystemExit("HARNAIS INVALIDE : un mutant évident (len() == 0) n'est pas détecté")
    shutil.rmtree(mutated_src)
    print("auto-contrôle du harnais OK : copie mutée importée, code intact réussi, canari tué", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=60)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--files", nargs="*", default=DEFAULT_FILES)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    all_mutants: list[tuple[str, int]] = []
    for name in args.files:
        tree = ast.parse((SRC / "pyplayer" / "api" / name).read_text(encoding="utf-8"))
        all_mutants += [(name, i) for i in range(len(collect_sites(tree)))]
    chosen = rng.sample(all_mutants, min(args.sample, len(all_mutants)))
    print(f"{len(all_mutants)} mutants possibles, {len(chosen)} testés")

    killed, survived = 0, []
    workdir = Path(tempfile.mkdtemp(prefix="mutants_"))
    try:
        self_check(workdir, args.timeout)
        for n, (name, index) in enumerate(chosen, 1):
            path = SRC / "pyplayer" / "api" / name
            tree = ast.parse(path.read_text(encoding="utf-8"))
            sites = collect_sites(tree)
            site = sites[index]
            site.apply()
            ast.fix_missing_locations(tree)
            mutated_src = workdir / "src"
            if mutated_src.exists():
                shutil.rmtree(mutated_src)
            shutil.copytree(SRC, mutated_src, ignore=shutil.ignore_patterns("__pycache__", "resources"))
            (mutated_src / "pyplayer" / "resources").symlink_to(SRC / "pyplayer" / "resources")
            (mutated_src / "pyplayer" / "api" / name).write_text(ast.unparse(tree), encoding="utf-8")
            start = time.time()
            passed, _output = run_tests(mutated_src, workdir, args.timeout)
            dead = not passed                       # échec OU blocage = mutant détecté
            status = "TUÉ     " if dead else "SURVIVANT"
            killed += dead
            if not dead:
                survived.append(f"{name}:{site.lineno}  {site.kind}")
            print(f"[{n:3d}/{len(chosen)}] {status} {name}:{site.lineno:<4d} {site.kind:<22s} ({time.time() - start:.1f}s)", flush=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    score = 100 * killed / max(1, len(chosen))
    print(f"\nScore de mutation : {killed}/{len(chosen)} = {score:.0f} %")
    if survived:
        print("Survivants :")
        for line in survived:
            print("  -", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
