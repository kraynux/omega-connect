# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Registre du parc (lot R1) : machines connues et resultat de leur dernier scan, sur la machine qui orchestre."""
from __future__ import annotations

from typing import Protocol

from omega_connect.domain.parc import MachineEntry


class ParcStore(Protocol):
    def load(self) -> tuple[MachineEntry, ...]: ...

    def save(self, machine: MachineEntry) -> None:
        """Remplace l'entree de cette machine (meme nom), garde les autres."""
        ...

    def remove(self, key: str) -> bool:
        """Oublie une machine distante (rien n'est touche sur la machine elle-meme) ; vrai si elle etait connue."""
        ...
