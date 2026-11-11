# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage « Inscrire » (lot R1) : plan unique affiche, accord, UNE authentification (faite par l'interface
avant `run_enroll`), puis : cartes d'identite -> nouvelle detection -> espace partage recalcule et compare a ce qui
a ete annonce -> commandes root une a une (meme moteur que le lot D, arret au premier echec, registre tenu a jour)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from omega_connect.application.repair_actions import RepairCallback, RepairResult, RepairTools, run_steps
from omega_connect.application.zone_actions import ApplyResult, StepCallback, ZoneTools, apply_plan, needs_elevation
from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.enroll import EnrollPlan, plan_enroll, selection, unannounced
from omega_connect.domain.zone import Operation, ZoneFacts, ZonePlan, plan_establish


@dataclass(frozen=True)
class EnrollTools:
    zone: ZoneTools
    repair: RepairTools
    detect: Callable[[], DetectionReport]


def enroll_plan(facts: ZoneFacts, detection: DetectionReport, tools: EnrollTools,
                roots: tuple[str, ...] | None = None) -> EnrollPlan:
    return plan_enroll(detection, facts, tools.zone.subject.subject(), tools.zone.now(), user=tools.repair.user(),
                       as_root=tools.repair.as_root, roots=roots)


@dataclass(frozen=True)
class EnrollResult:
    cards: RepairResult
    space_plan: ZonePlan | None = None
    space: ApplyResult | None = None
    unannounced: tuple[Operation, ...] = ()

    @property
    def ok(self) -> bool:
        refused = self.space_plan is not None and self.space_plan.refused
        return self.cards.ok and not refused and not self.unannounced and (self.space is None or self.space.ok)


def run_enroll(plan: EnrollPlan, tools: EnrollTools, *, on_card: RepairCallback | None = None,
               on_space: StepCallback | None = None) -> EnrollResult:
    cards = run_steps(plan.cards, tools.repair.runner, on_card)
    if not cards.ok:
        return EnrollResult(cards)
    facts = tools.zone.inspector.inspect(elevated=False)
    if needs_elevation(facts):
        facts = tools.zone.inspector.inspect(elevated=True)
    detection = selection(tools.detect(), plan.roots) if plan.pending else None
    space_plan = (plan_establish(facts, detection, tools.zone.subject.subject(), tools.zone.now())
                  if detection is not None else plan.space)
    if space_plan.refused:
        return EnrollResult(cards, space_plan)
    extra = unannounced(plan, space_plan)
    if extra:
        return EnrollResult(cards, space_plan, unannounced=extra)
    if not space_plan.operations:
        return EnrollResult(cards, space_plan)
    return EnrollResult(cards, space_plan, apply_plan(space_plan, facts, tools.zone.runner, on_space))
