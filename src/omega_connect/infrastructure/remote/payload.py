# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scanner envoye sur la machine distante (lot R2, decision Q2 : rien n'y est installe).

Les sources Python d'omega-connect (hors interface) et d'omega-lib sont mises dans une archive zip EN MEMOIRE,
envoyee sur l'entree de `python3 -c <amorce>` : l'amorce lit l'archive, importe les modules depuis la memoire
(aucun fichier ecrit la-bas, pas de `pip`), puis lance `omega_connect.app.remote_agent` (scan, ou plan avec
l'argument `plan`). Python 3.10 minimum.

Lancement dans un terminal (lot R3) : l'entree standard est alors celle de la personne (mot de passe sudo) ; le
meme contenu est envoye comme application zip (`agent.pyz`, avec `__main__.py`) dans un dossier prive, efface a la
fin."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import omega_lib

import omega_connect

EXCLUDED_PARTS = frozenset({"__pycache__", "locale", "tui", "report_styles", "styles"})
"""Rien d'inutile au scan : ni interface (Textual, absent la-bas), ni traductions, ni feuilles de style."""
MIN_PYTHON = (3, 10)

BOOTSTRAP = """
import sys
if sys.version_info < (3, 10):
    sys.stderr.write("omega-connect: python >= 3.10 requis\\n"); sys.exit(127)
import io, zipfile, importlib.abc, importlib.util
archive = zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()))
names = set(archive.namelist())
class InMemory(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path=None, target=None):
        base = name.replace(".", "/")
        if base + "/__init__.py" in names:
            spec = importlib.util.spec_from_loader(name, self, is_package=True, origin=base + "/__init__.py")
            spec.submodule_search_locations = [base]
            return spec
        if base + ".py" in names:
            return importlib.util.spec_from_loader(name, self, origin=base + ".py")
        return None
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        origin = module.__spec__.origin
        module.__file__ = "<omega-connect>/" + origin
        exec(compile(archive.read(origin), module.__file__, "exec"), module.__dict__)
sys.meta_path.insert(0, InMemory())
sys.stdin = open("/dev/null")
from omega_connect.app.remote_agent import main
sys.exit(main(sys.argv[1:]))
"""

ZIPAPP_MAIN = """
import sys
if sys.version_info < (3, 10):
    sys.stderr.write("omega-connect: python >= 3.10 requis\\n"); sys.exit(127)
from omega_connect.app.remote_agent import main
sys.exit(main(sys.argv[1:]))
"""


def _add_package(archive: zipfile.ZipFile, package_dir: Path) -> None:
    base = package_dir.parent
    for path in sorted(package_dir.rglob("*.py")):
        relative = path.relative_to(base)
        if EXCLUDED_PARTS.intersection(relative.parts):
            continue
        archive.writestr(relative.as_posix(), path.read_bytes())


def build_payload(*, runnable: bool = False) -> bytes:
    """`runnable` : application zip executable par `python3 agent.pyz` (lancement dans un terminal)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for package in (omega_connect, omega_lib):
            _add_package(archive, Path(package.__file__ or ".").resolve().parent)
        if runnable:
            archive.writestr("__main__.py", ZIPAPP_MAIN)
    return buffer.getvalue()
