# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scanner distant (lot R2) : verifier la clef de la machine, lui faire confiance (accord de la personne), scanner."""
from __future__ import annotations

from typing import Protocol

from omega_connect.domain.remote import HostCheck, RemoteFailure, RemoteScan, RemoteTarget
from omega_connect.domain.updates import RemotePlan, RemoteResult


class RemoteScanner(Protocol):
    def check_host(self, target: RemoteTarget) -> HostCheck:
        """Clef de la machine : connue, inconnue (empreintes a montrer), changee (refus), ou echec de connexion."""
        ...

    def trust(self, check: HostCheck) -> bool:
        """Ajoute la clef montree a `~/.ssh/known_hosts` ; appele seulement apres l'accord de la personne."""
        ...

    def scan(self, target: RemoteTarget) -> RemoteScan | tuple[RemoteFailure, str]:
        """Scanner envoye en memoire, lecture seule ; resultat, ou cause de l'echec et derniere ligne d'erreur."""
        ...


class RemoteSession(Protocol):
    """Lot R3 : plan calcule sur la machine (sans sudo), puis lancement dans un terminal."""

    def plan(self, target: RemoteTarget) -> RemotePlan | tuple[RemoteFailure, str]:
        ...

    def prepare(self, target: RemoteTarget, files: dict[str, bytes]) -> str | tuple[RemoteFailure, str]:
        """Envoie les fichiers dans un dossier prive de la machine ; renvoie ce dossier."""
        ...

    def run(self, target: RemoteTarget, directory: str) -> int:
        """Lance le programme dans le terminal de la personne (interface suspendue par l'appelant)."""
        ...

    def finish(self, target: RemoteTarget, directory: str) -> RemoteResult | None:
        """Relit le resultat puis efface le dossier prive."""
        ...
