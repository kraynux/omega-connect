# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Archives des outils publiees (lot R3) : Releases GitHub de chaque outil."""
from __future__ import annotations

from typing import Protocol

from omega_connect.domain.updates import ReleaseArchive, ReleaseFailure


class ReleaseSource(Protocol):
    def latest(self, tool: str) -> str | ReleaseFailure:
        """Derniere version publiee."""
        ...

    def fetch(self, tool: str, version: str) -> ReleaseArchive | ReleaseFailure:
        """Archive telechargee dans un dossier prive, empreinte verifiee avec `sha.txt` de la Release."""
        ...
