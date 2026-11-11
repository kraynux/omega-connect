# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""`etablir` / `retirer` en ligne de commande (lot D), et l'infrastructure : sudo factice, lecture de la zone.

Le vrai `sudo` n'est jamais appele : un script `sudo` factice note ce qu'il aurait lance."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from omega_lib.synchro.constants import ZONE_GROUP
from omega_lib.synchro.registry import ZoneState
from zone_fakes import AT, FIRE, FIRE_ID, SERV, SUBJECT, FakeSystem, _detection

from omega_connect.application.zone_actions import ZoneTools
from omega_connect.domain.fail2ban import Presence
from omega_connect.domain.zone import Operation, OperationKind, read_registry
from omega_connect.infrastructure.zone.inspector import SystemZoneInspector
from omega_connect.infrastructure.zone.system import SessionSubject, SudoRunner
from omega_connect.interfaces.cli.main import run


class _Subject:
    def subject(self):
        return SUBJECT


def _tools(system: FakeSystem, *, interactive: bool = True) -> ZoneTools:
    return ZoneTools(inspector=system, runner=system, subject=_Subject(), now=lambda: AT,
                     interactive=lambda: interactive)


def _run(system: FakeSystem, argv: list[str], answers: list[str] | None = None, *, interactive: bool = True,
         detection=None) -> int:
    replies = iter(answers or [])
    report = detection or _detection(SERV, FIRE)
    return run(argv, lambda request: report, zone=_tools(system, interactive=interactive),
               ask=lambda prompt: next(replies))


@pytest.fixture
def system(tmp_path: Path) -> FakeSystem:
    return FakeSystem(tmp_path)


def test_simulation_shows_every_command_and_runs_nothing(system, capsys):
    assert _run(system, ["etablir", "--simulation"]) == 0
    out = capsys.readouterr().out
    assert "sudo groupadd --system omega-synchro" in out
    assert f"sudo install -d -o root -g omega-synchro -m 2750 {system.zone}" in out
    assert "sudo gpasswd -a k omega-synchro" in out
    assert "Recopier la carte d'identité de /home/k/omega-serv" in out and "<contenu>" in out
    assert system.ran == [] and not os.path.exists(system.zone)


def test_establish_asks_then_runs_and_reports_each_step(system, capsys):
    assert _run(system, ["etablir"], ["n"]) == 1
    assert system.ran == [] and "rien n'a été lancé" in capsys.readouterr().out
    assert _run(system, ["etablir"], ["o"]) == 0
    out = capsys.readouterr().out
    assert "✔ 1/" in out and "toutes réussies" in out
    assert read_registry(system.inspect()).value.state is ZoneState.ACTIVE


def test_no_terminal_needs_explicit_consent(system, capsys):
    assert _run(system, ["etablir"], interactive=False) == 2
    assert system.ran == []
    assert _run(system, ["etablir", "--oui"], interactive=False) == 0
    assert _run(system, ["retirer", "--tout"], interactive=False) == 1
    assert "--garder-zone ou --effacer" in capsys.readouterr().err


def test_remove_all_question_keep_or_erase(system, capsys):
    before = system.snapshot()
    _run(system, ["etablir", "--oui"])
    assert _run(system, ["retirer", "--tout"], ["g", "o"]) == 0
    assert read_registry(system.inspect()).value.state is ZoneState.FROZEN
    assert _run(system, ["retirer", "--tout"], ["a"]) == 1
    assert _run(system, ["retirer", "--tout", "--effacer", "--oui"]) == 0
    assert system.snapshot() == before
    assert "rien à retirer" in (_run(system, ["retirer", "--tout", "--effacer"]) and capsys.readouterr().out)


def test_remove_tool_and_argument_errors(system, capsys):
    _run(system, ["etablir", "--oui"])
    assert _run(system, ["retirer"]) == 2
    assert _run(system, ["retirer", "omega-fire", "--tout"]) == 2
    assert _run(system, ["retirer", "omega-fire", "--effacer"]) == 2
    assert _run(system, ["retirer", "omega-fire", "--oui"]) == 1  # toujours installe
    assert "toujours installé" in capsys.readouterr().out
    assert _run(system, ["retirer", FIRE_ID[:8], "--oui"], detection=_detection(SERV)) == 0
    assert not Path(system.zone, "jetons", f"{FIRE_ID}.json").exists()


