# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""« Inscrire » (refonte du parcours, lot R1, decision Q5 de l'auteur) : UNE action par machine, UN plan, UN mot de
passe. Elle cree les cartes d'identite qui manquent (commande de chaque outil, sous son compte), prepare l'espace
partage (groupe, dossiers, vous ajouter), y recopie les cartes et donne l'acces aux services (plan d'`etablir`).

Les cartes creees a l'etape 1 n'existent pas encore quand le plan est affiche : il annonce leur copie, sans pouvoir
montrer leur contenu. Apres l'etape 1, le plan de l'espace partage est recalcule ; une commande qui n'etait pas
annoncee n'est jamais lancee (`unannounced`) : arret, et nouveau plan a afficher."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from omega_lib.synchro.constants import TOOL_LAUNCHERS
from omega_lib.synchro.models import ReadStatus

from omega_connect.domain.detection import DetectedInstallation, DetectionReport
from omega_connect.domain.links import RepairKind
from omega_connect.domain.repair import ROOT_ACCOUNT, RepairStep, Skipped
from omega_connect.domain.versions import outdated
from omega_connect.domain.zone import (
    FileRole,
    Operation,
    OperationKind,
    ZoneFacts,
    ZonePlan,
    ZoneSubject,
    plan_establish,
)


@dataclass(frozen=True)
class EnrollPlan:
    roots: tuple[str, ...]
    """Applications choisies (racines) ; toutes celles de la machine pour « Inscrire tout »."""
    cards: tuple[RepairStep, ...]
    """Etape 1 : cartes d'identite a creer (commande de l'outil, sous son compte, sans root)."""
    space: ZonePlan
    """Etape 2 : espace partage, calcule avec ce qui existe aujourd'hui."""
    pending: tuple[str, ...]
    """Racines dont la carte, creee a l'etape 1, sera recopiee a l'etape 2."""
    skipped: tuple[Skipped, ...] = ()

    @property
    def needs_root(self) -> bool:
        return bool(self.space.operations) or bool(self.pending)

    @property
    def empty(self) -> bool:
        return not self.cards and not self.space.operations and not self.pending


def _too_old(item: DetectedInstallation) -> bool:
    """Un outil trop ancien ne connait pas `synchro jeton` : il est mis a jour d'abord (lot R3)."""
    return outdated(item) is not None


def selection(detection: DetectionReport, roots: Iterable[str] | None) -> DetectionReport:
    """Detection reduite aux applications choisies (None : toutes)."""
    wanted = None if roots is None else set(roots)
    kept = tuple(item for item in detection.installations
                 if item.tool and (wanted is None or item.root in wanted))
    return DetectionReport(detection.home, kept, detection.duplicates, detection.scan_notes)


def plan_enroll(detection: DetectionReport, facts: ZoneFacts, subject: ZoneSubject, now: str, *, user: str,
                as_root: bool, roots: Iterable[str] | None = None) -> EnrollPlan:
    chosen = selection(detection, roots)
    cards: list[RepairStep] = []
    skipped: list[Skipped] = []
    for item in chosen.installations:
        if item.token_status is ReadStatus.OK or item.tool not in TOOL_LAUNCHERS or _too_old(item):
            continue
        step = RepairStep(RepairKind.TOKEN, item.root, item.tool, "", item.owner or "?", ())
        if not item.owner or item.owner == ROOT_ACCOUNT or (item.owner != user and not as_root):
            skipped.append(Skipped(step, "another-account"))
        else:
            cards.append(step)
    space = plan_establish(facts, chosen, subject, now)
    return EnrollPlan(tuple(item.root for item in chosen.installations), tuple(cards), space,
                      tuple(step.root for step in cards), tuple(skipped))


def unannounced(plan: EnrollPlan, actual: ZonePlan) -> tuple[Operation, ...]:
    """Commandes du plan recalcule qui n'etaient pas annoncees : jamais lancees."""
    announced = {(operation.kind, operation.target) for operation in plan.space.operations}
    pending = set(plan.pending)
    extra = []
    for operation in actual.operations:
        if (operation.kind, operation.target) in announced:
            continue
        if operation.kind is OperationKind.WRITE_FILE and operation.role is FileRole.REGISTRY:
            continue
        if operation.kind is OperationKind.WRITE_FILE and operation.role in (FileRole.TOKEN_COPY,
                                                                              FileRole.SHEET_COPY) \
                and operation.subject in pending:
            continue
        extra.append(operation)
    return tuple(extra)
