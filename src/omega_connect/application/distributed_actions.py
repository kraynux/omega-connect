# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage « Relier la charge distribuee » / « Delier » (lot L2, 2026-11-21).

Ordre impose a toute interface : plan calcule et AFFICHE -> accord de la personne -> pour chaque machine qui aide :
acces cree chez le pilote, puis `worker relier` sur elle par SSH (secret par l'entree standard) -> pare-feu du pilote
(un seul mot de passe sudo, saisi dans le vrai terminal ; jamais de sudo sans terminal) -> machines rescannees pour
que Liaisons montre l'etat reel. Une machine en echec n'arrete pas les autres."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from omega_connect.domain.distributed_load import (
    STRESS_LAUNCHER,
    Accord,
    Helper,
    LinkStep,
    PilotState,
    StepWhere,
    fill,
    relink_plan,
    unlink_plan,
)


class Runner(Protocol):
    def local(self, argv: Sequence[str], data: bytes = b"") -> tuple[int, bytes, str]: ...

    def remote(self, target: str, argv: Sequence[str], data: bytes = b"") -> tuple[int, bytes, str]: ...


class Privileged(Protocol):
    def capture(self, argv: Sequence[str]) -> tuple[int, bytes, str]: ...


@dataclass(frozen=True)
class DistributedTools:
    runner: Runner
    pilot: Callable[[], PilotState | None]
    address_towards: Callable[[str], str]
    """Adresse de cette machine vue depuis une machine du reseau (route du systeme)."""
    rescan: Callable[[str], None] = field(default=lambda _target: None)
    """Rescanne une machine (utilisateur@machine) apres la liaison."""


@dataclass(frozen=True)
class StepResult:
    helper: str
    shown: str
    ok: bool
    detail: str = ""
    firewall: tuple[str, ...] = ()
    """Compte rendu d'une commande de pare-feu : une ligne par regle (gestionnaire, reseau, etat, numero
    de regle chez omega-fire) ; retour de l'auteur, 2026-11-21."""


def firewall_lines(output: bytes, command: Sequence[str]) -> tuple[str, ...]:
    """Lignes de compte rendu : la reponse JSON d'omega-fire (`port ouvrir`), sinon la commande lancee
    (ufw, firewalld)."""
    data = _json(output)
    if isinstance(data, dict) and isinstance(data.get("lignes"), list):
        return tuple(
            " · ".join(str(line.get(key, "")) for key in ("cible", "source", "etat", "detail") if line.get(key))
            for line in data["lignes"] if isinstance(line, dict))
    return (" ".join(command),)


def firewall_commands(pilot: PilotState, runner: Runner) -> list[list[str]]:
    """Commandes du pare-feu du pilote, DONNEES par omega-stress (omega-fire d'abord, sinon ufw ou firewalld)."""
    if not pilot.firewall_needs_opening:
        return []
    code, output, _error = runner.local([f"{pilot.root.rstrip('/')}/{STRESS_LAUNCHER}", "coordinateur",
                                         "pare-feu", "ouvrir", "--commandes"])
    data = _json(output) if code == 0 else None
    commands = data.get("commands") if isinstance(data, dict) else None
    return [list(map(str, c)) for c in commands if isinstance(c, list)] if isinstance(commands, list) else []


def plan(pilot: PilotState, helpers: Iterable[Helper], accord: Accord, runner: Runner) -> tuple[LinkStep, ...]:
    return relink_plan(pilot, helpers, accord, firewall_commands(pilot, runner))


def needs_root(steps: Iterable[LinkStep]) -> bool:
    return any(step.where is StepWhere.ROOT for step in steps)


def run_plan(steps: Sequence[LinkStep], tools: DistributedTools, privileged: Privileged | None) -> list[StepResult]:
    """`privileged` : deja authentifie (sudo -v fait par l'interface dans le vrai terminal) ; None = pas de root."""
    results: list[StepResult] = []
    root_outputs: list[str] = []
    access: dict[str, dict[str, Any]] = {}
    failed: set[str] = set()
    targets: dict[str, str] = {}
    for step in steps:
        shown = " ".join(step.argv)
        if step.helper and step.helper in failed:
            continue
        if step.where is StepWhere.LOCAL:
            data = (json.dumps({"outputs": root_outputs}).encode() if "--fait" in step.argv else b"")
            code, output, error = tools.runner.local(step.argv, data)
            if code == 0 and "ajouter-machine" in step.argv:
                data = _json(output)
                if not isinstance(data, dict) or not data.get("secret"):
                    code, error = 1, "no access returned"
                else:
                    access[step.helper] = data
                    shown = " ".join(step.argv)  # le secret n'est jamais affiche
        elif step.where is StepWhere.REMOTE:
            targets[step.helper] = step.target
            granted = access.get(step.helper)
            secret = b""
            values: dict[str, str] = {}
            if "relier" in step.argv:
                if granted is None:
                    failed.add(step.helper)
                    results.append(StepResult(step.helper, shown, False, "no access"))
                    continue
                host = step.target.rpartition("@")[2]
                try:
                    address = tools.address_towards(host)
                except OSError as route_error:
                    failed.add(step.helper)
                    results.append(StepResult(step.helper, shown, False, str(route_error)))
                    continue
                values = {"adresse": f"{address}:{granted.get('port', 9650)}", "id": str(granted["id"])}
                secret = (str(granted.get("secret", "")) + "\n").encode()
            code, _output, error = tools.runner.remote(step.target, fill(step.argv, values), secret)
        else:
            if privileged is None:
                code, error = 1, "sudo"
            else:
                code, output, error = privileged.capture(step.argv)
                root_outputs.append(output.decode("utf-8", "replace"))
                results.append(StepResult("", shown, code == 0, "" if code == 0 else error,
                                          firewall_lines(output, step.argv)))
                continue
        ok = code == 0
        if not ok and step.helper:
            failed.add(step.helper)
        results.append(StepResult(step.helper, shown, ok, "" if ok else error))
    for target in dict.fromkeys(targets.values()):
        try:
            tools.rescan(target)
        except Exception:  # noqa: BLE001 - le rescan ne fait jamais echouer la liaison
            continue
    return results


def unlink(pilot: PilotState, helper: Helper, tools: DistributedTools) -> list[StepResult]:
    return run_plan(unlink_plan(pilot, helper), tools, None)


def _json(output: bytes) -> Any:
    for line in reversed(output.decode("utf-8", "replace").splitlines()):
        if line.strip().startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                return None
    return None
