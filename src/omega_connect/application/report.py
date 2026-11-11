# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Rapport complet (menu Maintenance -> Rapport ; commande `rapport`) : tout ce qu'omega-connect sait a un instant,
en lecture seule et sans root. Refait le 2026-11-11 (retour de l'auteur : « le contenu du rapport n'est plus en
adequation avec nos changements ») : bilan de toutes les machines, ce qu'il reste a faire range par bouton, registre
(applications, versions, etats), machines du reseau, outils de cette machine (cartes d'identite, fiches), liaisons
de cette machine et de chaque machine du reseau, espace partage et son registre."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from omega_lib.synchro.models import ReadResult
from omega_lib.synchro.registry import ZoneRegistry

from omega_connect.domain.fail2ban import Presence
from omega_connect.domain.fleet import RegistryRow, registry_rows
from omega_connect.domain.links import VerificationReport
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.zone import ZoneFacts, read_registry
from omega_connect.ports.export import ExportWriter
from omega_connect.ports.fleet import ParcStore
from omega_connect.ports.zone import ZoneInspector


@dataclass(frozen=True)
class FullReport:
    version: str
    generated_at: str
    """UTC, ISO 8601 avec Z."""
    verification: VerificationReport
    zone_path: str
    zone_present: bool
    registry: ReadResult[ZoneRegistry]
    machine: str = ""
    """Cette machine (celle qui fait le rapport)."""
    rows: tuple[RegistryRow, ...] = ()
    """Registre : applications de cette machine puis de chaque machine du reseau (dernier scan)."""
    machines: tuple[MachineEntry, ...] = ()
    """Machines du reseau (registre du parc)."""


def build_report(verification: VerificationReport, zone: ZoneFacts, *, version: str, now: str, machine: str = "",
                 network: tuple[MachineEntry, ...] = ()) -> FullReport:
    remote = tuple(entry for entry in network if not entry.local)
    rows = registry_rows(verification, zone, machine or "local") + tuple(
        row for entry in remote for row in entry.shown_rows())
    return FullReport(version, now, verification, zone.path, zone.root.presence is Presence.PRESENT,
                      read_registry(zone), machine, rows, remote)


def collect_report(verification: VerificationReport, inspector: ZoneInspector, *, version: str, now: str,
                   machine: str = "", parc: ParcStore | None = None) -> FullReport:
    """La zone est lue sous le compte qui lance, jamais avec sudo : illisible = dit tel quel dans le rapport. Les
    machines du reseau : leur dernier scan (registre du parc), rien n'est relance."""
    network = parc.load() if parc is not None else ()
    return build_report(verification, inspector.inspect(elevated=False), version=version, now=now, machine=machine,
                        network=network)


@dataclass(frozen=True)
class ReportTools:
    """Ce que l'interface recoit : le rapport a l'instant (detection + verification + zone) et l'ecriture."""

    collect: Callable[[], FullReport]
    writer: ExportWriter
