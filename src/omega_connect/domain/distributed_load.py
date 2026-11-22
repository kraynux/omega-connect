# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Liaison « Charge distribuee » d'omega-stress (etude STRESS/ETUDE_PARCOURS_CHARGE_DISTRIBUEE_SIMPLE.md, lot L2,
2026-11-21). Regles pures.

Cette machine (celle d'omega-connect) PILOTE ; chaque machine du reseau ou omega-stress est installe peut AIDER.
omega-connect relie (acces cree chez le pilote, machine qui aide reliee par SSH, pare-feu du pilote) puis verifie ;
la charge passe ensuite directement entre les omega-stress, sans omega-connect. Jamais omega-connect n'ecrit les
fichiers d'omega-stress lui-meme : il lance les commandes d'omega-stress (et d'omega-fire pour le pare-feu).

Le scan distant releve l'etat de la machine qui aide (`worker etat --format json`) dans un lien brut
(STRESS_HELPER_FACTS) ; omega-connect le compose ici avec l'etat du pilote (`coordinateur etat --format json`)."""
from __future__ import annotations

import json
import shlex
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Any

from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind

if TYPE_CHECKING:
    from omega_connect.domain.fleet import RegistryRow

STRESS_TOOL = "omega-stress"
STRESS_LAUNCHER = "omega-stress.sh"


class Accord(str, Enum):
    ASK = "demander"
    """Demander pour chaque nouvelle cible."""
    ALL = "tout"
    """Tout accepter de ce pilote (parc personnel)."""


@dataclass(frozen=True)
class PilotState:
    """`coordinateur etat --format json` de cette machine."""

    root: str
    fingerprint: str
    port: int
    machines: tuple[tuple[str, str, str, str], ...]
    """(identifiant, nom, ssh, dossier) des machines qui aident."""
    firewall_backend: str = ""
    firewall_needs_opening: bool = False
    firewall_needs_omega_fire: bool = False

    def machine_for(self, ssh: str, path: str) -> str:
        return next((m[0] for m in self.machines if m[2] == ssh and m[3] == path), "")


def pilot_from_json(root: str, data: object) -> PilotState | None:
    if not isinstance(data, dict) or not isinstance(data.get("fingerprint"), str):
        return None
    machines = tuple(
        (str(m.get("id", "")), str(m.get("name", "")), str(m.get("ssh", "")), str(m.get("path", "")))
        for m in data.get("machines") or [] if isinstance(m, dict))
    raw_wall = data.get("firewall")
    wall: dict[str, Any] = raw_wall if isinstance(raw_wall, dict) else {}
    return PilotState(root, data["fingerprint"], int(data.get("port", 9650)), machines,
                      str(wall.get("backend", "")), bool(wall.get("needs_opening")),
                      bool(wall.get("needs_omega_fire")))


@dataclass(frozen=True)
class HelperFacts:
    """`worker etat --format json` d'une machine qui aide (releve par le scan distant)."""

    root: str
    readable: bool
    pilots: tuple[str, ...] = ()
    """Empreintes des pilotes acceptes."""
    accord: Accord | None = None


def helper_roots(rows: Iterable[RegistryRow]) -> dict[str, str]:
    """omega-stress de la machine qui peuvent aider (dossier -> version). L'omega-stress embarque par omega-suite
    aide comme un autonome (son lanceur prend le `.venv` et le `var/stress` de la suite ; decision de l'auteur,
    2026-11-22) ; s'il y a aussi un omega-stress autonome sur la machine, c'est lui qui aide (une seule aide)."""
    stress = [row for row in rows if row.tool == STRESS_TOOL]
    alone = [row for row in stress if not row.suite]
    return {row.root: row.version for row in (alone or stress[:1])}


def facts_link(root: str, raw: str | None, *, old_version: str = "") -> Link:
    """Lien brut ecrit par le scan distant : la sortie JSON telle quelle (ou rien si illisible) ; `old_version` :
    omega-stress trop ancien pour aider (pas lance), garde dans `instance`."""
    return Link(LinkKind.DISTRIBUTED_LOAD, old_version, root, (Check(
        CheckCode.STRESS_HELPER_FACTS, CheckStatus.INFO, root, raw or ""),))


def facts_from_link(link: Link) -> HelperFacts | None:
    check = next((c for c in link.checks if c.code is CheckCode.STRESS_HELPER_FACTS), None)
    if check is None:
        return None
    try:
        data = json.loads(check.detail) if check.detail else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return HelperFacts(link.root, False)
    authorization = data.get("authorization")
    if not isinstance(authorization, dict):
        return HelperFacts(link.root, True)
    pilots = tuple(str(p) for p in authorization.get("coordinators") or [])
    accord = Accord.ALL if authorization.get("accept_all_targets") else Accord.ASK
    return HelperFacts(link.root, True, pilots, accord)


def compose(link: Link, *, target: str, pilot: PilotState | None, machine: str, local_name: str) -> Link:
    """Liaison vue par omega-connect : la machine `machine` (joignable par `target`) aide-t-elle ce pilote ?"""
    facts = facts_from_link(link)
    if facts is None:
        return link
    base = replace(link, machine=machine, peer=local_name)
    root = facts.root
    if pilot is None:
        return replace(base, checks=(Check(CheckCode.STRESS_NO_PILOT, CheckStatus.INFO, root),))
    if not facts.readable:
        return replace(base, checks=(Check(CheckCode.STRESS_HELPER_UNREADABLE, CheckStatus.UNVERIFIABLE, root,
                                           link.instance),))
    pilot_side = bool(pilot.machine_for(target, root))
    helper_side = pilot.fingerprint in facts.pilots
    if not pilot_side and not helper_side:
        return replace(base, checks=(Check(CheckCode.STRESS_NOT_LINKED, CheckStatus.INFO, root),))
    if pilot_side != helper_side:
        side = "pilot" if pilot_side else "helper"
        return replace(base, checks=(Check(CheckCode.STRESS_HALF_LINKED, CheckStatus.FAILURE, root, side),))
    checks = [Check(CheckCode.STRESS_LINKED, CheckStatus.OK, root,
                    facts.accord.value if facts.accord else "")]
    if pilot.firewall_needs_opening:
        checks.append(Check(CheckCode.STRESS_FIREWALL_CLOSED, CheckStatus.WARNING, pilot.firewall_backend))
    elif pilot.firewall_needs_omega_fire:
        checks.append(Check(CheckCode.STRESS_NEEDS_OMEGA_FIRE, CheckStatus.WARNING, pilot.firewall_backend))
    return replace(base, checks=tuple(checks))


def compose_links(links: Iterable[Link], *, target: str, pilot: PilotState | None, machine: str,
                  local_name: str) -> tuple[Link, ...]:
    return tuple(compose(link, target=target, pilot=pilot, machine=machine, local_name=local_name)
                 if link.kind is LinkKind.DISTRIBUTED_LOAD else link for link in links)


# ---- plan « Relier la charge distribuee » -------------------------------------------------------------------

class StepWhere(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"
    ROOT = "root"
    """Sur cette machine, en root (pare-feu du pilote) : sudo -v dans le vrai terminal, puis sudo -n."""


@dataclass(frozen=True)
class Helper:
    name: str
    target: str
    """utilisateur@machine (acces SSH deja accepte dans omega-connect)."""
    root: str
    machine_id: str = ""
    """Acces deja cree chez le pilote (vide : a creer)."""


@dataclass(frozen=True)
class LinkStep:
    where: StepWhere
    helper: str
    """Nom de la machine qui aide concernee (vide : pare-feu)."""
    argv: tuple[str, ...]
    target: str = ""


def relink_plan(pilot: PilotState, helpers: Iterable[Helper], accord: Accord,
                firewall_commands: Iterable[Iterable[str]] = ()) -> tuple[LinkStep, ...]:
    """Pour chaque machine qui aide : acces cree chez le pilote (l'ancien retire), puis `worker relier` sur elle
    (le secret passe par l'entree standard du SSH, jamais en argument) ; puis le pare-feu du pilote."""
    launcher = f"{pilot.root.rstrip('/')}/{STRESS_LAUNCHER}"
    steps: list[LinkStep] = []
    for helper in helpers:
        if helper.machine_id:  # acces ancien (liaison a moitie faite) : remplace, le secret n'est jamais relu
            steps.append(LinkStep(StepWhere.LOCAL, helper.name, (
                launcher, "coordinateur", "retirer-machine", helper.machine_id)))
        steps.append(LinkStep(StepWhere.LOCAL, helper.name, (
            launcher, "coordinateur", "ajouter-machine", "--nom", helper.name, "--ssh", helper.target,
            "--chemin", helper.root, "--format", "json")))
        steps.append(LinkStep(StepWhere.REMOTE, helper.name, (
            f"{helper.root.rstrip('/')}/{STRESS_LAUNCHER}", "worker", "relier", "--pilote-adresse",
            "{adresse}", "--pilote-empreinte", pilot.fingerprint, "--id", "{id}", "--accord", accord.value),
            helper.target))
    commands = [tuple(command) for command in firewall_commands]
    for command in commands:
        steps.append(LinkStep(StepWhere.ROOT, "", command))
    if commands:
        steps.append(LinkStep(StepWhere.LOCAL, "", (launcher, "coordinateur", "pare-feu", "ouvrir", "--fait",
                                                    "--par", "omega-connect")))
    return tuple(steps)


def unlink_plan(pilot: PilotState, helper: Helper) -> tuple[LinkStep, ...]:
    launcher = f"{pilot.root.rstrip('/')}/{STRESS_LAUNCHER}"
    steps = [LinkStep(StepWhere.REMOTE, helper.name, (
        f"{helper.root.rstrip('/')}/{STRESS_LAUNCHER}", "worker", "retirer-pilote", pilot.fingerprint),
        helper.target)]
    if helper.machine_id:
        steps.append(LinkStep(StepWhere.LOCAL, helper.name, (
            launcher, "coordinateur", "retirer-machine", helper.machine_id)))
    return tuple(steps)


def shown(step: LinkStep) -> str:
    """Commande affichee dans le plan, telle qu'elle sera lancee."""
    text = shlex.join(step.argv)
    if step.where is StepWhere.REMOTE:
        return f"ssh {step.target} {text}"
    if step.where is StepWhere.ROOT:
        return f"sudo {text}"
    return text


def fill(argv: tuple[str, ...], values: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(values.get(item[1:-1], item) if item.startswith("{") and item.endswith("}") else item
                 for item in argv)


def helpers_from(links: Iterable[tuple[Link, str]]) -> list[dict[str, Any]]:
    """(liaison composee, cible SSH) -> lignes a afficher (nom, etat)."""
    return [{"machine": link.machine, "target": target, "root": link.root, "state": link.state.value}
            for link, target in links if link.kind is LinkKind.DISTRIBUTED_LOAD]
