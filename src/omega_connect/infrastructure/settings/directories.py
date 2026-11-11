# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Vider le dossier des exports ou des captures (Reglages) : copie de la regle d'omega-serv
(`application/terminal/clear_directory.py`, correctif de la suite du 2026-10-27).

- le dossier CONFIGURE, son CONTENU seulement (le dossier reste) ; un lien symbolique est supprime sans suivre sa
  cible ;
- dossiers systeme, personnels, le projet et ses parents refuses : le champ est libre ;
- un element qui resiste est signale, jamais retente avec sudo."""
from __future__ import annotations

import shutil
from pathlib import Path

from omega_connect.application.settings import ClearResult, UnsafeDirectoryError
from omega_connect.shared.i18n import _

SYSTEM_DIRS = frozenset(Path(p) for p in (
    "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32", "/lib64", "/media", "/mnt",
    "/opt", "/proc", "/root", "/run", "/sbin", "/srv", "/sys", "/tmp", "/usr", "/var",
    "/var/lib", "/var/log", "/usr/local",
))


def check_clearable(directory: Path, project_root: Path) -> Path:
    target = directory.resolve()
    project = project_root.resolve()
    if target in SYSTEM_DIRS or target.parent == Path("/home") or target == Path.home().resolve():
        raise UnsafeDirectoryError(str(target), _("dossier système ou personnel"))
    if target == project or target in project.parents:
        raise UnsafeDirectoryError(str(target), _("contient l'installation d'omega-connect"))
    if target.exists() and not target.is_dir():
        raise UnsafeDirectoryError(str(target), _("ce n'est pas un dossier"))
    return target


def clear_directory(directory: Path, project_root: Path) -> ClearResult:
    target = check_clearable(directory, project_root)
    target.mkdir(parents=True, exist_ok=True)
    removed = 0
    failed: list[str] = []
    for entry in sorted(target.iterdir()):
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        except OSError as exc:
            failed.append(f"{entry.name} ({exc.strerror or exc})")
        else:
            removed += 1
    return ClearResult(target, removed, tuple(failed))