def test_failure_is_reported_with_the_recovery(system, capsys):
    system.fail_on = OperationKind.ADD_MEMBER
    assert _run(system, ["etablir", "--oui"]) == 1
    out = capsys.readouterr().out
    assert "Arrêt à l'étape « Ajouter k au groupe omega-synchro »" in out
    assert "Registre réécrit" in out


# ---- infrastructure ------------------------------------------------------------------------------

def _fake_sudo(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "sudo.log"
    script = tmp_path / "sudo"
    script.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        'for last; do :; done\n'
        'case "$*" in *" install -o "*) prev=""; for a; do [ "$a" = "$last" ] && break; prev="$a"; done; '
        f'cat "$prev" >> "{log}"; ls -l "$prev" | cut -c1-10 >> "{log}" ;; esac\n'
        'case "$*" in *groupdel*) echo "groupdel: refused" >&2; exit 8 ;; esac\n'
        "exit 0\n", encoding="utf-8")
    script.chmod(0o755)
    return script, log


def test_sudo_runner_never_uses_a_shell_and_cleans_its_temporary_file(tmp_path):
    script, log = _fake_sudo(tmp_path)
    runner = SudoRunner(sudo=str(script))
    write = Operation(OperationKind.WRITE_FILE, "/var/lib/omega-synchro/registre.json", b'{"a": 1}\n')
    assert runner.run(write).ok
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("-n -- install -o root -g omega-synchro -m 0640 ")
    assert lines[1] == '{"a": 1}' and lines[2] == "-rw-------"
    source = lines[0].split()[-2]
    assert not os.path.exists(source) and not os.path.exists(os.path.dirname(source))
    outcome = runner.run(Operation(OperationKind.DELETE_GROUP, ZONE_GROUP))
    assert outcome.code == 8 and outcome.error == "groupdel: refused"


def test_inspector_reads_the_zone_without_following_links(tmp_path):
    zone = tmp_path / "omega-synchro"
    (zone / "jetons").mkdir(parents=True)
    (zone / "registre.json").write_text("{}", encoding="utf-8")
    (zone / "jetons" / f"{'a' * 32}.json").write_text("{}", encoding="utf-8")
    (zone / "fiches").symlink_to("/etc")
    facts = SystemZoneInspector(str(zone), group="groupe-qui-n-existe-pas").inspect(elevated=False)
    assert facts.listing_known and not facts.group_exists
    assert set(facts.contents) == {"registre.json", f"jetons/{'a' * 32}.json"}
    assert facts.entry("fiches").is_symlink and facts.entry("liens").presence is Presence.MISSING
    missing = SystemZoneInspector(str(tmp_path / "rien")).inspect(elevated=False)
    assert missing.root.presence is Presence.MISSING and missing.listing_known


def test_inspector_falls_back_to_read_only_sudo_commands(tmp_path):
    zone = tmp_path / "omega-synchro"
    zone.mkdir()
    calls: list[list[str]] = []
    outputs = {
        "find": f"{zone}/registre.json\n{zone}/jetons\n".encode(),
        "stat": (f"root|omega-synchro|640|regular file|{zone}/registre.json\n"
                 f"root|omega-synchro|2750|directory|{zone}/jetons\n").encode(),
        "cat": b'{"format": "omega-registre"}',
    }

    def capture(argv):
        calls.append(list(argv))
        return 0, outputs[argv[0]], ""

    zone.chmod(0)
    try:
        inspector = SystemZoneInspector(str(zone), capture)
        assert not inspector.inspect(elevated=False).listing_known and calls == []
        facts = inspector.inspect(elevated=True)
    finally:
        zone.chmod(stat.S_IRWXU)
    assert [call[0] for call in calls] == ["find", "stat", "cat"]
    assert facts.entry("jetons").mode == 0o2750 and facts.entry("jetons").is_dir
    assert facts.contents["registre.json"].startswith(b'{"format"')


def test_session_subject_uses_sudo_user_only_under_root():
    subject = SessionSubject({"SUDO_USER": "quelquun"}).subject()
    assert subject.user != "quelquun" or os.geteuid() == 0
    assert subject.session_groups
