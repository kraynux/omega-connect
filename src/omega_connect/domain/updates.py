# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Mise a jour des outils trop anciens d'une machine distante (lot R3 ; ETUDE_REFONTE §16) : regles pures.

Plan d'une machine = outils trop anciens (version installee, derniere version publiee sur GitHub), puis le plan de
reparation et de synchronisation calcule SUR la machine, sans sudo (texte rendu par les memes vues que la ligne de
commande). Le format echange avec le programme envoye sur la machine est versionne
(`omega-connect-plan-distant` v1, `omega-connect-maj` v1, `omega-connect-resultat-distant` v1)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from omega_connect.domain.versions import Outdated, UpdateMode, is_newer, too_old, update_mode

PLAN_FORMAT = "omega-connect-plan-distant"
UPDATES_FORMAT = "omega-connect-maj"
RESULT_FORMAT = "omega-connect-resultat-distant"
SCHEMA_VERSION = 1


class Purpose(str, Enum):
    """Ce que la personne a demande (retour de l'auteur, 2026-11-11 : « mettre a jour le registre, mettre a jour
    l'application, synchroniser l'application, c'est pas la meme chose ») : un bouton, une seule chose."""

    UPDATE = "update"
    """Mettre a jour l'application : seulement les outils trop anciens, depuis GitHub."""
    SYNC = "sync"
    """Synchroniser : reparer puis synchroniser ; jamais de mise a jour."""
    REPAIR = "repair"
    """Reparer : seulement les corrections faites par les outils eux-memes (`reparer`)."""


class ReleaseFailure(str, Enum):
    NO_RELEASE = "no-release"
    """Aucune Release publiee sur GitHub pour cet outil (ou fichier absent de la Release)."""
    NETWORK = "network"
    """GitHub injoignable depuis cet ordinateur (reseau, DNS, delai, certificat)."""
    NO_SHA = "no-sha"
    """`sha.txt` de la Release ne cite pas l'archive : refus."""
    BAD_SHA = "bad-sha"
    """Empreinte differente de `sha.txt` : archive refusee, rien n'est envoye."""
    TOO_LARGE = "too-large"
    TOO_OLD_RELEASE = "too-old-release"
    """La derniere Release publiee est elle-meme trop ancienne (pas encore de version a contrats)."""


@dataclass(frozen=True)
class ReleaseArchive:
    tool: str
    version: str
    path: str
    """Fichier local, dans un dossier prive, empreinte deja verifiee."""
    sha256: str


@dataclass(frozen=True)
class UpdateChoice:
    """Ce qui sera fait pour un outil trop ancien."""

    outdated: Outdated
    latest: str = ""
    """Derniere version publiee sur GitHub ; vide si inconnue."""
    failure: ReleaseFailure | None = None

    @property
    def possible(self) -> bool:
        return self.failure is None and bool(self.latest)

    @property
    def mode(self) -> UpdateMode:
        return update_mode(self.outdated.tool)


def choose_update(item: Outdated, latest: str | ReleaseFailure) -> UpdateChoice:
    if isinstance(latest, ReleaseFailure):
        return UpdateChoice(item, failure=latest)
    if item.incomplete:  # reinstallation : la meme version convient
        same_or_newer = not is_newer(item.version, latest)
        return UpdateChoice(item, latest) if same_or_newer and not too_old(item.tool, latest) else \
            UpdateChoice(item, latest, ReleaseFailure.TOO_OLD_RELEASE)
    if too_old(item.tool, latest) or not is_newer(latest, item.version):
        return UpdateChoice(item, latest, ReleaseFailure.TOO_OLD_RELEASE)
    return UpdateChoice(item, latest)


@dataclass(frozen=True)
class RemotePlan:
    hostname: str
    fingerprint: str
    outdated: tuple[Outdated, ...]
    repair_text: str
    """Plan de `reparer`, tel que la ligne de commande l'affiche sur la machine."""
    enroll_text: str
    """Plan de `synchroniser` (sans sudo : l'espace partage illisible sera relu avec sudo au lancement)."""
    space_unreadable: bool = False
    needs_work: bool = False
    """Quelque chose a faire (mise a jour, reparation ou synchronisation)."""
    sync_work: bool = False
    """Reparation ou synchronisation a faire (hors outils trop anciens, qui se mettent a jour a part)."""
    repair_work: bool = False
    """Une correction qu'un outil sait faire lui-meme (`reparer`)."""
    manual_commands: tuple[str, ...] = ()
    """Commandes qu'aucun outil ne sait lancer : a copier (retour de l'auteur : « on ne peut meme pas les copier »)."""


def outdated_to_list(items: tuple[Outdated, ...]) -> list[dict[str, Any]]:
    return [{"tool": item.tool, "root": item.root, "version": item.version, "minimum": item.minimum,
             "incomplete": item.incomplete} for item in items]


