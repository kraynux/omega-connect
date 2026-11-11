# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage « scanner une machine distante » (lot R2). Ordre impose a toute interface :
cible saisie -> clef de la machine verifiee -> inconnue : empreintes MONTREES, accord, ajout a known_hosts ;
changee : refus -> scan en lecture seule -> registre du parc mis a jour (ou machine marquee injoignable)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from omega_connect.domain.parc import MachineEntry, entry_after_failure, entry_from_scan
from omega_connect.domain.remote import RemoteFailure, RemoteScan, RemoteTarget, Suggestion, parse_target
from omega_connect.ports.fleet import ParcStore
from omega_connect.ports.remote import RemoteScanner


@dataclass(frozen=True)
class RemoteTools:
    scanner: RemoteScanner
    parc: ParcStore
    suggest: Callable[[], tuple[Suggestion, ...]] = field(default=lambda: ())
    """Machines que cet ordinateur sait deja joindre (Unison, ~/.ssh/config, known_hosts)."""


@dataclass(frozen=True)
class RemoteOutcome:
    target: RemoteTarget
    scan: RemoteScan | None = None
    failure: RemoteFailure | None = None
    detail: str = ""
    entry: MachineEntry | None = None
    """Entree du parc ecrite (scan reussi, ou machine connue marquee injoignable)."""

    @property
    def ok(self) -> bool:
        return self.scan is not None


def scan_remote(target: RemoteTarget, tools: RemoteTools) -> RemoteOutcome:
    """A appeler une fois la clef de la machine connue (ou acceptee par la personne)."""
    result = tools.scanner.scan(target)
    machines = tools.parc.load()
    if isinstance(result, RemoteScan):
        scanned = entry_from_scan(machines, result, target)
        tools.parc.save(scanned)
        return RemoteOutcome(target, scan=result, entry=scanned)
    failure, detail = result
    marked = entry_after_failure(machines, target, failure)
    if marked is not None:
        tools.parc.save(marked)
    return RemoteOutcome(target, failure=failure, detail=detail, entry=marked)


def forget_machine(machine: MachineEntry, tools: RemoteTools) -> bool:
    """« Retirer cette machine » (demande de l'auteur : sur un grand parc, ne pas tout rescanner) : elle sort du
    registre du parc ; rien n'est modifie sur elle, et elle peut etre scannee de nouveau a tout moment."""
    return tools.parc.remove(machine.key)


def failed(target: RemoteTarget, failure: RemoteFailure, detail: str, tools: RemoteTools) -> RemoteOutcome:
    """Echec avant le scan (clef changee, machine injoignable...) : une machine deja connue est marquee."""
    entry = entry_after_failure(tools.parc.load(), target, failure)
    if entry is not None:
        tools.parc.save(entry)
    return RemoteOutcome(target, failure=failure, detail=detail, entry=entry)


def rescan_network(tools: RemoteTools) -> int:
    """Rescanne chaque machine du reseau deja connue (lecture seule) ; une machine qui ne repond plus est marquee
    injoignable. Renvoie le nombre de machines rescannees."""
    count = 0
    for machine in tools.parc.load():
        target = parse_target(machine.target) if not machine.local else None
        if target is None:
            continue
        try:
            scan_remote(target, tools)
        except Exception:  # noqa: BLE001 - une machine ne bloque jamais les autres
            continue
        count += 1
    return count
