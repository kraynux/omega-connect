# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Registre vu par la personne (refonte du parcours, lot R1 ; ~/DEV/CONNECT/ETUDE_REFONTE_PARCOURS_OMEGA_CONNECT.md).

Trois niveaux et rien d'autre : machine -> application installee -> service (s'il y en a un). Chaque ligne a un
etat lisible, tire de la detection, de la verification et du registre de l'espace partage (zone) :

- Detectee : trouvee, sans carte d'identite (jeton) ;
- Inscrite : a sa carte, mais n'est pas (ou plus a jour) dans l'espace partage ;
- Reliee : sa carte est dans l'espace partage, a jour ;
- A corriger : un ecart qu'un outil (ou `etablir`) sait corriger la concerne ;
- Ancienne version : trop ancienne pour avoir une carte (pas de `synchro`) ;
- (Injoignable : machine distante, lot R2.)

Le vocabulaire technique (jeton, fiche, zone) reste dans « Detail » et le rapport (decision de l'auteur, Q7)."""
from __future__ import annotations

import posixpath
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from omega_lib.synchro.codec import token_to_dict
from omega_lib.synchro.models import ReadStatus
from omega_lib.synchro.registry import ZoneRegistry

from omega_connect.domain.detection import DetectedInstallation
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind, LinkState, VerificationReport
from omega_connect.domain.versions import outdated
from omega_connect.domain.zone import TOKEN_DATE_KEY, ZoneFacts, encode, read_registry, same_document

LOCAL_MACHINE = "local"


class AppState(str, Enum):
    DETECTED = "detected"
    ENROLLED = "enrolled"
    LINKED = "linked"
    TO_FIX = "to-fix"
    OLD_VERSION = "old-version"
    INCOMPLETE = "incomplete"
    """Version a jour, installation inachevee (install.sh arrete) : « Mettre a jour l'application » la reinstalle."""
    UNREACHABLE = "unreachable"


ENROLL_CODES = frozenset({
    CheckCode.TOKEN_MISSING, CheckCode.TOKEN_DAMAGED, CheckCode.TOKEN_RIGHTS, CheckCode.ZONE_NOT_LINKED,
    CheckCode.ZONE_COPY_MISSING, CheckCode.ZONE_COPY_STALE, CheckCode.ZONE_COPY_RIGHTS,
    CheckCode.ZONE_SERVICE_GROUP_MISSING,
})
"""Ecarts que « Inscrire » corrige de lui-meme : ils font l'etat Detectee / Inscrite, pas « A corriger »."""


@dataclass(frozen=True)
class RegistryRow:
    machine: str
    tool: str
    root: str
    instance: str
    """Instance ou service (vide : l'application n'a pas de service)."""
    service_state: str
    version: str
    state: AppState
    findings: tuple[tuple[Link, Check], ...] = ()
    """Ecarts qui font « A corriger » (verification)."""

    @property
    def key(self) -> str:
        return f"{self.machine}:{self.root}"


def _under(path: str, root: str) -> bool:
    path, root = posixpath.normpath(path), posixpath.normpath(root)
    return path == root or path.startswith(root.rstrip("/") + "/")


def _concerns(link: Link, check: Check, root: str) -> bool:
    if link.root:
        return _under(link.root, root)
    return bool(check.subject) and check.subject.startswith("/") and _under(check.subject, root)


def _row_findings(report: VerificationReport, root: str) -> tuple[tuple[Link, Check], ...]:
    found = []
    for link in report.links:
        for check in link.checks:
            if check.status not in (CheckStatus.WARNING, CheckStatus.FAILURE) or check.code in ENROLL_CODES:
                continue
            if (check.fix or check.repair is not None) and _concerns(link, check, root):
                found.append((link, check))
    return tuple(found)


def _instance(item: DetectedInstallation) -> tuple[str, str]:
    sheet = item.sheet.sheet if item.sheet is not None and item.sheet.status is ReadStatus.OK else None
    service = sheet.service if sheet is not None else None
    if service is not None and service.unit:
        return service.unit.removesuffix(".service"), service.state
    if sheet is not None and sheet.instance and sheet.instance != item.tool:
        return sheet.instance, ""
    if item.service_names:
        return item.service_names[0], ""
    return "", ""


def _in_shared_space(item: DetectedInstallation, registry: ZoneRegistry | None, facts: ZoneFacts | None) -> bool:
    if registry is None or facts is None or item.token is None:
        return False
    linked = registry.installation(item.installation_id)
    if linked is None:
        return False
    current = facts.contents.get(linked.token_file)
    return current is not None and same_document(current, encode(token_to_dict(item.token)), TOKEN_DATE_KEY)


def registry_rows(report: VerificationReport, facts: ZoneFacts | None,
                  machine: str = LOCAL_MACHINE) -> tuple[RegistryRow, ...]:
    """Une ligne par application installee (une instance omega-serv = une ligne)."""
    result = read_registry(facts) if facts is not None else None
    registry = result.value if result is not None else None
    rows = []
    for item in sorted(report.detection.installations, key=lambda entry: (entry.tool, entry.root)):
        if not item.tool:
            continue
        instance, service_state = _instance(item)
        version = item.token.version if item.token is not None else (
            item.sheet.sheet.version if item.sheet is not None and item.sheet.sheet is not None else item.version)
        findings = _row_findings(report, item.root)
        found = outdated(item)
        if found is not None:
            state = AppState.INCOMPLETE if found.incomplete else AppState.OLD_VERSION
        elif findings:
            state = AppState.TO_FIX
        elif item.token is None or item.token_status is not ReadStatus.OK:
            state = AppState.DETECTED
        elif _in_shared_space(item, registry, facts):
            state = AppState.LINKED
        else:
            state = AppState.ENROLLED
        rows.append(RegistryRow(machine, item.tool, item.root, instance, service_state, version, state, findings))
    return tuple(rows)


class SpaceStatus(str, Enum):
    """Pastille de l'espace partage : signale, ne demande rien."""

    NOT_PREPARED = "not-prepared"
    READY = "ready"
    TO_FIX = "to-fix"
    READ_WITH_AUTHORIZATION = "read-with-authorization"
    UNKNOWN = "unknown"


def space_status(report: VerificationReport, *, elevated: bool = False) -> SpaceStatus:
    link = next((item for item in report.links if item.kind is LinkKind.ZONE), None)
    if link is None:
        return SpaceStatus.UNKNOWN
    codes = {check.code for check in link.checks}
    if CheckCode.ZONE_ABSENT in codes:
        return SpaceStatus.NOT_PREPARED
    if link.state is LinkState.UNVERIFIABLE:
        return SpaceStatus.UNKNOWN
    if link.state is LinkState.BROKEN or any(
            check.status in (CheckStatus.WARNING, CheckStatus.FAILURE) and check.code not in ENROLL_CODES
            for check in link.checks):
        return SpaceStatus.TO_FIX
    if elevated:
        return SpaceStatus.READ_WITH_AUTHORIZATION
    return SpaceStatus.READY


def selectable(rows: Iterable[RegistryRow]) -> tuple[RegistryRow, ...]:
    """Lignes qu'« Inscrire » peut faire avancer (ni ancienne version, ni deja reliee)."""
    return tuple(row for row in rows if row.state in (AppState.DETECTED, AppState.ENROLLED, AppState.TO_FIX))



@dataclass(frozen=True)
class Todo:
    """Ce qu'il reste a faire, range par bouton (rapport ; retour de l'auteur, 2026-11-11 : une action par bouton)."""

    update: tuple[RegistryRow, ...] = ()
    """« Mettre a jour l'application » (Registre) : ancienne version ou installation inachevee."""
    sync: tuple[RegistryRow, ...] = ()
    """Synchronisation : sans carte d'identite, ou pas encore dans l'espace partage."""
    repair: tuple[RegistryRow, ...] = ()
    """Reparer : un ecart a corriger."""
    unreachable: tuple[str, ...] = ()
    """Machines qui ne repondent plus (Scanner)."""

    @property
    def empty(self) -> bool:
        return not (self.update or self.sync or self.repair or self.unreachable)


def todo(rows: Iterable[RegistryRow]) -> Todo:
    rows = tuple(rows)
    unreachable = tuple(dict.fromkeys(row.machine for row in rows if row.state is AppState.UNREACHABLE))
    return Todo(tuple(row for row in rows if row.state in (AppState.OLD_VERSION, AppState.INCOMPLETE)),
                tuple(row for row in rows if row.state in (AppState.DETECTED, AppState.ENROLLED)),
                tuple(row for row in rows if row.state is AppState.TO_FIX), unreachable)
