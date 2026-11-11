# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Refonte du parcours, lot R1 : etats du registre, « Inscrire » en un seul plan, registre du parc, et les
commandes `scanner` / `inscrire`. Faux systeme et faux executeur : jamais de vrai sudo, jamais le vrai /var/lib."""
from __future__ import annotations

from pathlib import Path

import pytest
from omega_lib.synchro.models import InstanceSheet, ReadStatus
from zone_fakes import AT, FIRE, LATER, SERV, SUBJECT, FakeSystem, _detection

from omega_connect.application.enroll_actions import EnrollTools, enroll_plan, run_enroll
from omega_connect.application.repair_actions import RepairTools
from omega_connect.application.zone_actions import ZoneTools, apply_plan, establish_plan
from omega_connect.domain.detection import DetectedInstallation, SheetResult, Source
from omega_connect.domain.enroll import unannounced
from omega_connect.domain.fleet import AppState, SpaceStatus, registry_rows, space_status
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind, VerificationReport
from omega_connect.domain.parc import MachineEntry, parc_from_dict, parc_to_dict
from omega_connect.domain.repair import RepairStep, StepOutcome
from omega_connect.domain.zone import Operation, OperationKind, read_registry
from omega_connect.domain.zone_checks import zone_link
from omega_connect.infrastructure.fleet.parc_store import FileParcStore
from omega_connect.interfaces.cli.main import run

NEW_ROOT = "/home/k/omega-waf"
NEW = DetectedInstallation(NEW_ROOT, "omega-serv", (Source.HOME,), "k", ReadStatus.ABSENT,
                           sheet=SheetResult(ReadStatus.OK, InstanceSheet("omega-serv", "2.6.1", "", "omega-serv", AT)))
OLD = DetectedInstallation("/home/k/omega-fire-vieux", "omega-fire", (Source.HOME,), "k", ReadStatus.ABSENT,
                           sheet=SheetResult(ReadStatus.ABSENT))
OTHER = DetectedInstallation("/home/autre/omega-jail", "omega-jail", (Source.HOME,), "autre", ReadStatus.ABSENT)


@pytest.fixture
def system(tmp_path: Path) -> FakeSystem:
    return FakeSystem(tmp_path)


class _Subject:
    def subject(self):
        return SUBJECT


class _Noted:
    def __init__(self) -> None:
        self.ran: list[tuple[str, ...]] = []

    def run(self, step: RepairStep) -> StepOutcome:
        self.ran.append(step.argv())
        return StepOutcome(step, 0)


def _tools(system: FakeSystem, detection, noted: _Noted | None = None, interactive: bool = True) -> EnrollTools:
    zone = ZoneTools(inspector=system, runner=system, subject=_Subject(), now=lambda: LATER,
                     interactive=lambda: interactive)
    return EnrollTools(zone=zone, repair=RepairTools(runner=noted or _Noted(), user=lambda: "k"),
                       detect=lambda: detection)


def _report(system: FakeSystem, detection, *extra: Link) -> VerificationReport:
    return VerificationReport(detection, (*extra, zone_link(system.inspect(), detection, SUBJECT, "oc")))


# ---- etats du registre -----------------------------------------------------------------------

def test_row_states(system: FakeSystem):
    detection = _detection(SERV, FIRE, NEW, OLD)
    rows = {row.root: row.state for row in registry_rows(_report(system, detection), system.inspect())}
    assert rows == {SERV.root: AppState.ENROLLED, FIRE.root: AppState.ENROLLED, NEW_ROOT: AppState.DETECTED,
                    OLD.root: AppState.OLD_VERSION}
    assert space_status(_report(system, detection)) is SpaceStatus.NOT_PREPARED

    facts = system.inspect()
    assert apply_plan(establish_plan(facts, _detection(SERV, FIRE), SUBJECT, AT), facts, system).ok
    broken = Link(LinkKind.BLOCKLIST, "omega-serv", SERV.root, (
        Check(CheckCode.BLOCKLIST_MODE, CheckStatus.FAILURE, f"{SERV.root}/var/b.json", fix="p"),))
    log_only = Link(LinkKind.MAGNET_LOGS, "omega-serv", FIRE.root, (
        Check(CheckCode.MAGNET_LOG_ONLY, CheckStatus.WARNING, "omega-waf-magnet-alerts"),))  # rien a corriger
    report = _report(system, detection, broken, log_only)
    rows = {row.root: row.state for row in registry_rows(report, system.inspect())}
    assert rows[SERV.root] is AppState.TO_FIX and rows[FIRE.root] is AppState.LINKED
    assert space_status(report) is SpaceStatus.READY


def test_parc_round_trip(tmp_path: Path, system: FakeSystem):
    rows = registry_rows(_report(system, _detection(SERV, NEW)), system.inspect(), "pc-107")
    store = FileParcStore(tmp_path / "var")
    store.save(MachineEntry("pc-107", True, AT, rows))
    store.save(MachineEntry("hpc-109", False, AT, ()))
    store.save(MachineEntry("pc-107", True, LATER, rows))
    machines = store.load()
    assert [machine.name for machine in machines] == ["pc-107", "hpc-109"] and machines[0].scanned_at == LATER
    assert {row.state for row in machines[0].rows} == {AppState.ENROLLED, AppState.DETECTED}
    assert parc_from_dict({"format": "autre"}) == ()
    assert parc_from_dict(parc_to_dict(machines)) == machines


# ---- « Inscrire » : un seul plan ---------------------------------------------------------------

def test_one_plan_cards_then_shared_space(system: FakeSystem):
    detection = _detection(SERV, FIRE, NEW, OLD, OTHER)
    noted = _Noted()
    tools = _tools(system, detection, noted)
    plan = enroll_plan(system.inspect(), detection, tools)
    assert [step.root for step in plan.cards] == [NEW_ROOT]  # ancienne version : pas de carte possible
    assert [skipped.step.root for skipped in plan.skipped] == [OTHER.root]  # autre compte
    assert plan.pending == (NEW_ROOT,) and plan.needs_root
    kinds = [operation.kind for operation in plan.space.operations]
    assert kinds[0] is OperationKind.CREATE_GROUP and OperationKind.ADD_MEMBER in kinds
    result = run_enroll(plan, tools)
    assert result.ok and noted.ran == [(f"{NEW_ROOT}/omega-serv.sh", "synchro", "jeton")]
    registry = read_registry(system.inspect()).value
    assert registry is not None and {item.root for item in registry.installations} == {SERV.root, FIRE.root}


def test_selection_only(system: FakeSystem):
    detection = _detection(SERV, FIRE)
    tools = _tools(system, detection)
    plan = enroll_plan(system.inspect(), detection, tools, (FIRE.root,))
    assert plan.roots == (FIRE.root,)
    assert run_enroll(plan, tools).ok
    registry = read_registry(system.inspect()).value
    assert registry is not None and [item.root for item in registry.installations] == [FIRE.root]


def test_a_command_that_was_not_announced_is_never_run(system: FakeSystem):
    detection = _detection(SERV)
    tools = _tools(system, detection)
    plan = enroll_plan(system.inspect(), detection, tools)
    sneaky = Operation(OperationKind.ADD_MEMBER, "intrus")
    assert unannounced(plan, type(plan.space)(plan.space.action, plan.space.zone, LATER, None,
                                              (*plan.space.operations, sneaky))) == (sneaky,)

    # Entre l'affichage du plan et « Lancer », le groupe disparait : le plan recalcule voudrait le recreer, ce qui
    # n'etait pas annonce -> arret avant l'espace partage, aucune commande root.
    facts = system.inspect()
    assert apply_plan(establish_plan(facts, _detection(SERV), SUBJECT, AT), facts, system).ok
    detection = _detection(SERV, NEW)
    tools = _tools(system, detection)
    plan = enroll_plan(system.inspect(), detection, tools)
    assert plan.pending == (NEW_ROOT,)
    assert OperationKind.CREATE_GROUP not in {operation.kind for operation in plan.space.operations}
    del system.groups["omega-synchro"]
    system.ran.clear()
    result = run_enroll(plan, tools)
    assert not result.ok and result.unannounced[0].kind is OperationKind.CREATE_GROUP and not system.ran


def test_nothing_to_do_once_linked(system: FakeSystem):
    detection = _detection(SERV, FIRE)
    tools = _tools(system, detection)
    assert run_enroll(enroll_plan(system.inspect(), detection, tools), tools).ok
    again = enroll_plan(system.inspect(), detection, tools)
    assert again.empty


# ---- ligne de commande ------------------------------------------------------------------------

def test_cli_scanner_and_inscrire(system: FakeSystem, capsys):
    detection = _detection(SERV, FIRE, NEW)
    noted = _Noted()
    tools = _tools(system, detection, noted)
    parc_saved: list[MachineEntry] = []

    class Parc:
        def load(self):
            return tuple(parc_saved)

        def save(self, machine):
            parc_saved.append(machine)

    def verify(_request):
        return _report(system, detection)

    assert run(["scanner"], lambda _request: detection, verify, zone=tools.zone, parc=Parc(), machine="pc-t") == 0
    out = capsys.readouterr().out
    assert "Registre — machine pc-t" in out and "◐ Inscrite" in out and "○ Détectée" in out
    assert "pas encore préparé" in out and parc_saved[0].name == "pc-t"

    assert run(["inscrire", "--simulation"], lambda _request: detection, verify, zone=tools.zone,
               repair=tools.repair) == 0
    assert not system.ran and not noted.ran and "Cartes d'identité à créer" in capsys.readouterr().out

    assert run(["synchroniser", "omega-fire", "--oui"], lambda _request: detection, verify, zone=tools.zone,
               repair=tools.repair) == 0
    assert "Synchronisation terminée" in capsys.readouterr().out
    registry = read_registry(system.inspect()).value
    assert registry is not None and [item.root for item in registry.installations] == [FIRE.root]
    assert run(["inscrire", "rien-de-tel"], lambda _request: detection, verify, zone=tools.zone,
               repair=tools.repair) == 2


def test_link_provenance():
    from omega_connect.domain.links import Provenance

    local = Link(LinkKind.BLOCKLIST, "omega-serv", "/r", ())
    remote = Link(LinkKind.BLOCKLIST, "omega-serv", "/r", (), machine="hpc-109")
    between = Link(LinkKind.BRIDGE, "", "", (), peer="hpc-109")
    assert local.provenance is Provenance.LOCAL
    assert remote.provenance is Provenance.NETWORK and between.provenance is Provenance.NETWORK
