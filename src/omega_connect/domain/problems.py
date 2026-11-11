# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tout ce qui ne va pas, sur toutes les machines (ecran Reparer ; retour de l'auteur, 2026-11-11 : « dans Reparer
il devrait y avoir la liste de tout ce qui ne va pas, et la on choisit de reparer »). Regles pures : une ligne par
probleme, la machine, et ce qui le corrige."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from omega_connect.domain.fleet import AppState, RegistryRow
from omega_connect.domain.links import CheckStatus, Link, LinkState
from omega_connect.domain.parc import MachineEntry

TO_REPAIR = (LinkState.DEGRADED, LinkState.BROKEN)


class ProblemKind(str, Enum):
    UNREACHABLE = "unreachable"
    """Machine qui ne repond plus : la rescanner (Scanner)."""
    UPDATE = "update"
    """Application trop ancienne ou installation inachevee : « Mettre a jour l'application »."""
    REPAIR = "repair"
    """Liaison a reparer : Reparer (commandes des outils ; commandes « a la main » lancees aussi a distance)."""


KIND_ORDER = {ProblemKind.UNREACHABLE: 0, ProblemKind.UPDATE: 1, ProblemKind.REPAIR: 2}


@dataclass(frozen=True)
class Problem:
    machine: str
    """Nom affiche de la machine (cette machine : son nom)."""
    local: bool
    kind: ProblemKind
    link: Link | None = None
    row: RegistryRow | None = None
    target: str = ""
    """`utilisateur@machine` d'une machine du reseau ; vide pour cette machine."""

    @property
    def by_tool(self) -> bool:
        """Au moins un ecart que l'outil proprietaire sait corriger lui-meme."""
        return self.link is not None and any(
            check.repair is not None for check in self.link.checks
            if check.status in (CheckStatus.WARNING, CheckStatus.FAILURE))

    @property
    def fixable(self) -> bool:
        """Une correction connue : l'outil la fait, ou une commande est connue (lancee sur la machine, ou copiee)."""
        if self.link is None:
            return True
        return self.by_tool or any(check.fix for check in self.link.checks
                                   if check.status in (CheckStatus.WARNING, CheckStatus.FAILURE))

    @property
    def blocking(self) -> bool:
        return self.link is not None and self.link.state is LinkState.BROKEN


def _machine_problems(name: str, local: bool, links: Iterable[Link], rows: Iterable[RegistryRow],
                      target: str = "") -> list[Problem]:
    found = [Problem(name, local, ProblemKind.UPDATE, row=row, target=target) for row in rows
             if row.state in (AppState.OLD_VERSION, AppState.INCOMPLETE)]
    found += [Problem(name, local, ProblemKind.REPAIR, link=link, target=target) for link in links
              if link.state in TO_REPAIR]
    return found


def problems(machine: str, links: Iterable[Link], rows: Iterable[RegistryRow],
             network: Iterable[MachineEntry]) -> tuple[Problem, ...]:
    """Cette machine d'abord (verification du moment), puis chaque machine du reseau (son dernier scan)."""
    found = _machine_problems(machine, True, links, rows)
    for entry in network:
        if entry.local:
            continue
        if not entry.reachable:
            found.append(Problem(entry.label, False, ProblemKind.UNREACHABLE, target=entry.target))
            continue
        found += _machine_problems(entry.label, False, entry.links, entry.shown_rows(), entry.target)
    order = {name: index for index, name in enumerate(dict.fromkeys(problem.machine for problem in found))}
    return tuple(sorted(found, key=lambda problem: (order[problem.machine], KIND_ORDER[problem.kind],
                                                     not problem.blocking)))
