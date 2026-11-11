# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""`verifier` de bout en bout (lot B) : fausses installations, faux /etc/fail2ban, jamais le vrai systeme.

Les fichiers de fail2ban et le script du pont appartiennent a root sur une vraie machine ; ici ils sont crees
sous le compte des tests, puis presentes comme appartenant a root (`_AsRoot`) quand le test le demande."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import make_installation

from omega_connect.app.main import build_detect, build_verify
from omega_connect.application.verify_links import verify_links
from omega_connect.domain.fail2ban import ConfigText, Fail2banSnapshot, FileFacts
from omega_connect.domain.links import CheckCode, LinkKind, LinkState, RepairKind, VerificationReport
from omega_connect.infrastructure.verification.files import Fail2banFilesReader, StatFileProbe, file_facts
from omega_connect.interfaces.cli.main import DetectRequest, run
from omega_connect.interfaces.cli.verification_view import check_text, render_text

NEVER = ["100.64.0.0/10", "10.0.0.0/8"]
LOGS = {"waf-log": "var/log/waf-alerts.log", "access-log": "var/log/access.log",
        "active-defense-log": "var/log/active-defense-enriched.jsonl",
        "riposte-decisions": "var/log/riposte-decisions.jsonl",
        "magnet-alerts-log": "var/log/magnet-alerts.log", "magnet-blocklist-log": "var/log/magnet-blocklist.log",
        "blocklist": "var/lib/waf/blocklist.json"}


class _AsRoot:
    """Presente certains fichiers comme root:root (stat reel sinon)."""

    def __init__(self, paths: set[str]) -> None:
        self.paths = paths

    def facts(self, path: str) -> FileFacts:
        facts = file_facts(path)
        return replace(facts, owner="root", group="root") if path in self.paths or any(
            path.startswith(prefix + "/") for prefix in self.paths) else facts


class _Fail2banAsRoot:
    def __init__(self, directory: Path) -> None:
        self.reader = Fail2banFilesReader(str(directory))

    def read(self) -> Fail2banSnapshot:
        snapshot = self.reader.read()

        def root(facts: FileFacts) -> FileFacts:
            return replace(facts, owner="root", group="root")

        return replace(
            snapshot,
            jail_files=tuple(ConfigText(root(item.facts), item.text) for item in snapshot.jail_files),
            filter_files=tuple(root(item) for item in snapshot.filter_files),
            action_files=tuple(ConfigText(root(item.facts), item.text) for item in snapshot.action_files),
        )


