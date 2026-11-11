# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lot E : `reparer` (commandes des outils proprietaires) et groupe de la zone donne au service omega-serv.

Aucune commande root n'est lancee : `FakeSystem` joue la zone et omega-serv, un faux executeur note les
commandes des outils, un faux `sudo` (script place en tete du PATH) remplace le vrai."""
from __future__ import annotations

from pathlib import Path

import pytest
from omega_lib.synchro.constants import ZONE_GROUP
from omega_lib.synchro.models import ReadStatus
from omega_lib.synchro.registry import CreatedKind
from omega_lib.synchro.service_group import drop_in_text
from zone_fakes import AT, FIRE, LATER, SERV, SERV_SERVICE, SUBJECT, FakeSystem, _detection

from omega_connect.application.repair_actions import RepairTools, run_steps
from omega_connect.application.zone_actions import ZoneTools, apply_plan, establish_plan, remove_all_plan
from omega_connect.domain.detection import DetectedInstallation, DetectionReport, Source
from omega_connect.domain.links import (
    Check,
    CheckCode,
    CheckStatus,
    Link,
    LinkKind,
    Repair,
    RepairKind,
    VerificationReport,
)
from omega_connect.domain.repair import RepairStep, StepOutcome, plan_repair
from omega_connect.domain.zone import NoteCode, OperationKind, read_registry
from omega_connect.domain.zone_checks import zone_link
from omega_connect.infrastructure.repair.tool_runner import ToolCommandRunner
from omega_connect.infrastructure.zone.inspector import SystemZoneInspector
from omega_connect.interfaces.cli.main import run

JAIL_ROOT = "/home/k/omega-jail"
SERV_ROOT = "/home/k/omega-serv"
OTHER_ROOT = "/home/autre/omega-fire"


# ---- plan --------------------------------------------------------------------------------------

def _report(*links: Link) -> VerificationReport:
    installations = (
        DetectedInstallation(SERV_ROOT, "omega-serv", (Source.HOME,), "k", ReadStatus.OK),
        DetectedInstallation(JAIL_ROOT, "omega-jail", (Source.HOME,), "k", ReadStatus.OK),
        DetectedInstallation(OTHER_ROOT, "omega-fire", (Source.HOME,), "autre", ReadStatus.ABSENT,
                             version="3.6.1"),
    )
    return VerificationReport(DetectionReport("/home/k", installations), links)


JAIL = Repair(RepairKind.JAIL_APPLY, JAIL_ROOT, "omega-jail")
PERMISSIONS = Repair(RepairKind.SERV_PERMISSIONS, SERV_ROOT, "omega-serv", "omega-serv")


def _sample_report() -> VerificationReport:
    serv_links = Link(LinkKind.SERV_LOGS, "omega-serv", SERV_ROOT, (
        Check(CheckCode.JAIL_LOG_MISSING, CheckStatus.FAILURE, "/x.log", fix="j", repair=JAIL),
        Check(CheckCode.JAIL_LOG_RIGHTS, CheckStatus.WARNING, "/y.log", fix="p", repair=PERMISSIONS),
        Check(CheckCode.JAIL_LOG_OK, CheckStatus.OK, "/z.log", repair=PERMISSIONS),
    ))
    blocklist = Link(LinkKind.BLOCKLIST, "omega-serv", SERV_ROOT, (
        Check(CheckCode.BLOCKLIST_MODE, CheckStatus.FAILURE, "/b", fix="p", repair=PERMISSIONS),
        Check(CheckCode.BLOCKLIST_OWNER, CheckStatus.WARNING, "/b", fix="sudo chown k /b"),
    ))
    files = Link(LinkKind.FAIL2BAN_FILES, "", "", (
        Check(CheckCode.FILE_RIGHTS, CheckStatus.WARNING, "/etc/fail2ban/jail.d/omega-a.conf", fix="j", repair=JAIL),
        Check(CheckCode.NO_JAIL_FILES, CheckStatus.INFO, fix="j", repair=JAIL),
    ))
    tokens = Link(LinkKind.TOKENS, "", "", (
        Check(CheckCode.TOKEN_MISSING, CheckStatus.WARNING, OTHER_ROOT, "omega-fire", fix="t",
              repair=Repair(RepairKind.TOKEN, OTHER_ROOT, "omega-fire")),
        Check(CheckCode.TOKEN_MISSING, CheckStatus.WARNING, SERV_ROOT, "omega-serv", fix="t",
              repair=Repair(RepairKind.TOKEN, SERV_ROOT, "omega-serv")),
    ))
    zone = Link(LinkKind.ZONE, "", "", (
        Check(CheckCode.ZONE_COPY_STALE, CheckStatus.WARNING, SERV_ROOT, fix="e", repair=Repair(RepairKind.ZONE)),
        Check(CheckCode.ZONE_TOOL_GONE, CheckStatus.WARNING, "/old", fix="omega-connect retirer 12345678"),
    ))
    return _report(serv_links, blocklist, files, tokens, zone)


def test_plan_groups_by_owner_tool_in_order():
    plan = plan_repair(_sample_report(), "k", as_root=False)
    assert [step.kind for step in plan.steps] == [RepairKind.TOKEN, RepairKind.SERV_PERMISSIONS,
                                                  RepairKind.JAIL_APPLY]
    token, permissions, jail = plan.steps
    assert token.argv() == (f"{SERV_ROOT}/omega-serv.sh", "synchro", "jeton") and token.account == "k"
    assert permissions.argv() == (f"{SERV_ROOT}/omega-serv.sh", "service", "permissions", "--service-name",
                                  "omega-serv")
    assert len(permissions.findings) == 2 and permissions.needs_root  # le controle conforme n'y est pas
    assert jail.argv() == (f"{JAIL_ROOT}/omega-jail.sh", "--apply", "--update") and len(jail.findings) == 2
    assert [finding.check.code for finding in plan.zone] == [CheckCode.ZONE_COPY_STALE]
    assert [finding.check.code for finding in plan.manual] == [CheckCode.BLOCKLIST_OWNER]
    assert [finding.check.code for finding in plan.decisions] == [CheckCode.ZONE_TOOL_GONE]
    assert [skipped.step.root for skipped in plan.skipped] == [OTHER_ROOT]
    assert plan.needs_root


def test_root_session_can_create_another_accounts_token():
    plan = plan_repair(_sample_report(), "k", as_root=True)
    assert [step.account for step in plan.steps if step.kind is RepairKind.TOKEN] == ["autre", "k"]
    assert not plan.skipped


def test_nothing_to_repair():
    plan = plan_repair(_report(Link(LinkKind.TOKENS, "", "", (Check(CheckCode.TOKEN_OK, CheckStatus.OK),))), "k",
                       as_root=False)
    assert plan.empty and not plan.needs_root


def test_run_stops_at_first_failure():
    plan = plan_repair(_sample_report(), "k", as_root=False)
    ran: list[RepairStep] = []

    class Runner:
        def run(self, step: RepairStep) -> StepOutcome:
            ran.append(step)
            return StepOutcome(step, 0 if step.kind is RepairKind.TOKEN else 3, "boom")

    result = run_steps(plan.steps, Runner())
    assert not result.ok and len(ran) == 2 and result.failed is not None and result.failed.code == 3


# ---- verifier : le bon outil pour chaque ecart ----------------------------------------------

def test_verify_names_the_owner_tool(tmp_path):
    from omega_connect.domain.fail2ban import Fail2banSnapshot, FileFacts, Presence
    from omega_connect.domain.links import evaluate_links, read_fail2ban

    jail = DetectedInstallation(JAIL_ROOT, "omega-jail", (Source.HOME,), "k", ReadStatus.OK)
    detection = DetectionReport("/home/k", (jail,))
    path = "/etc/fail2ban/jail.d/omega-jail-x.conf"
    snapshot = Fail2banSnapshot(installed=True, readable=True, jail_files=(), filter_files=(
        FileFacts(path, Presence.PRESENT, is_file=True, owner="root", group="root", mode=0o666),))
    links = evaluate_links(detection, read_fail2ban(snapshot), {})
    files = next(link for link in links if link.kind is LinkKind.FAIL2BAN_FILES)
    unsafe = next(check for check in files.checks if check.code is CheckCode.FILE_UNSAFE)
    assert unsafe.fix == f"{JAIL_ROOT}/omega-jail.sh --apply --update" and unsafe.repair == JAIL


# ---- groupe de la zone donne au service ------------------------------------------------------

@pytest.fixture
def system(tmp_path: Path) -> FakeSystem:
    return FakeSystem(tmp_path)


def test_establish_asks_omega_serv_for_the_service_group_then_remove_all_restores(system: FakeSystem):
    before = system.snapshot()
    facts = system.inspect()
    plan = establish_plan(facts, _detection(SERV_SERVICE, FIRE), SUBJECT, AT)
    kinds = [operation.kind for operation in plan.operations]
    grant = kinds.index(OperationKind.GRANT_SERVICE_GROUP)
    assert kinds.index(OperationKind.CREATE_GROUP) < grant
    assert plan.operations[grant].argv() == (f"{SERV_ROOT}/omega-serv.sh", "synchro", "groupe-service", "ajouter",
                                             "--service-name", "omega-serv")
    assert NoteCode.SERVICE_RESTART in {note.code for note in plan.notes}
    assert apply_plan(plan, facts, system).ok
    assert system.service_groups == {"omega-serv"}
    registry = read_registry(system.inspect()).value
    assert registry is not None
    assert [item.target for item in registry.created_items(CreatedKind.SERVICE_GROUP)] == ["omega-serv"]
    link = zone_link(system.inspect(), _detection(SERV_SERVICE, FIRE), SUBJECT, "omega-connect")
    assert CheckCode.ZONE_SERVICE_GROUP_OK in {check.code for check in link.checks}

    again = establish_plan(system.inspect(), _detection(SERV_SERVICE, FIRE), SUBJECT, LATER)
    assert OperationKind.GRANT_SERVICE_GROUP not in {operation.kind for operation in again.operations}

    facts = system.inspect()
    removal = remove_all_plan(facts, LATER, keep_zone=False, detection=_detection(SERV_SERVICE, FIRE))
    kinds = [operation.kind for operation in removal.operations]
    assert kinds[0] is OperationKind.REVOKE_SERVICE_GROUP and kinds[-1] is OperationKind.DELETE_GROUP
    assert apply_plan(removal, facts, system).ok
    assert system.snapshot() == before


def test_service_on_the_owner_account_needs_nothing(system: FakeSystem):
    plan = establish_plan(system.inspect(), _detection(SERV, FIRE), SUBJECT, AT)
    assert OperationKind.GRANT_SERVICE_GROUP not in {operation.kind for operation in plan.operations}


def test_missing_service_group_is_reported_and_repaired_by_establish(system: FakeSystem):
    facts = system.inspect()
    assert apply_plan(establish_plan(facts, _detection(SERV_SERVICE), SUBJECT, AT), facts, system).ok
    system.service_groups.clear()  # complement retire a la main
    link = zone_link(system.inspect(), _detection(SERV_SERVICE), SUBJECT, "omega-connect")
    missing = next(check for check in link.checks if check.code is CheckCode.ZONE_SERVICE_GROUP_MISSING)
    assert missing.status is CheckStatus.WARNING and missing.repair == Repair(RepairKind.ZONE)
    plan = establish_plan(system.inspect(), _detection(SERV_SERVICE), SUBJECT, LATER)
    grant = next(operation for operation in plan.operations if operation.kind is OperationKind.GRANT_SERVICE_GROUP)
    assert grant.record is None  # deja au registre : pas de doublon
    assert apply_plan(plan, system.inspect(), system).ok


def test_group_kept_while_a_service_still_has_it_and_omega_serv_is_gone(system: FakeSystem):
    facts = system.inspect()
    assert apply_plan(establish_plan(facts, _detection(SERV_SERVICE), SUBJECT, AT), facts, system).ok
    facts = system.inspect()
    plan = remove_all_plan(facts, LATER, keep_zone=False, detection=_detection())
    assert NoteCode.SERVICE_GROUP_KEPT in {note.code for note in plan.notes}
    assert OperationKind.DELETE_GROUP not in {operation.kind for operation in plan.operations}
    assert apply_plan(plan, facts, system).ok
    assert ZONE_GROUP in system.groups  # sinon le service ne demarrerait plus
    registry = read_registry(system.inspect()).value
    assert registry is not None and registry.created_items(CreatedKind.SERVICE_GROUP)


def test_drop_in_already_gone_is_forgotten_without_command(system: FakeSystem):
    before = system.snapshot()
    facts = system.inspect()
    assert apply_plan(establish_plan(facts, _detection(SERV_SERVICE), SUBJECT, AT), facts, system).ok
    system.service_groups.clear()
    facts = system.inspect()
    plan = remove_all_plan(facts, LATER, keep_zone=False, detection=_detection())
    assert OperationKind.REVOKE_SERVICE_GROUP not in {operation.kind for operation in plan.operations}
    assert apply_plan(plan, facts, system).ok
    assert system.snapshot() == before


def test_inspector_reads_drop_ins_without_following_links(tmp_path: Path):
    units = tmp_path / "systemd"
    (units / "omega-serv.service.d").mkdir(parents=True)
    (units / "omega-serv.service.d" / "omega-synchro.conf").write_text(drop_in_text(), encoding="utf-8")
    (units / "omega-serv-blog.service.d").mkdir()
    (units / "omega-serv-blog.service.d" / "omega-synchro.conf").write_text("[Service]\nNice=1\n", encoding="utf-8")
    (units / "piege.service.d").mkdir()
    target = tmp_path / "ailleurs.conf"
    target.write_text(drop_in_text(), encoding="utf-8")
    (units / "piege.service.d" / "omega-synchro.conf").symlink_to(target)
    facts = SystemZoneInspector(str(tmp_path / "zone"), unit_dir=str(units)).inspect(elevated=False)
    assert facts.service_groups == frozenset({"omega-serv"})


# ---- executeur des commandes des outils -------------------------------------------------------

def _tool(root: Path, launcher: str, mode: int = 0o755) -> Path:
    root.mkdir(parents=True)
    script = root / launcher
    script.write_text("#!/bin/sh\necho \"$@\" >> \"$(dirname \"$0\")/appels.txt\"\n", encoding="utf-8")
    script.chmod(mode)
    return script


def test_tool_runner_commands(tmp_path: Path):
    serv = _tool(tmp_path / "omega-serv", "omega-serv.sh")
    step = RepairStep(RepairKind.SERV_PERMISSIONS, str(serv.parent), "omega-serv", "omega-serv", "root", ())
    token = RepairStep(RepairKind.TOKEN, str(serv.parent), "omega-serv", "", "k", ())
    user = ToolCommandRunner(euid=1000)
    assert user.command(step)[0] == ["sudo", "-n", "--", str(serv), "service", "permissions", "--service-name",
                                     "omega-serv"]
    assert user.command(token)[0] == [str(serv), "synchro", "jeton"]
    root = ToolCommandRunner(euid=0)
    assert root.command(step)[0] == [str(serv), "service", "permissions", "--service-name", "omega-serv"]
    assert root.command(token)[0] == ["runuser", "-u", "k", "--", str(serv), "synchro", "jeton"]


def test_tool_runner_refuses_an_unsafe_launcher(tmp_path: Path):
    jail = _tool(tmp_path / "omega-jail", "omega-jail.sh", mode=0o775)
    step = RepairStep(RepairKind.JAIL_APPLY, str(jail.parent), "omega-jail", "", "root", ())
    outcome = ToolCommandRunner(euid=1000).run(step)
    assert outcome.code == 1 and "writable by group" in outcome.error
    assert not (jail.parent / "appels.txt").exists()


def test_tool_runner_runs_the_token_command_without_terminal(tmp_path: Path):
    serv = _tool(tmp_path / "omega-serv", "omega-serv.sh")
    step = RepairStep(RepairKind.TOKEN, str(serv.parent), "omega-serv", "", "k", ())
    outcome = ToolCommandRunner().run(step)
    assert outcome.ok, outcome.error
    assert (serv.parent / "appels.txt").read_text(encoding="utf-8") == "synchro jeton\n"


# ---- ligne de commande ------------------------------------------------------------------------

class _NotedRunner:
    def __init__(self) -> None:
        self.ran: list[tuple[str, ...]] = []

    def run(self, step: RepairStep) -> StepOutcome:
        self.ran.append(step.argv())
        return StepOutcome(step, 0)


def _cli_tools(system: FakeSystem) -> ZoneTools:
    return ZoneTools(inspector=system, runner=system, subject=type("S", (), {"subject": lambda self: SUBJECT})(),
                     now=lambda: LATER, interactive=lambda: True)


def test_cli_reparer_simulation_runs_nothing(system: FakeSystem, capsys):
    noted = _NotedRunner()
    tools = RepairTools(runner=noted, user=lambda: "k")
    code = run(["reparer", "--simulation"], lambda _request: _detection(), lambda _request: _sample_report(),
               zone=_cli_tools(system), repair=tools)
    out = capsys.readouterr().out
    assert code == 0 and not noted.ran and not system.ran
    assert "omega-jail remet à jour" in out and "À faire à la main" in out and "À décider" in out
    assert f"sudo {JAIL_ROOT}/omega-jail.sh --apply --update" in out
    assert "aucun outil ne sait le corriger" in out


def test_cli_reparer_runs_steps_then_proposes_establish(system: FakeSystem, capsys):
    noted = _NotedRunner()
    tools = RepairTools(runner=noted, user=lambda: "k")
    answers = iter(["o", "n"])
    code = run(["reparer"], lambda _request: _detection(SERV_SERVICE), lambda _request: _sample_report(),
               zone=_cli_tools(system), repair=tools, ask=lambda _question: next(answers))
    out = capsys.readouterr().out
    assert [argv[1:] for argv in noted.ran] == [("synchro", "jeton"), ("service", "permissions", "--service-name",
                                                                         "omega-serv"), ("--apply", "--update")]
    assert "Établir la zone neutre" in out and "Abandon" in out  # plan de la zone affiche, refuse : rien lance
    assert code == 1 and not system.ran


def test_cli_reparer_needs_terminal_or_oui(system: FakeSystem):
    tools = RepairTools(runner=_NotedRunner(), user=lambda: "k")
    zone = ZoneTools(inspector=system, runner=system, subject=_cli_tools(system).subject, now=lambda: LATER,
                     interactive=lambda: False)
    assert run(["reparer"], lambda _request: _detection(), lambda _request: _sample_report(), zone=zone,
               repair=tools) == 2



def test_new_tokens_offer_establish_even_when_the_zone_is_unverifiable():
    """Retour de l'auteur (2026-11-10) : jetons crees par `reparer` avant la reconnexion, outils jamais relies."""
    tokens = Link(LinkKind.TOKENS, "", "", (
        Check(CheckCode.TOKEN_MISSING, CheckStatus.WARNING, SERV_ROOT, "omega-serv", fix="t",
              repair=Repair(RepairKind.TOKEN, SERV_ROOT, "omega-serv")),))
    awaiting = Link(LinkKind.ZONE, "", "", (Check(CheckCode.ZONE_AWAITING_RELOGIN, CheckStatus.UNVERIFIABLE, "k"),))
    absent = Link(LinkKind.ZONE, "", "", (Check(CheckCode.ZONE_ABSENT, CheckStatus.INFO, "/var/lib/omega-synchro"),))
    plan = plan_repair(_report(tokens, awaiting), "k", as_root=False)
    assert plan.relink and plan.offers_zone and not plan.zone
    assert not plan_repair(_report(tokens, absent), "k", as_root=False).offers_zone


