# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Dashboard (refonte 2026-11-11) : calcul de la vue d'ensemble, sans interface."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from omega_connect.domain.fleet import AppState, RegistryRow, SpaceStatus
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind, LinkState
from omega_connect.domain.overview import build_overview, parse_moment
from omega_connect.domain.parc import MachineEntry
from omega_connect.interfaces.tui.overview_view import ago, top_size
from omega_connect.interfaces.tui.screens.overview import columns

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def _link(kind: LinkKind, status: CheckStatus, machine: str = "") -> Link:
    code = CheckCode.BLOCKLIST_OK if status is CheckStatus.OK else CheckCode.BLOCKLIST_ROOT_OWNED
    return Link(kind, "omega-serv", "/srv/s", (Check(code, status, "/b"),), machine=machine)


def _row(machine: str, tool: str, state: AppState, version: str = "1.0.0") -> RegistryRow:
    return RegistryRow(machine, tool, f"/srv/{tool}", "", "", version, state)


def _overview():  # type: ignore[no-untyped-def]
    web = MachineEntry("web", False, "2026-11-11T11:00:00Z",
                       (_row("web", "omega-serv", AppState.TO_FIX), _row("web", "omega-jail", AppState.OLD_VERSION,
                                                                         "1.1.0")),
                       "1" * 16, links=(_link(LinkKind.BLOCKLIST, CheckStatus.FAILURE, "web"),
                                        _link(LinkKind.SERV_LOGS, CheckStatus.WARNING, "web")))
    gate = MachineEntry("gate", False, "2026-11-08T12:00:00Z", (_row("gate", "omega-fire", AppState.LINKED),),
                        "2" * 16, reachable=False)
    return build_overview(machine="poste", rows=(_row("poste", "omega-fire", AppState.LINKED),),
                          links=(_link(LinkKind.BLOCKLIST, CheckStatus.OK),
                                 _link(LinkKind.SERV_LOGS, CheckStatus.WARNING)),
                          space=SpaceStatus.READY, verified_at=NOW, network=(web, gate))


def test_counters_and_sides():
    overview = _overview()
    assert [machine.name for machine in overview.machines] == ["poste", "web", "gate"]
    assert overview.unreachable == 1
    assert overview.link_states()[LinkState.BROKEN] == 1 and overview.link_states()[LinkState.DEGRADED] == 2
    blocklist = next(row for row in overview.by_kind() if row.kind is LinkKind.BLOCKLIST)
    assert (blocklist.ok, blocklist.to_fix, blocklist.total) == (1, 1, 2)
    assert overview.side(True).machines == 1 and overview.side(False).applications == 3


def test_tops_order_blocking_first_and_skip_machines_with_nothing_to_fix():
    overview = _overview()
    assert [machine.name for machine in overview.top_machines(5)] == ["web", "poste"]  # gate : rien a reparer
    first, machine = overview.top_links(5)[0]
    assert first.state is LinkState.BROKEN and machine == "web"
    assert [row.tool for row in overview.top_versions(5)] == ["omega-jail"]
    assert [machine.name for machine in overview.top_oldest(5)] == ["gate", "web"]  # injoignable d'abord
    assert len(overview.top_links(1)) == 1


def test_small_screen_and_columns():
    assert top_size(140, 45) == 5 and top_size(90, 45) == 3 and top_size(140, 25) == 3
    assert columns(140, 4) == 4 and columns(90, 4) == 2 and columns(50, 4) == 1


def test_relative_moments():
    assert parse_moment("2026-11-11T11:00:00Z") == NOW - timedelta(hours=1)
    assert parse_moment("pas une date") is None
    assert ago(NOW - timedelta(hours=3), NOW) == "il y a 3 h" and ago(None, NOW) == "jamais vue"
