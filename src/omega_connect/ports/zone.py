# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrats des lots D et E (spec etape 3, §3.3 a §3.5) : lire la zone, lancer une commande root, lancer la
commande d'un outil (`reparer`)."""
from __future__ import annotations

from typing import Protocol

from omega_connect.domain.repair import RepairStep, StepOutcome
from omega_connect.domain.zone import CommandOutcome, Operation, ZoneFacts, ZoneSubject


class ZoneInspector(Protocol):
    @property
    def zone_path(self) -> str: ...

    def inspect(self, *, elevated: bool) -> ZoneFacts:
        """Etat de la zone et du groupe. `elevated` : ce que la session ne peut pas lire est lu avec `sudo -n`
        (find, stat, cat : lecture seule), apres `PrivilegedRunner.authenticate()`."""
        ...


class PrivilegedRunner(Protocol):
    def authenticate(self) -> bool:
        """`sudo -v` sur le vrai terminal (mot de passe) ; vrai si root ou si l'authentification a reussi."""
        ...

    def run(self, operation: Operation) -> CommandOutcome:
        """Lance UNE commande du plan en root (`sudo -n`), jamais un shell."""
        ...


class SubjectProvider(Protocol):
    def subject(self) -> ZoneSubject: ...


class ToolRunner(Protocol):
    def run(self, step: RepairStep) -> StepOutcome:
        """Lance la commande de l'outil proprietaire (`reparer`) : lanceur verifie, jamais de shell ; en root
        (`sudo -n`, apres `PrivilegedRunner.authenticate()`) ou sous le compte proprietaire (jeton)."""
        ...
