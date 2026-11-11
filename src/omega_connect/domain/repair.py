# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""`reparer` (spec etape 3, §3.4 ; lot E) : plan des corrections, regles pures.

Principe « orchestrer, jamais ecrire a la place » : chaque ecart est corrige par la commande de l'outil qui
possede le fichier (omega-jail pour ce qu'il pose dans fail2ban, omega-serv pour les droits de son var/, chaque
outil pour son jeton), ou par `etablir` pour ce que le registre de la zone dit qu'omega-connect a cree. Rien
d'autre : un ecart sans commande proprietaire reste « a faire a la main » (commande affichee), et un outil
relie mais desinstalle reste une decision (`retirer`).

Ordre : jetons (sans root) -> droits d'omega-serv -> omega-jail (il recree aussi les journaux absents, qui
doivent alors etre partages) -> zone, dont le plan est construit APRES les etapes precedentes (un jeton cree
doit etre recopie) et affiche a son tour avant d'etre lance."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from omega_lib.synchro.constants import TOOL_LAUNCHERS

from omega_connect.domain.links import (
    JAIL_APPLY_ARGUMENTS,
    SERV_PERMISSIONS_ARGUMENTS,
    TOKEN_ARGUMENTS,
    Check,
    CheckCode,
    CheckStatus,
    Link,
    LinkKind,
    LinkState,
    Repair,
    RepairKind,
    VerificationReport,
)
from omega_connect.domain.versions import Outdated, outdated_roots

ROOT_ACCOUNT = "root"
STEP_ORDER = (RepairKind.TOKEN, RepairKind.SERV_PERMISSIONS, RepairKind.JAIL_APPLY)
DECISION_CODES = frozenset({CheckCode.ZONE_TOOL_GONE})
"""Ecarts qui demandent une decision de la personne (retirer un outil), jamais lances par `reparer`."""


@dataclass(frozen=True)
class Finding:
    """Un ecart a corriger, tel que `verifier` l'a vu."""

    link: Link
    check: Check


@dataclass(frozen=True)
class RepairStep:
    kind: RepairKind
    root: str
    tool: str
    service: str
    account: str
    """`root`, ou le compte proprietaire de l'outil (jeton)."""
    findings: tuple[Finding, ...]

    @property
    def needs_root(self) -> bool:
        return self.account == ROOT_ACCOUNT

    @property
    def launcher(self) -> str:
        return f"{self.root}/{TOOL_LAUNCHERS[self.tool]}"

    def argv(self) -> tuple[str, ...]:
        arguments: dict[RepairKind, tuple[str, ...]] = {
            RepairKind.TOKEN: TOKEN_ARGUMENTS,
            RepairKind.SERV_PERMISSIONS: (*SERV_PERMISSIONS_ARGUMENTS, self.service),
            RepairKind.JAIL_APPLY: JAIL_APPLY_ARGUMENTS,
        }
        return (self.launcher, *arguments[self.kind])


@dataclass(frozen=True)
class Skipped:
    """Etape impossible depuis cette session (jeton d'un autre compte, sans root)."""

    step: RepairStep
    reason: str


@dataclass(frozen=True)
class RepairPlan:
    steps: tuple[RepairStep, ...] = ()
    zone: tuple[Finding, ...] = ()
    """Ecarts de la zone : `etablir` les corrige, son plan est propose apres les etapes."""
    manual: tuple[Finding, ...] = ()
    """Ecarts sans commande proprietaire : commande affichee, a lancer a la main."""
    decisions: tuple[Finding, ...] = ()
    skipped: tuple[Skipped, ...] = ()
    relink: bool = False
    """La zone existe et des jetons vont etre crees ou mis a jour : `etablir` est propose ensuite pour les relier
    au registre, meme si la zone est « non verifiable » (avant reconnexion ; retour de l'auteur, 2026-11-10)."""
    zone_unreadable: bool = False
    outdated: tuple[Outdated, ...] = ()
    """Outils trop anciens (lot R3) : aucune de leurs commandes n'est lancee, ils sont a mettre a jour d'abord."""
    """La zone existe mais la session ne peut pas la lire (avant reconnexion) : on ne sait pas si tout est relie,
    `etablir` est propose (il la lit avec sudo et ne fait que ce qui manque)."""

    @property
    def offers_zone(self) -> bool:
        return bool(self.zone) or self.relink or self.zone_unreadable

    @property
    def needs_root(self) -> bool:
        return any(step.needs_root for step in self.steps)

    @property
    def empty(self) -> bool:
        return not (self.steps or self.zone or self.manual or self.decisions or self.skipped or self.offers_zone
                    or self.outdated)