def outdated_from_list(raw: object) -> tuple[Outdated, ...]:
    found = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and all(isinstance(item.get(key), str) for key in ("tool", "root")):
            found.append(Outdated(item["tool"], item["root"], str(item.get("version", "")),
                                  str(item.get("minimum", "")), bool(item.get("incomplete"))))
    return tuple(found)


def plan_to_dict(plan: RemotePlan) -> dict[str, Any]:
    return {"format": PLAN_FORMAT, "schema_version": SCHEMA_VERSION, "hostname": plan.hostname,
            "machine": plan.fingerprint, "outdated": outdated_to_list(plan.outdated), "repair": plan.repair_text,
            "enroll": plan.enroll_text, "space_unreadable": plan.space_unreadable, "needs_work": plan.needs_work,
            "sync_work": plan.sync_work, "repair_work": plan.repair_work,
            "manual_commands": list(plan.manual_commands)}


def plan_from_dict(data: object) -> RemotePlan | None:
    if not isinstance(data, dict) or data.get("format") != PLAN_FORMAT:
        return None
    version = data.get("schema_version")
    if not isinstance(version, int) or version > SCHEMA_VERSION:
        return None
    hostname = data.get("hostname")
    if not isinstance(hostname, str) or not hostname:
        return None
    return RemotePlan(hostname[:64], str(data.get("machine", "")), outdated_from_list(data.get("outdated")),
                      str(data.get("repair", "")), str(data.get("enroll", "")),
                      bool(data.get("space_unreadable")), bool(data.get("needs_work")),
                      bool(data.get("sync_work", data.get("needs_work"))), bool(data.get("repair_work")),
                      tuple(str(item) for item in data.get("manual_commands") or [] if isinstance(item, str)))


# ---- mises a jour envoyees, resultat rendu --------------------------------------------------------

@dataclass(frozen=True)
class UpdateOrder:
    """Une mise a jour a faire sur la machine : l'archive envoyee dans le dossier prive de la session."""

    tool: str
    root: str
    version: str
    archive: str
    """Nom du fichier dans le dossier de la session (jamais un chemin)."""
    sha256: str
    mode: UpdateMode


def updates_to_dict(orders: tuple[UpdateOrder, ...], purpose: Purpose = Purpose.UPDATE,
                    manual: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"format": UPDATES_FORMAT, "schema_version": SCHEMA_VERSION, "purpose": purpose.value,
            "manual": list(manual),
            "updates": [{"tool": order.tool, "root": order.root, "version": order.version, "archive": order.archive,
                         "sha256": order.sha256, "mode": order.mode.value} for order in orders]}


def purpose_from_dict(data: object) -> Purpose:
    try:
        return Purpose(data.get("purpose")) if isinstance(data, dict) else Purpose.UPDATE
    except ValueError:
        return Purpose.UPDATE


def manual_from_dict(data: object) -> tuple[str, ...]:
    """Commandes « a la main » ANNONCEES a la personne (Reparer) : seules celles-ci peuvent etre lancees."""
    raw = data.get("manual") if isinstance(data, dict) else None
    return tuple(item for item in raw if isinstance(item, str) and item) if isinstance(raw, list) else ()


def updates_from_dict(data: object) -> tuple[UpdateOrder, ...] | None:
    if not isinstance(data, dict) or data.get("format") != UPDATES_FORMAT:
        return None
    orders = []
    for item in data.get("updates") or []:
        try:
            archive = str(item["archive"])
            if "/" in archive or archive.startswith("."):
                return None
            orders.append(UpdateOrder(str(item["tool"]), str(item["root"]), str(item["version"]), archive,
                                      str(item["sha256"]), UpdateMode(item["mode"])))
        except (KeyError, TypeError, ValueError):
            return None
    return tuple(orders)


class StepName(str, Enum):
    UPDATE = "update"
    REPAIR = "repair"
    ENROLL = "enroll"
    MANUAL = "manual"
    """Commande qu'aucun outil ne sait lancer, annoncee puis lancee sur la machine (Reparer)."""


@dataclass(frozen=True)
class RemoteStepResult:
    name: StepName
    code: int
    tool: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.code == 0


@dataclass(frozen=True)
class RemoteResult:
    steps: tuple[RemoteStepResult, ...]

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)


def result_to_dict(result: RemoteResult) -> dict[str, Any]:
    return {"format": RESULT_FORMAT, "schema_version": SCHEMA_VERSION,
            "steps": [{"name": step.name.value, "code": step.code, "tool": step.tool, "detail": step.detail}
                      for step in result.steps]}


def result_from_dict(data: object) -> RemoteResult | None:
    if not isinstance(data, dict) or data.get("format") != RESULT_FORMAT:
        return None
    steps = []
    for item in data.get("steps") or []:
        try:
            steps.append(RemoteStepResult(StepName(item["name"]), int(item["code"]), str(item.get("tool", "")),
                                          str(item.get("detail", ""))[:500]))
        except (KeyError, TypeError, ValueError):
            continue
    return RemoteResult(tuple(steps))
