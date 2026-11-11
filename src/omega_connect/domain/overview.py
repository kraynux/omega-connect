# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Vue d'ensemble du Dashboard (refonte, demande de l'auteur 2026-11-11) : des cadres separes, comme un tableau de
bord web. Machines, applications, liaisons, espace partage ; liaisons par type ; local / reseau ; un top 5 (top 3
sur un ecran etroit) par categorie.

Tout est calcule sur ce qui est deja connu : la verification de cette machine et le dernier scan de chaque machine
du reseau (registre du parc). Rien n'est lance, aucune connexion. Les mots d'etat sont ceux du reste de
l'application (OK, a reparer, a reparer (bloquant), absent, non verifiable ; Reliee, Inscrite, ...)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from omega_connect.domain.fleet import AppState, RegistryRow, SpaceStatus
from omega_connect.domain.links import Link, LinkKind, LinkState
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.versions import version_key

TOP_WIDE = 5
TOP_NARROW = 3
TO_FIX_STATES = (LinkState.BROKEN, LinkState.DEGRADED)
LATE_STATES = (AppState.OLD_VERSION, AppState.INCOMPLETE)


@dataclass(frozen=True)
class MachineView:
    name: str
    local: bool
    seen_at: datetime | None
    reachable: bool
    rows: tuple[RegistryRow, ...]
    links: tuple[Link, ...]

    @property
    def links_to_fix(self) -> int:
        return sum(1 for link in self.links if link.state in TO_FIX_STATES)

    @property
    def blocking(self) -> int:
        return sum(1 for link in self.links if link.state is LinkState.BROKEN)

    @property
    def apps_to_fix(self) -> int:
        return sum(1 for row in self.rows if row.state is AppState.TO_FIX)


@dataclass(frozen=True)
class KindCount:
    kind: LinkKind
    ok: int
    to_fix: int
    total: int


@dataclass(frozen=True)
class SideCount:
    machines: int
    applications: int
    states: Counter[LinkState]


@dataclass(frozen=True)
class Overview:
    machines: tuple[MachineView, ...]
    """Cette machine d'abord, puis celles du reseau."""
    space: SpaceStatus

    @property
    def local(self) -> tuple[MachineView, ...]:
        return tuple(machine for machine in self.machines if machine.local)

    @property
    def network(self) -> tuple[MachineView, ...]:
        return tuple(machine for machine in self.machines if not machine.local)

    @property
    def unreachable(self) -> int:
        return sum(1 for machine in self.machines if not machine.reachable)

    def rows(self) -> tuple[RegistryRow, ...]:
        return tuple(row for machine in self.machines for row in machine.rows)

    def links(self) -> tuple[Link, ...]:
        return tuple(link for machine in self.machines for link in machine.links)

    def app_states(self) -> Counter[AppState]:
        return Counter(row.state for row in self.rows())

    def link_states(self) -> Counter[LinkState]:
        return Counter(link.state for link in self.links())

    def by_kind(self) -> tuple[KindCount, ...]:
        """Une ligne par type de liaison present, dans l'ordre des types."""
        links = self.links()
        result = []
        for kind in LinkKind:
            found = [link for link in links if link.kind is kind]
            if found:
                result.append(KindCount(kind, sum(1 for link in found if link.state is LinkState.ACTIVE),
                                        sum(1 for link in found if link.state in TO_FIX_STATES), len(found)))
        return tuple(result)

    def side(self, local: bool) -> SideCount:
        machines = self.local if local else self.network
        return SideCount(len(machines), sum(len(machine.rows) for machine in machines),
                         Counter(link.state for machine in machines for link in machine.links))

    # ---- tops ---------------------------------------------------------------

    def top_machines(self, size: int) -> tuple[MachineView, ...]:
        """Machines qui ont le plus a reparer (liaisons bloquantes d'abord) ; une machine sans rien n'y est pas."""
        found = [machine for machine in self.machines if machine.links_to_fix or machine.apps_to_fix]
        found.sort(key=lambda machine: (-machine.blocking, -(machine.links_to_fix + machine.apps_to_fix),
                                        machine.name))
        return tuple(found[:size])

    def top_links(self, size: int) -> tuple[tuple[Link, str], ...]:
        """Liaisons a reparer, les bloquantes d'abord, avec le nom de leur machine."""
        found = [(link, machine.name) for machine in self.machines for link in machine.links
                 if link.state in TO_FIX_STATES]
        found.sort(key=lambda item: (TO_FIX_STATES.index(item[0].state), item[1], list(LinkKind).index(item[0].kind)))
        return tuple(found[:size])

    def top_versions(self, size: int) -> tuple[RegistryRow, ...]:
        """Applications en retard (ancienne version, installation inachevee), les plus anciennes d'abord."""
        found = [row for row in self.rows() if row.state in LATE_STATES]
        found.sort(key=lambda row: (row.state is not AppState.OLD_VERSION, version_key(row.version) or (),
                                    row.tool, row.machine))
        return tuple(found[:size])

    def top_oldest(self, size: int) -> tuple[MachineView, ...]:
        """Machines du reseau vues il y a le plus longtemps (dernier scan) ; les injoignables d'abord."""
        found = list(self.network)
        found.sort(key=lambda machine: (machine.reachable, machine.seen_at or datetime.min.astimezone(),
                                        machine.name))
        return tuple(found[:size])


def parse_moment(text: str) -> datetime | None:
    """`2026-11-11T09:30:00Z` -> datetime avec fuseau ; None si illisible."""
    value = text.strip()
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.astimezone()


def build_overview(*, machine: str, rows: Iterable[RegistryRow], links: Iterable[Link], space: SpaceStatus,
                   verified_at: datetime | None, network: Iterable[MachineEntry]) -> Overview:
    """`rows`/`links` : cette machine (verification en cours) ; `network` : le registre du parc (dernier scan)."""
    machines = [MachineView(machine, True, verified_at, True, tuple(rows), tuple(links))]
    for entry in network:
        if entry.local:
            continue
        machines.append(MachineView(entry.name, False, parse_moment(entry.scanned_at), entry.reachable,
                                    entry.shown_rows(), entry.links))
    return Overview(tuple(machines), space)