def _to_fix(check: Check) -> bool:
    return check.status in (CheckStatus.WARNING, CheckStatus.FAILURE)


def findings(report: VerificationReport) -> Iterable[Finding]:
    for link in report.links:
        for check in link.checks:
            if _to_fix(check):
                yield Finding(link, check)


def _owner(report: VerificationReport, root: str) -> str:
    for item in report.detection.installations:
        if item.root == root:
            return item.owner
    return ""


def plan_repair(report: VerificationReport, user: str, *, as_root: bool) -> RepairPlan:
    """`user` : compte qui lance omega-connect (`SUDO_USER` sous sudo) ; un jeton se cree sous le compte
    proprietaire de l'outil : le meme, ou n'importe lequel si omega-connect tourne en root (runuser)."""
    grouped: dict[tuple[RepairKind, str, str], list[Finding]] = {}
    key: tuple[RepairKind, str, str]
    repairs: dict[tuple[RepairKind, str, str], Repair] = {}
    zone: list[Finding] = []
    manual: list[Finding] = []
    decisions: list[Finding] = []
    for finding in findings(report):
        check = finding.check
        repair = check.repair
        if check.code in DECISION_CODES:
            decisions.append(finding)
        elif repair is None:
            if check.fix:
                manual.append(finding)
        elif repair.kind is RepairKind.ZONE:
            zone.append(finding)
        else:
            key = (repair.kind, repair.root, repair.service)
            grouped.setdefault(key, []).append(finding)
            repairs.setdefault(key, repair)
    steps: list[RepairStep] = []
    skipped: list[Skipped] = []
    for key in sorted(grouped, key=lambda item: (STEP_ORDER.index(item[0]), item[1], item[2])):
        repair = repairs[key]
        if repair.kind is RepairKind.TOKEN:
            owner = _owner(report, repair.root)
            step = RepairStep(repair.kind, repair.root, repair.tool, repair.service, owner or "?",
                              tuple(grouped[key]))
            if not owner or (owner != user and not as_root):
                skipped.append(Skipped(step, "another-account"))
                continue
        else:
            step = RepairStep(repair.kind, repair.root, repair.tool, repair.service, ROOT_ACCOUNT,
                              tuple(grouped[key]))
        steps.append(step)
    zone_exists = any(link.kind is LinkKind.ZONE and link.checks and
                      all(check.code is not CheckCode.ZONE_ABSENT for check in link.checks)
                      for link in report.links)
    relink = zone_exists and any(step.kind is RepairKind.TOKEN for step in steps)
    unreadable = any(link.kind is LinkKind.ZONE and link.state is LinkState.UNVERIFIABLE for link in report.links)
    old = outdated_roots(report.detection.installations)
    steps = [step for step in steps if step.root not in old]
    return RepairPlan(tuple(steps), tuple(zone), tuple(manual), tuple(decisions), tuple(skipped), relink,
                      unreadable, tuple(old[root] for root in sorted(old)))


@dataclass(frozen=True)
class StepOutcome:
    step: RepairStep
    code: int
    error: str = ""
    """Derniere ligne d'erreur de l'outil (texte de l'outil, jamais traduit)."""

    @property
    def ok(self) -> bool:
        return self.code == 0
