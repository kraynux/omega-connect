# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecriture d'un export (rapport) dans le dossier des exports d'omega-connect."""
from __future__ import annotations

from typing import Protocol


class ExportWriter(Protocol):
    def save(self, name: str, content: str) -> str:
        """Ecrit `content` sous `name` (nom de fichier seul) ; renvoie le chemin complet."""
        ...