def test_cli_reparer_chains_establish_after_new_tokens(system: FakeSystem, capsys):
    facts = system.inspect()
    assert apply_plan(establish_plan(facts, _detection(), SUBJECT, AT), facts, system).ok
    system.ran.clear()
    tokens = Link(LinkKind.TOKENS, "", "", (
        Check(CheckCode.TOKEN_MISSING, CheckStatus.WARNING, SERV_ROOT, "omega-serv", fix="t",
              repair=Repair(RepairKind.TOKEN, SERV_ROOT, "omega-serv")),))
    awaiting = Link(LinkKind.ZONE, "", "", (Check(CheckCode.ZONE_AWAITING_RELOGIN, CheckStatus.UNVERIFIABLE, "k"),))
    noted = _NotedRunner()
    code = run(["reparer", "--oui"], lambda _request: _detection(SERV, FIRE),
               lambda _request: _report(tokens, awaiting), zone=_cli_tools(system),
               repair=RepairTools(runner=noted, user=lambda: "k"))
    out = capsys.readouterr().out
    assert code == 0 and noted.ran == [(f"{SERV_ROOT}/omega-serv.sh", "synchro", "jeton")]
    assert "Ensuite : « etablir » reliera" in out and "Établir la zone neutre" in out
    registry = read_registry(system.inspect()).value
    assert registry is not None and len(registry.installations) == 2


def test_unreadable_zone_offers_establish_without_any_other_step():
    """Cas reel du soir du 2026-11-10 : jetons deja crees, zone illisible avant reconnexion, outils pas relies :
    `reparer` ne dit plus « rien à réparer », il propose « etablir » (lecture avec sudo)."""
    awaiting = Link(LinkKind.ZONE, "", "", (Check(CheckCode.ZONE_AWAITING_RELOGIN, CheckStatus.UNVERIFIABLE, "k"),))
    plan = plan_repair(_report(awaiting), "k", as_root=False)
    assert plan.zone_unreadable and plan.offers_zone and not plan.empty and not plan.steps
