# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Exports dans `<omega-connect>/var/exports/` (comme le reste de la suite). Jamais un fichier a root dans le
dossier de l'utilisateur : lance sous sudo, le fichier est rendu au proprietaire du dossier (piege deja vu :
fichier root dans var/ -> l'outil ne peut plus l'ecrire ensuite)."""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from omega_connect.infrastructure.zone.system import running_as_root


class FileExportWriter:
    def __init__(self, directory: Path | Callable[[], Path]) -> None:
        """`directory` : dossier fixe, ou lu a chaque export (Reglages -> dossier des exports)."""
        self._directory = directory

    def save(self, name: str, content: str) -> str:
        if "/" in name or name.startswith("."):
            raise ValueError("export name must be a plain file name")
        directory = self._directory() if callable(self._directory) else self._directory
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(content, encoding="utf-8")
        if running_as_root():
            owner = directory.parent.stat()
            for item in (directory, path):
                os.chown(item, owner.st_uid, owner.st_gid)
        return str(path)
