# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Registre du parc (`var/parc.json`, sur la machine qui orchestre ; decision Q3 de la refonte) : chaque machine
connue, son identite (empreinte), ses adresses, le resultat de son dernier scan, et si elle repond encore.

Une machine se reconnait a son empreinte, jamais a son adresse (lot R2, reponse a l'auteur) : scannee par
`192.168.1.109` puis par `100.64.0.9`, hpc-109 reste UNE machine aux deux adresses."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from omega_connect.domain.fleet import AppState, RegistryRow
from omega_connect.domain.links import Link
from omega_connect.domain.remote import (
    RemoteFailure,
    RemoteScan,
    RemoteTarget,
    links_from_list,
    links_to_list,
    rows_from_list,
    rows_to_list,
)

PARC_FORMAT = "omega-connect-parc"
PARC_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MachineEntry:
    """Une machine du parc et le resultat de son dernier scan."""

    name: str
    local: bool
    scanned_at: str
    rows: tuple[RegistryRow, ...] = ()
    fingerprint: str = ""
    addresses: tuple[str, ...] = ()
    """Adresses ou noms saisis pour la joindre (machine distante)."""
    target: str = ""
    """Derniere cible SSH utilisee (`utilisateur@adresse`)."""
    reachable: bool = True
    links: tuple[Link, ...] = ()
    last_error: str = ""
    """Cause du dernier echec (`RemoteFailure`) ; vide si le dernier scan a reussi."""

    @property
    def key(self) -> str:
        return self.fingerprint or self.name

    @property
    def label(self) -> str:
        """`hpc-109 (192.168.1.109, 100.64.0.9)` ; la machine locale : son nom seul."""
        shown = [address for address in self.addresses if address != self.name]
        return f"{self.name} ({', '.join(shown)})" if shown else self.name

    def shown_rows(self) -> tuple[RegistryRow, ...]:
        """Lignes affichees : une machine qui ne repond plus garde ses lignes, en « Injoignable »."""
        rows = tuple(replace(row, machine=self.label) for row in self.rows)
        if self.reachable:
            return rows
        return tuple(replace(row, state=AppState.UNREACHABLE, findings=()) for row in rows)


def find_machine(machines: Iterable[MachineEntry], *, fingerprint: str = "", address: str = "") -> MachineEntry | None:
    for machine in machines:
        if fingerprint and machine.fingerprint == fingerprint:
            return machine
    for machine in machines:
        if address and address in machine.addresses:
            return machine
    return None


def match_machine(machines: Iterable[MachineEntry], text: str) -> MachineEntry | None:
    """Machine distante designee par son nom, une de ses adresses, sa cible (`utilisateur@adresse`) ou son empreinte."""
    wanted = text.strip()
    host = wanted.rpartition("@")[2]
    for machine in machines:
        if machine.local:
            continue
        if wanted in (machine.name, machine.target, machine.fingerprint) or host in machine.addresses:
            return machine
    return None


def entry_from_scan(machines: Iterable[MachineEntry], scan: RemoteScan, target: RemoteTarget) -> MachineEntry:
    """Nouvelle entree (ou entree mise a jour) apres un scan distant reussi ; adresses cumulees."""
    # Empreinte connue : elle seule decide (deux machines de meme adresse sur deux reseaux restent deux).
    known = (find_machine(tuple(machines), fingerprint=scan.fingerprint) if scan.fingerprint
             else find_machine(tuple(machines), address=target.host))
    addresses = tuple(dict.fromkeys([*(known.addresses if known is not None else ()), target.host]))
    return MachineEntry(scan.hostname, False, scan.scanned_at, scan.rows, scan.fingerprint, addresses, target.text,
                        True, scan.links)


def entry_after_failure(machines: Iterable[MachineEntry], target: RemoteTarget,
                        failure: RemoteFailure) -> MachineEntry | None:
    """Machine deja connue qui ne repond pas : ses lignes restent, marquees injoignables. Inconnue : None."""
    known = find_machine(tuple(machines), address=target.host)
    if known is None or known.local:
        return None
    gone = failure in (RemoteFailure.UNREACHABLE, RemoteFailure.NO_SSH_SERVER, RemoteFailure.UNKNOWN_NAME)
    return replace(known, reachable=not gone and known.reachable, last_error=failure.value)


def parc_to_dict(machines: Iterable[MachineEntry]) -> dict[str, object]:
    return {
        "format": PARC_FORMAT, "schema_version": PARC_SCHEMA_VERSION,
        "machines": [{
            "name": machine.name, "local": machine.local, "scanned_at": machine.scanned_at,
            "fingerprint": machine.fingerprint, "addresses": list(machine.addresses), "target": machine.target,
            "reachable": machine.reachable, "last_error": machine.last_error,
            "applications": rows_to_list(machine.rows), "links": links_to_list(machine.links),
        } for machine in machines],
    }


def parc_from_dict(data: object) -> tuple[MachineEntry, ...]:
    """Lecture tolerante : une entree abimee est ignoree (le parc se reconstruit au prochain scan)."""
    if not isinstance(data, dict) or data.get("format") != PARC_FORMAT:
        return ()
    machines = []
    for raw in data.get("machines") or []:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            continue
        name = raw["name"]
        addresses = raw.get("addresses")
        machines.append(MachineEntry(
            name, bool(raw.get("local")), str(raw.get("scanned_at", "")), rows_from_list(raw.get("applications"), name),
            str(raw.get("fingerprint", "")),
            tuple(str(item) for item in addresses) if isinstance(addresses, list) else (),
            str(raw.get("target", "")), bool(raw.get("reachable", True)),
            links_from_list(raw.get("links"), "" if raw.get("local") else name), str(raw.get("last_error", ""))))
    return tuple(machines)
