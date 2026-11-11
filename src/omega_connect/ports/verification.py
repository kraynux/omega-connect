# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrats de `verifier` (spec etape 3, §3.2) : lecture seule, sans root."""
from __future__ import annotations

from typing import Protocol

from omega_connect.domain.fail2ban import Fail2banSnapshot, FileFacts


class Fail2banReader(Protocol):
    def read(self) -> Fail2banSnapshot:
        """Fichiers d'omega-jail dans fail2ban (jail.d, filter.d, action.d), texte et droits."""
        ...


class FileProbe(Protocol):
    def facts(self, path: str) -> FileFacts:
        """Existence, proprietaire, groupe et droits d'un fichier (stat sans suivre de lien), jamais son contenu."""
        ...