class FakeMachine:
    def __init__(self, fake_system: dict[str, Path], tmp_path: Path) -> None:
        self.system = fake_system
        self.fail2ban = tmp_path / "fail2ban"
        for sub in ("jail.d", "filter.d", "action.d"):
            (self.fail2ban / sub).mkdir(parents=True)
        self.bridge = tmp_path / "usr-local-lib-omega-jail" / "omega-jail-tailscale-bridge.py"
        self.bridge.parent.mkdir(parents=True)
        self.bridge.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        self.bridge.chmod(0o755)
        self.jail_root = make_installation(fake_system["home"] / "omega-jail", "omega-jail", token_id="c" * 32)
        self.group = ""

    def serv(self, root: Path, *, instance: str = "omega-serv", files: tuple[str, ...] = ("waf-log", "access-log",
             "blocklist"), never: list[str] | None = NEVER, waf_mode: str = "block",
             capabilities: dict[str, str] | None = None, token_id: str = "a" * 32) -> Path:
        for key in files:
            path = root / LOGS[key]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
            path.chmod(0o660 if key == "blocklist" else 0o664)
            self.group = file_facts(str(path)).group
        sheet = {
            "format": "omega-fiche", "schema_version": 1, "tool": "omega-serv", "version": "2.6.1",
            "installation_id": token_id, "instance": instance, "generated_at": "2026-11-10T14:05:00Z",
            "capabilities": capabilities or {"waf": "active", "magnet": "disabled"},
            "service": {"manager": "systemd", "unit": f"{instance}.service", "user": "omega-serv",
                        "group": self.group, "state": "active"},
            "files": {key: {"path": str(root / LOGS[key]), "contract": None} for key in files},
            "partial": False, "exposure": "direct", "waf_mode": waf_mode,
        }
        if never is not None:
            sheet["never_auto_block"] = never
        make_installation(root, "omega-serv", token_id=token_id, sheet=sheet)
        (root / "var" / "omega-jeton.json").chmod(0o644)
        (root / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
        (root / ".venv" / "bin" / "omega-serv").write_text("", encoding="utf-8")
        return root

    def jail(self, name: str, logpath: Path | str, *, ignoreip: list[str] = NEVER,
             bridge: str | None = "omega-jail-tailscale-bridge", with_filter: bool = True) -> None:
        text = (f"# Genere par Omega-Jail\n[{name}]\nenabled = true\nfilter = omega-jail-{name}\n"
                f"logpath = {logpath}\nmaxretry = 3\nfindtime = 600\nbantime = 43200\n"
                f"ignoreip = {' '.join(ignoreip)}\n")
        if bridge:
            text += f"action = %(action_)s\n          {bridge}\n"
        (self.fail2ban / "jail.d" / f"omega-jail-{name}.conf").write_text(text, encoding="utf-8")
        if with_filter:
            (self.fail2ban / "filter.d" / f"omega-jail-{name}.conf").write_text(
                "[Definition]\nfailregex = x <HOST>\n", encoding="utf-8")

    def action(self, name: str, serv_root: Path | str, exempt: list[str] = NEVER) -> None:
        servcli = f"{serv_root}/.venv/bin/omega-serv" if serv_root else ""
        line = (f'/usr/bin/python3 {self.bridge} --ip=<ip> --mode=ban --servcli="{servcli}" --servconfig="" '
                f'--cidr="100.64.0.0/10" --exempt="{",".join(exempt)}" --jail=<name> --bantime=<bantime>')
        (self.fail2ban / "action.d" / f"{name}.conf").write_text(
            f"[Definition]\nactionstart =\nactionban = {line}\nactionunban = {line}\n", encoding="utf-8")

    def verify(self, *, root_owned: tuple[Path, ...] = ()) -> VerificationReport:
        detect = build_detect(home=self.system["home"], systemd_dir=str(self.system["systemd"]),
                              openrc_dir=str(self.system["openrc"]), runit_dir=str(self.system["runit"]),
                              srv_dir=str(self.system["srv"]), mounts_file=str(self.system["mounts"]))
        probe = _AsRoot({str(self.bridge)} | {str(path) for path in root_owned})
        return verify_links(detect(DetectRequest([], with_sheets=True)), _Fail2banAsRoot(self.fail2ban), probe)


def _link(report: VerificationReport, kind: LinkKind, instance: str = "omega-serv"):
    return next(link for link in report.links if link.kind is kind and link.instance == instance)


def _codes(link) -> list[CheckCode]:
    return [check.code for check in link.checks]


@pytest.fixture
def machine(fake_system, tmp_path) -> FakeMachine:
    return FakeMachine(fake_system, tmp_path)


def _standard(machine: FakeMachine) -> Path:
    root = machine.serv(machine.system["home"] / "omega-serv")
    machine.jail("omega-serv-waf-block", root / LOGS["waf-log"])
    machine.jail("omega-serv-scan", root / LOGS["access-log"])
    machine.action("omega-jail-tailscale-bridge", root)
    return root


def test_every_link_active(machine):
    _standard(machine)
    report = machine.verify()
    states = {(link.kind, link.instance): link.state for link in report.links}
    assert states == {
        (LinkKind.SERV_LOGS, "omega-serv"): LinkState.ACTIVE,
        (LinkKind.MAGNET_LOGS, "omega-serv"): LinkState.ABSENT,
        (LinkKind.BRIDGE, "omega-serv"): LinkState.ACTIVE,
        (LinkKind.PROTECTED_LIST, "omega-serv"): LinkState.ACTIVE,
        (LinkKind.BLOCKLIST, "omega-serv"): LinkState.ACTIVE,
        (LinkKind.FAIL2BAN_FILES, ""): LinkState.ACTIVE,
        (LinkKind.TOKENS, ""): LinkState.ACTIVE,
    }
    assert not report.has_problems
    assert _codes(_link(report, LinkKind.MAGNET_LOGS)) == [CheckCode.FUNCTION_OFF]


def test_missing_log_and_filter_break_the_link(machine):
    root = _standard(machine)
    (root / LOGS["waf-log"]).unlink()
    (machine.fail2ban / "filter.d" / "omega-jail-omega-serv-scan.conf").unlink()
    link = _link(machine.verify(), LinkKind.SERV_LOGS)
    assert link.state is LinkState.BROKEN
    missing = next(check for check in link.checks if check.code is CheckCode.JAIL_LOG_MISSING)
    assert missing.fix == f"{machine.jail_root}/omega-jail.sh --apply --update"
    assert CheckCode.JAIL_FILTER_MISSING in _codes(link)


def test_jail_reading_another_file_and_uncovered_function(machine):
    root = machine.serv(machine.system["home"] / "omega-serv",
                        files=("waf-log", "access-log", "active-defense-log", "blocklist"))
    other = root / "var" / "log" / "ancien-waf.log"
    other.write_text("", encoding="utf-8")
    machine.jail("omega-serv-waf-block", other)
    machine.jail("omega-serv-scan", root / LOGS["access-log"])
    machine.action("omega-jail-tailscale-bridge", root)
    link = _link(machine.verify(), LinkKind.SERV_LOGS)
    assert link.state is LinkState.BROKEN
    assert CheckCode.JAIL_PATH_DIFFERS in _codes(link)
    uncovered = [check for check in link.checks if check.code is CheckCode.FUNCTION_NOT_COVERED]
    # waf-log : deja signale par JAIL_PATH_DIFFERS (le jail existe mais lit un autre fichier), jamais deux fois.
    assert [check.subject for check in uncovered] == ["active-defense-log"]


def test_riposte_jail_of_second_instance_relaying_to_the_first(machine):
    main = _standard(machine)
    blog = machine.serv(machine.system["srv"] / "blog", instance="omega-serv-blog", token_id="b" * 32,
                        files=("access-log", "riposte-decisions", "blocklist"),
                        capabilities={"waf": "active", "riposte": "active"})
    machine.jail("omega-serv-blog-riposte-1h", blog / LOGS["riposte-decisions"])  # ancien bug : pont de main
    report = machine.verify()
    bridge = _link(report, LinkKind.BRIDGE, "omega-serv-blog")
    assert bridge.state is LinkState.BROKEN
    wrong = next(check for check in bridge.checks if check.code is CheckCode.BRIDGE_WRONG_TARGET)
    assert wrong.subject == "omega-serv-blog-riposte-1h" and wrong.detail == str(main)
    assert CheckCode.BRIDGE_ACTION_MISSING in _codes(bridge)
    machine.action("omega-jail-tailscale-bridge-omega-serv-blog", blog)
    machine.jail("omega-serv-blog-riposte-1h", blog / LOGS["riposte-decisions"],
                 bridge="omega-jail-tailscale-bridge-omega-serv-blog")
    assert _link(machine.verify(), LinkKind.BRIDGE, "omega-serv-blog").state is LinkState.ACTIVE


def test_protected_list_differs_or_unknown(machine):
    root = machine.serv(machine.system["home"] / "omega-serv")
    machine.jail("omega-serv-waf-block", root / LOGS["waf-log"], ignoreip=["100.64.0.0/10", "192.0.2.1"])
    machine.action("omega-jail-tailscale-bridge", root)
    link = _link(machine.verify(), LinkKind.PROTECTED_LIST)
    assert link.state is LinkState.DEGRADED
    differs = next(check for check in link.checks if check.code is CheckCode.PROTECTED_JAIL_DIFFERS)
    assert differs.detail == "+192.0.2.1/32 -10.0.0.0/8"
    machine.serv(root, never=None)  # omega-serv anterieur a la liste dans la fiche
    assert _link(machine.verify(), LinkKind.PROTECTED_LIST).state is LinkState.UNVERIFIABLE


def test_blocklist_rights(machine):
    root = _standard(machine)
    blocklist = root / LOGS["blocklist"]
    report = machine.verify(root_owned=(blocklist,))
    link = _link(report, LinkKind.BLOCKLIST)
    assert link.state is LinkState.BROKEN and _codes(link) == [CheckCode.BLOCKLIST_ROOT_OWNED]
    # Lot E : la commande d'omega-serv, jamais un chown d'omega-connect sur son fichier.
    assert link.checks[0].fix == f"{root}/omega-serv.sh service permissions --service-name omega-serv"
    assert link.checks[0].repair is not None and link.checks[0].repair.kind is RepairKind.SERV_PERMISSIONS
    blocklist.chmod(0o600)  # cas reel du 2026-11-06 : 600 via omega-jail, plus de 451
    link = _link(machine.verify(), LinkKind.BLOCKLIST)
    assert _codes(link) == [CheckCode.BLOCKLIST_MODE] and not link.checks[0].fix_account
    assert link.checks[0].repair is not None and link.checks[0].repair.root == str(root)
    blocklist.unlink()
    assert _codes(_link(machine.verify(), LinkKind.BLOCKLIST)) == [CheckCode.BLOCKLIST_NOT_CREATED]


def test_bridge_script_and_fail2ban_files_must_belong_to_root(machine):
    _standard(machine)
    report = verify_links(
        build_detect(home=machine.system["home"], systemd_dir=str(machine.system["systemd"]),
                     openrc_dir=str(machine.system["openrc"]), runit_dir=str(machine.system["runit"]),
                     srv_dir=str(machine.system["srv"]), mounts_file=str(machine.system["mounts"]))(
            DetectRequest([], with_sheets=True)),
        Fail2banFilesReader(str(machine.fail2ban)), StatFileProbe())
    assert CheckCode.BRIDGE_SCRIPT_UNSAFE in _codes(_link(report, LinkKind.BRIDGE))
    files = _link(report, LinkKind.FAIL2BAN_FILES, "")
    assert files.state is LinkState.BROKEN and set(_codes(files)) == {CheckCode.FILE_UNSAFE}


def test_magnet_in_log_only_mode(machine):
    root = machine.serv(machine.system["home"] / "omega-serv", waf_mode="log-only",
                        files=("waf-log", "access-log", "magnet-alerts-log", "magnet-blocklist-log", "blocklist"),
                        capabilities={"waf": "active", "magnet": "active"})
    machine.jail("omega-waf-magnet-alerts", root / LOGS["magnet-alerts-log"])
    machine.jail("omega-waf-blocklist-sync", root / LOGS["magnet-blocklist-log"])
    machine.action("omega-jail-tailscale-bridge", root)
    link = _link(machine.verify(), LinkKind.MAGNET_LOGS)
    assert link.state is LinkState.DEGRADED and CheckCode.MAGNET_LOG_ONLY in _codes(link)
    # Decision de l'auteur (2026-11-10) : degrade, message explicite, aucune correction proposee.
    check = next(check for check in link.checks if check.code is CheckCode.MAGNET_LOG_ONLY)
    text = check_text(check)
    assert "mode log-only" in text and "omega-waf-magnet-alerts" in text and "posé par omega-jail" in text
    assert "au niveau réseau" in text and "ne se substitue pas à fail2ban" in text and not check.fix


def test_orphan_jail_and_bridge_to_vanished_instance(machine):
    _standard(machine)
    gone = machine.system["srv"] / "disparue"
    machine.jail("omega-serv-active-defense", gone / LOGS["active-defense-log"])
    machine.action("omega-jail-tailscale-bridge-disparue", gone)
    report = machine.verify()
    orphans = [link for link in report.links if link.instance == "" and link.kind is LinkKind.SERV_LOGS]
    assert orphans and orphans[0].state is LinkState.BROKEN
    assert {CheckCode.JAIL_NO_INSTANCE, CheckCode.JAIL_LOG_MISSING} <= set(_codes(orphans[0]))
    stray = next(link for link in report.links if link.instance == "" and link.kind is LinkKind.BRIDGE)
    assert _codes(stray) == [CheckCode.BRIDGE_TARGET_MISSING]


def test_damaged_files_and_unknown_action(machine):
    root = _standard(machine)
    machine.jail("omega-serv-scan", root / LOGS["access-log"], bridge="omega-jail-tailscale-bridge-inconnue")
    (machine.fail2ban / "jail.d" / "omega-jail-casse.conf").write_text("[casse\n", encoding="utf-8")
    (machine.fail2ban / "action.d" / "omega-jail-tailscale-bridge-vide.conf").write_text("x\n", encoding="utf-8")
    report = machine.verify()
    assert CheckCode.BRIDGE_UNKNOWN_ACTION in _codes(_link(report, LinkKind.BRIDGE))
    files = _link(report, LinkKind.FAIL2BAN_FILES, "")
    assert {CheckCode.JAIL_FILE_DAMAGED, CheckCode.BRIDGE_ACTION_DAMAGED} <= set(_codes(files))


def test_without_fail2ban_or_omega_jail(machine, tmp_path):
    root = machine.serv(machine.system["home"] / "omega-serv")
    detect = build_detect(home=machine.system["home"], systemd_dir=str(machine.system["systemd"]),
                          openrc_dir=str(machine.system["openrc"]), runit_dir=str(machine.system["runit"]),
                          srv_dir=str(machine.system["srv"]), mounts_file=str(machine.system["mounts"]))
    report = build_verify(detect, fail2ban_dir=str(tmp_path / "pas-de-fail2ban"))(DetectRequest([], True))
    link = _link(report, LinkKind.SERV_LOGS)
    assert link.state is LinkState.ABSENT and _codes(link) == [CheckCode.FAIL2BAN_NOT_INSTALLED]
    assert _link(report, LinkKind.BLOCKLIST).state is LinkState.ACTIVE
    assert root.exists()


def test_tokens(machine):
    _standard(machine)
    fire = make_installation(machine.system["home"] / "omega-fire", "omega-fire",
                             sheet={"format": "omega-fiche", "schema_version": 1, "tool": "omega-fire",
                                    "version": "3.6.0", "installation_id": "", "instance": "omega-fire",
                                    "generated_at": "2026-11-10T14:05:00Z", "partial": True})
    (fire / "src" / "omega_fire" / "core").mkdir(parents=True)
    (fire / "src" / "omega_fire" / "core" / "constants.py").write_text('OMEGA_FIRE_VERSION = "3.6.1"\n',
                                                                      encoding="utf-8")
    (fire / ".venv" / "bin").mkdir(parents=True)  # installation complete : seule la carte a ete effacee
    (fire / ".venv" / "bin" / "activate").write_text("", encoding="utf-8")
    (fire / ".venv" / "bin" / "python").symlink_to("/usr/bin/python3")
    make_installation(machine.system["home"] / "omega-fire-ancien", "omega-fire", exit_code=2)
    link = _link(machine.verify(), LinkKind.TOKENS, "")
    by_subject = {check.subject: check for check in link.checks}
    assert by_subject[str(fire)].code is CheckCode.TOKEN_MISSING
    assert by_subject[str(fire)].fix == f"{fire}/omega-fire.sh synchro jeton" and by_subject[str(fire)].fix_account
    assert by_subject[str(machine.system["home"] / "omega-fire-ancien")].code is CheckCode.TOKEN_TOOL_TOO_OLD
    assert link.state is LinkState.DEGRADED


def test_cli_text_json_and_exit_code(machine, capsys):
    root = _standard(machine)
    detect = build_detect(home=machine.system["home"], systemd_dir=str(machine.system["systemd"]),
                          openrc_dir=str(machine.system["openrc"]), runit_dir=str(machine.system["runit"]),
                          srv_dir=str(machine.system["srv"]), mounts_file=str(machine.system["mounts"]))
    verify = build_verify(detect, fail2ban_dir=str(machine.fail2ban))
    # Fichiers de fail2ban et script du pont non possedes par root dans les tests : liens casses, code 1.
    assert run(["verifier", "--format", "json"], detect, verify) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "omega-connect-verification" and payload["schema_version"] == 1
    assert payload["detection"]["format"] == "omega-connect-detection"
    kinds = {(item["kind"], item["instance"]) for item in payload["links"]}
    assert ("serv-logs-to-jails", "omega-serv") in kinds
    assert run(["verifier"], detect, verify) == 1
    text = capsys.readouterr().out
    assert f"omega-serv « omega-serv » — {root}" in text and "à réparer (bloquant)" in text
    assert "correction : " in text and "omega-jail.sh --apply --update" in text and "par « reparer »" in text
    assert "contrôle(s) conforme(s)" in text
    assert "contrôle(s) conforme(s)" not in render_text(machine.verify(), with_details=True)
