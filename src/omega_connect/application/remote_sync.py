# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage « synchroniser une machine distante » (lot R3 ; ETUDE_REFONTE §16 : aucune commande a taper sur la
machine distante). Ordre impose a toute interface :

1. clef de la machine CONNUE (sinon : la scanner d'abord, la confiance s'y donne) ;
2. plan calcule SUR la machine, sans sudo : outils trop anciens, reparations, synchronisation ; pour chaque outil
   trop ancien, derniere version publiee sur GitHub ;
3. plan AFFICHE, accord de la personne ;
4. archives telechargees ici, empreinte verifiee avec `sha.txt` de la Release (rien n'est envoye sinon) ;
5. envoi dans un dossier prive de la machine, lancement dans le terminal de la personne (un mot de passe sudo pour
   la machine, tape par elle), resultat relu et dossier efface ;
6. nouveau scan de la machine : le registre montre le resultat."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from omega_connect.application.remote_actions import RemoteOutcome, RemoteTools, scan_remote
from omega_connect.domain.remote import RemoteFailure, RemoteTarget
from omega_connect.domain.updates import (
    Purpose,
    ReleaseArchive,
    ReleaseFailure,
    RemotePlan,
    RemoteResult,
    UpdateChoice,
    UpdateOrder,
    choose_update,
    updates_to_dict,
)
from omega_connect.domain.versions import archive_name
from omega_connect.ports.remote import RemoteSession
from omega_connect.ports.updates import ReleaseSource

AGENT_FILE = "agent.pyz"
UPDATES_FILE = "updates.json"


@dataclass(frozen=True)
class RemoteSyncTools:
    session: RemoteSession
    releases: ReleaseSource
    remote: RemoteTools
    payload: Callable[[], bytes]
    """Programme envoye (application zip) ; fourni par l'assemblage de l'application."""


@dataclass(frozen=True)
class MachinePlan:
    target: RemoteTarget
    plan: RemotePlan
    updates: tuple[UpdateChoice, ...]
    purpose: Purpose = Purpose.SYNC

    @property
    def needs_work(self) -> bool:
        if self.purpose is Purpose.UPDATE:
            return any(choice.possible for choice in self.updates)
        if self.purpose is Purpose.REPAIR:
            return self.plan.repair_work or bool(self.plan.manual_commands)
        return self.plan.sync_work


@dataclass(frozen=True)
class PlanFailure:
    target: RemoteTarget
    failure: RemoteFailure
    detail: str = ""


def machine_plan(target: RemoteTarget, tools: RemoteSyncTools,
                 purpose: Purpose = Purpose.SYNC) -> MachinePlan | PlanFailure:
    answer = tools.session.plan(target)
    if not isinstance(answer, RemotePlan):
        failure, detail = answer
        return PlanFailure(target, failure, detail)
    latest: dict[str, str | ReleaseFailure] = {}
    choices = []
    for item in answer.outdated if purpose is Purpose.UPDATE else ():
        if item.tool not in latest:
            latest[item.tool] = tools.releases.latest(item.tool)
        choices.append(choose_update(item, latest[item.tool]))
    return MachinePlan(target, answer, tuple(choices), purpose)


@dataclass(frozen=True)
class Prepared:
    """Fichiers envoyes ; reste a lancer dans le terminal (`run_prepared`)."""

    target: RemoteTarget
    directory: str
    orders: tuple[UpdateOrder, ...]
    refused: tuple[tuple[UpdateChoice, ReleaseFailure], ...] = ()


@dataclass(frozen=True)
class PrepareFailure:
    target: RemoteTarget
    failure: RemoteFailure | None = None
    release: tuple[tuple[UpdateChoice, ReleaseFailure], ...] = ()
    detail: str = ""


def prepare_machine(plan: MachinePlan, tools: RemoteSyncTools) -> Prepared | PrepareFailure:
    """Telecharge et verifie les archives, puis envoie tout dans un dossier prive de la machine. Une archive
    refusee (empreinte, reseau) arrete tout : rien n'est envoye, la machine n'est pas touchee."""
    archives: list[ReleaseArchive] = []
    refused: list[tuple[UpdateChoice, ReleaseFailure]] = []
    try:
        for choice in plan.updates:
            if not choice.possible:
                continue
            fetched = tools.releases.fetch(choice.outdated.tool, choice.latest)
            if isinstance(fetched, ReleaseFailure):
                refused.append((choice, fetched))
            else:
                archives.append(fetched)
        if refused:
            return PrepareFailure(plan.target, release=tuple(refused))
        orders = []
        files = {AGENT_FILE: tools.payload()}
        by_tool = {archive.tool: archive for archive in archives}
        for choice in plan.updates:
            archive = by_tool.get(choice.outdated.tool)
            if archive is None:
                continue
            name = archive_name(archive.tool, archive.version)
            files[name] = Path(archive.path).read_bytes()
            orders.append(UpdateOrder(choice.outdated.tool, choice.outdated.root, archive.version, name,
                                      archive.sha256, choice.mode))
        manual = plan.plan.manual_commands if plan.purpose is Purpose.REPAIR else ()
        files[UPDATES_FILE] = json.dumps(updates_to_dict(tuple(orders), plan.purpose, manual)).encode("utf-8")
    finally:
        for archive in archives:
            shutil.rmtree(Path(archive.path).parent, ignore_errors=True)
    sent = tools.session.prepare(plan.target, files)
    if not isinstance(sent, str):
        failure, detail = sent
        return PrepareFailure(plan.target, failure, detail=detail)
    return Prepared(plan.target, sent, tuple(orders))


def run_prepared(prepared: Prepared, tools: RemoteSyncTools) -> int:
    """A appeler interface SUSPENDUE : le programme parle a la personne dans son terminal."""
    return tools.session.run(prepared.target, prepared.directory)


@dataclass(frozen=True)
class SyncOutcome:
    target: RemoteTarget
    code: int
    result: RemoteResult | None
    rescan: RemoteOutcome | None

    @property
    def ok(self) -> bool:
        return self.code == 0 and self.result is not None and self.result.ok


def finish_machine(prepared: Prepared, code: int, tools: RemoteSyncTools) -> SyncOutcome:
    """Resultat relu, dossier efface, machine rescannee (registre du parc a jour)."""
    result = tools.session.finish(prepared.target, prepared.directory)
    rescan = scan_remote(prepared.target, tools.remote)
    return SyncOutcome(prepared.target, code, result, rescan)
