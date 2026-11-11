# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage du lot E : `reparer` (spec etape 3, §3.4).

Ordre impose a toute interface : verifier -> plan -> l'AFFICHER -> accord -> une authentification sudo (s'il y a
une etape root) -> commandes des outils une a une, arret au premier echec -> si la zone a des ecarts : nouvelle
detection, plan d'`etablir`, affiche a son tour avant tout lancement (meme flux que le lot D)."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from omega_connect.domain.links import VerificationReport
from omega_connect.domain.repair import RepairPlan, RepairStep, StepOutcome, plan_repair
from omega_connect.ports.zone import ToolRunner

RepairCallback = Callable[[int, RepairStep, StepOutcome], None]


@dataclass(frozen=True)
class RepairTools:
    runner: ToolRunner
    user: Callable[[], str]
    as_root: bool = False


def repair_plan(report: VerificationReport, tools: RepairTools) -> RepairPlan:
    return plan_repair(report, tools.user(), as_root=tools.as_root)


@dataclass(frozen=True)
class RepairResult:
    outcomes: tuple[StepOutcome, ...]

    @property
    def ok(self) -> bool:
        return all(outcome.ok for outcome in self.outcomes)

    @property
    def failed(self) -> StepOutcome | None:
        return next((outcome for outcome in self.outcomes if not outcome.ok), None)


def run_steps(steps: Sequence[RepairStep], runner: ToolRunner, on_step: RepairCallback | None = None) -> RepairResult:
    outcomes: list[StepOutcome] = []
    for index, step in enumerate(steps):
        outcome = runner.run(step)
        outcomes.append(outcome)
        if on_step is not None:
            on_step(index, step, outcome)
        if not outcome.ok:
            break
    return RepairResult(tuple(outcomes))
