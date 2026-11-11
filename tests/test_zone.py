# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Zone neutre (lot D) : plans, execution et REVERSIBILITE dans un faux systeme de fichiers.

Aucune commande root n'est lancee : `FakeSystem` interprete les commandes du plan (groupadd, install, gpasswd,
rm, rmdir, groupdel) sur un dossier temporaire et un faux fichier des groupes. La machine est photographiee
avant `etablir` et apres `retirer --tout` : les deux photos doivent etre identiques."""
from __future__ import annotations

import json
import os
import posixpath
from pathlib import Path

import pytest
from omega_lib.synchro.constants import ZONE_GROUP
from omega_lib.synchro.registry import CreatedKind, ZoneState
from zone_fakes import AT, FIRE, FIRE_ID, LATER, SERV, SERV_ID, SUBJECT, FakeSystem, _detection, _installation

from omega_connect.application.zone_actions import (
    apply_plan,
    establish_plan,
    needs_elevation,
    remove_all_plan,
    remove_tool_plan,
)
from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.fail2ban import FileFacts, Presence
from omega_connect.domain.links import CheckCode, LinkState
from omega_connect.domain.zone import NoteCode, OperationKind, ZoneFacts, ZoneSubject, read_registry
from omega_connect.domain.zone_checks import zone_link


@pytest.fixture
def system(tmp_path: Path) -> FakeSystem:
    return FakeSystem(tmp_path)


def _establish(system: FakeSystem, detection: DetectionReport, now: str = AT):
    facts = system.inspect()
    plan = establish_plan(facts, detection, SUBJECT, now)
    return plan, apply_plan(plan, facts, system)


def _remove_all(system: FakeSystem, *, keep_zone: bool = False):
    facts = system.inspect()
    plan = remove_all_plan(facts, LATER, keep_zone=keep_zone)
    return plan, apply_plan(plan, facts, system)


def test_establish_then_remove_all_restores_the_machine(system: FakeSystem):
    before = system.snapshot()
    plan, result = _establish(system, _detection(SERV, FIRE))
    assert result.ok
    kinds = [operation.kind for operation in plan.operations]
    assert kinds[:6] == [OperationKind.CREATE_GROUP] + [OperationKind.CREATE_DIRECTORY] * 5
    assert system.ran[0] == ("groupadd", "--system", ZONE_GROUP)
    assert system.ran[1] == ("install", "-d", "-o", "root", "-g", ZONE_GROUP, "-m", "2750", system.zone)
    assert ("gpasswd", "-a", "k", ZONE_GROUP) in system.ran
    registry = read_registry(system.inspect()).value
    assert registry is not None and registry.state is ZoneState.ACTIVE
    assert [item.installation_id for item in registry.installations] == [FIRE_ID, SERV_ID]
    assert registry.installation(SERV_ID).has_sheet and not registry.installation(FIRE_ID).has_sheet
    assert {item.kind for item in registry.created} == {CreatedKind.GROUP, CreatedKind.DIRECTORY, CreatedKind.MEMBER}
    assert Path(system.zone, "jetons", f"{SERV_ID}.json").is_file()
    assert Path(system.zone, "fiches", f"{SERV_ID}.json").is_file()
    assert system.meta[posixpath.join(system.zone, "registre.json")] == ("root", ZONE_GROUP, 0o640)
    assert zone_link(system.inspect(), _detection(SERV, FIRE), SUBJECT, "oc").state is LinkState.ACTIVE

    plan, result = _remove_all(system)
    assert result.ok, result.error
    assert plan.operations[-1].kind is OperationKind.DELETE_GROUP
    assert system.snapshot() == before


def test_second_establish_has_nothing_to_do_then_refreshes_a_new_version(system: FakeSystem):
    _establish(system, _detection(SERV, FIRE))
    plan, _result = _establish(system, _detection(SERV, FIRE), now=LATER)
    assert plan.operations == () and [note.code for note in plan.notes] == [NoteCode.NOTHING_TO_DO]

    newer = _installation("omega-fire", FIRE_ID, "/home/k/omega-fire", version="3.7.0")
    assert zone_link(system.inspect(), _detection(SERV, newer), SUBJECT, "oc").state is LinkState.DEGRADED
    plan, result = _establish(system, _detection(SERV, newer), now=LATER)
    assert result.ok and [operation.kind for operation in plan.operations] == [OperationKind.WRITE_FILE] * 2
    registry = read_registry(system.inspect()).value
    assert registry.installation(FIRE_ID).version == "3.7.0"
    assert registry.installation(FIRE_ID).linked_at == AT  # date du premier lien gardee


def test_failure_midway_keeps_what_was_created_in_the_registry(system: FakeSystem):
    before = system.snapshot()
    system.fail_on = OperationKind.ADD_MEMBER
    plan, result = _establish(system, _detection(SERV))
    assert not result.ok and result.failed.kind is OperationKind.ADD_MEMBER
    assert result.recovery is not None and result.recovery_ok
    registry = read_registry(system.inspect()).value
    assert {item.kind for item in registry.created} == {CreatedKind.GROUP, CreatedKind.DIRECTORY}
    system.fail_on = None
    _plan, result = _remove_all(system)
    assert result.ok and system.snapshot() == before


def test_unknown_file_keeps_its_folder_the_zone_and_the_group(system: FakeSystem):
    before = system.snapshot()
    _establish(system, _detection(SERV))
    Path(system.zone, "bans", "journal.jsonl").write_text("{}\n", encoding="utf-8")
    plan, result = _remove_all(system)
    assert result.ok
    codes = {note.code for note in plan.notes}
    assert NoteCode.UNKNOWN_FILES_KEPT in codes and NoteCode.GROUP_KEPT in codes
    assert Path(system.zone, "bans", "journal.jsonl").exists() and ZONE_GROUP in system.groups
    registry = read_registry(system.inspect()).value
    assert registry.installations == () and {item.kind for item in registry.created} == {
        CreatedKind.GROUP, CreatedKind.DIRECTORY}
    Path(system.zone, "bans", "journal.jsonl").unlink()
    _plan, result = _remove_all(system)
    assert result.ok and system.snapshot() == before


def test_keep_zone_freezes_and_establish_reactivates(system: FakeSystem):
    _establish(system, _detection(SERV))
    plan, result = _remove_all(system, keep_zone=True)
    assert result.ok and [operation.kind for operation in plan.operations] == [OperationKind.WRITE_FILE]
    assert read_registry(system.inspect()).value.state is ZoneState.FROZEN
    link = zone_link(system.inspect(), _detection(SERV), SUBJECT, "oc")
    assert CheckCode.ZONE_FROZEN in {check.code for check in link.checks}
    _establish(system, _detection(SERV), now=LATER)
    assert read_registry(system.inspect()).value.state is ZoneState.ACTIVE


def test_remove_a_tool_that_was_uninstalled(system: FakeSystem):
    _establish(system, _detection(SERV, FIRE))
    facts = system.inspect()
    refused = remove_tool_plan(facts, _detection(SERV, FIRE), "omega-fire", LATER)
    assert refused.refused and refused.notes[0].code is NoteCode.TARGET_STILL_INSTALLED
    assert remove_tool_plan(facts, _detection(SERV), "omega-stress", LATER).notes[0].code is NoteCode.TARGET_NOT_FOUND

    link = zone_link(facts, _detection(SERV), SUBJECT, "oc")
    gone = [check for check in link.checks if check.code is CheckCode.ZONE_TOOL_GONE]
    assert gone and gone[0].fix == f"oc retirer {FIRE_ID[:8]}"
    plan = remove_tool_plan(facts, _detection(SERV), FIRE_ID[:8], LATER)
    assert apply_plan(plan, facts, system).ok
    assert not Path(system.zone, "jetons", f"{FIRE_ID}.json").exists()
    registry = read_registry(system.inspect()).value
    assert [item.installation_id for item in registry.installations] == [SERV_ID]


def test_refusals_never_propose_a_command(system: FakeSystem):
    os.makedirs(system.zone)
    plan = establish_plan(system.inspect(), _detection(SERV), SUBJECT, AT)
    assert plan.refused and plan.operations == () and plan.notes[0].code is NoteCode.ZONE_FOREIGN
    with pytest.raises(ValueError):
        apply_plan(plan, system.inspect(), system)
    os.rmdir(system.zone)
    os.symlink("/etc", system.zone)
    plan = establish_plan(system.inspect(), _detection(SERV), SUBJECT, AT)
    assert plan.refused and plan.notes[0].code is NoteCode.ZONE_UNSAFE
    assert remove_all_plan(system.inspect(), AT, keep_zone=False).refused


def test_damaged_registry_is_never_trusted_for_removal(system: FakeSystem):
    _establish(system, _detection(SERV))
    path = Path(system.zone, "registre.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["created"].append({"kind": "directory", "target": "/etc/../root", "at": AT})
    path.write_text(json.dumps(data), encoding="utf-8")
    plan = remove_all_plan(system.inspect(), LATER, keep_zone=False)
    assert plan.refused and plan.notes[0].code is NoteCode.REGISTRY_DAMAGED


def test_relogin_and_unreadable_zone_are_not_failures(system: FakeSystem):
    _establish(system, _detection(SERV))
    fresh = ZoneSubject("k", ("k",))
    link = zone_link(system.inspect(), _detection(SERV), fresh, "oc")
    assert CheckCode.ZONE_RELOGIN in {check.code for check in link.checks} and link.state is LinkState.ACTIVE
    hidden = ZoneFacts(system.zone, {"": system.inspect().root}, False, group_exists=True, group_members=("k",))
    waiting = zone_link(hidden, _detection(SERV), fresh, "oc")
    assert waiting.state is LinkState.UNVERIFIABLE
    assert [check.code for check in waiting.checks] == [CheckCode.ZONE_AWAITING_RELOGIN]  # une seule raison, explicite
    stranger = zone_link(hidden, _detection(SERV), ZoneSubject("autre", ("autre",)), "oc")
    reason = next(check for check in stranger.checks if check.status.value == "unverifiable")
    assert reason.code is CheckCode.ZONE_NOT_MEMBER_UNREADABLE and reason.fix == "oc etablir"
    assert needs_elevation(hidden)
    empty = ZoneFacts(system.zone, {"": FileFacts(system.zone, Presence.MISSING)}, True)
    assert zone_link(empty, _detection(SERV), SUBJECT, "oc").state is LinkState.ABSENT
    assert not needs_elevation(empty)
