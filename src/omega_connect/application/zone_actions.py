# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage du lot D : `etablir`, `retirer --tout`, `retirer <outil>` (spec etape 3, §3.3 et §3.5).

Ordre impose a toute interface : lire la zone -> construire le plan -> l'AFFICHER -> accord -> authentification
sudo -> lancer les commandes une a une. Au premier echec, on s'arrete et le registre est reecrit pour dire ce
qui existe vraiment (une creation reussie n'est jamais oubliee : `retirer --tout` pourra la defaire)."""
from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from omega_lib.synchro.models import ReadStatus

from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.fail2ban import Presence
from omega_connect.domain.zone import (
    CommandOutcome,
    Operation,
    ZoneFacts,
    ZonePlan,
    ZoneSubject,
    plan_establish,
    plan_freeze,
    plan_remove_all,
    plan_remove_tool,
    read_registry,
    recovery_operation,
)
from omega_connect.ports.zone import PrivilegedRunner, SubjectProvider, ZoneInspector

StepCallback = Callable[[int, Operation, CommandOutcome], None]


@dataclass(frozen=True)
class ZoneTools:
    """Ce que le lot D recoit de la composition : lecture de la zone, commandes root, personne, horloge."""

    inspector: ZoneInspector
    runner: PrivilegedRunner
    subject: SubjectProvider
    now: Callable[[], str]
    as_root: bool = False
    interactive: Callable[[], bool] = field(default=lambda: sys.stdin.isatty())
    command: str = "omega-connect"
    """Commande d'omega-connect proposee dans les corrections (`<racine>/omega-connect.sh`)."""


def needs_elevation(facts: ZoneFacts) -> bool:
    """La zone existe mais la session ne peut pas la lire (pas encore membre effectif du groupe)."""
    if facts.root.presence is Presence.UNKNOWN:
        return True
    return facts.root.presence is Presence.PRESENT and facts.root.is_dir and (
        not facts.listing_known or read_registry(facts).status is ReadStatus.UNREADABLE)


@dataclass(frozen=True)
class ApplyResult:
    done: tuple[Operation, ...]
    failed: Operation | None = None
    error: str = ""
    recovery: Operation | None = None
    recovery_ok: bool = True

    @property
    def ok(self) -> bool:
        return self.failed is None


def apply_plan(plan: ZonePlan, facts: ZoneFacts, runner: PrivilegedRunner,
               on_step: StepCallback | None = None) -> ApplyResult:
    if plan.refused:
        raise ValueError("refused plan")
    done: list[Operation] = []
    for index, operation in enumerate(plan.operations):
        outcome = runner.run(operation)
        if on_step is not None:
            on_step(index, operation, outcome)
        if not outcome.ok:
            recovery = recovery_operation(plan, facts, done)
            recovered = runner.run(recovery).ok if recovery is not None else True
            return ApplyResult(tuple(done), operation, outcome.error, recovery, recovered)
        done.append(operation)
    return ApplyResult(tuple(done))


def establish_plan(facts: ZoneFacts, detection: DetectionReport, subject: ZoneSubject, now: str) -> ZonePlan:
    return plan_establish(facts, detection, subject, now)


def remove_all_plan(facts: ZoneFacts, now: str, *, keep_zone: bool,
                    detection: DetectionReport | None = None) -> ZonePlan:
    """« Garder la zone (liens figes) » ou « tout retirer » (etude, §9). `detection` : lanceur d'omega-serv qui
    retire le groupe de son service avant que le groupe disparaisse (lot E)."""
    return plan_freeze(facts, now) if keep_zone else plan_remove_all(facts, now, detection)


def remove_tool_plan(facts: ZoneFacts, detection: DetectionReport, target: str, now: str) -> ZonePlan:
    return plan_remove_tool(facts, detection, target, now)
