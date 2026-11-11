# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrats de la detection (spec etape 3, §3.1)."""
from __future__ import annotations

from typing import Protocol

from omega_lib.synchro.models import InstallToken, ReadResult

from omega_connect.domain.detection import Candidate, ScanNote, SheetResult


class CandidateLocator(Protocol):
    """Une source de candidats : registre omega-serv, services, recherche dans un dossier, saisie."""

    def candidates(self) -> list[Candidate]:
        ...

    def notes(self) -> list[ScanNote]:
        """Remarques sur la recherche, vides si rien a signaler."""
        ...


class InstallationInspector(Protocol):
    def read_token(self, root: str) -> ReadResult[InstallToken]:
        ...

    def layout_tool(self, root: str) -> str:
        """Outil reconnu a la disposition des fichiers (lanceur + paquet), vide sinon."""
        ...

    def owner(self, root: str) -> str:
        ...

    def version(self, root: str, tool: str) -> str:
        """Version lue dans les fichiers de l'outil, sans rien executer ; vide si illisible (lot R3)."""
        ...

    def venv_ready(self, root: str) -> bool:
        """Environnement Python de l'outil present et complet (sans rien executer)."""
        ...


class SheetFetcher(Protocol):
    def fetch(self, root: str, tool: str) -> SheetResult:
        """Fiche demandee a l'outil, sous le compte proprietaire du dossier, jamais en root."""
        ...
