# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Liaison « Charge distribuee » d'omega-stress (lot L2, 2026-11-21) : regles, plan, execution, releve distant,
et un essai de bout en bout contre le VRAI omega-stress (faux ssh qui execute la commande ici, un dossier var/ par
« machine »). Jamais le vrai pare-feu, jamais sudo."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from omega_connect.app.remote_scan import stress_helper_links
from omega_connect.application.distributed_actions import DistributedTools, needs_root, plan, run_plan, unlink
from omega_connect.domain.distributed_load import (
    Accord,
    Helper,
    PilotState,
    StepWhere,
    compose,
    facts_link,
    pilot_from_json,
    relink_plan,
    shown,
)
from omega_connect.domain.fleet import AppState, RegistryRow
from omega_connect.domain.links import CheckCode, LinkKind, LinkState
from omega_connect.infrastructure.stress.runner import StressRunner, last_json

FP = "ab" * 32
PILOT = PilotState("/opt/stress", FP, 9650, (("m1", "b", "kr@b", "/home/kr/omega-stress"),), "omega-fire", False)


def _facts(pilots=(FP,), accept_all=False, readable=True):
    raw = None if not readable else json.dumps({"authorization": {
        "coordinators": list(pilots), "accept_all_targets": accept_all, "targets": []}})
    return facts_link("/home/kr/omega-stress", raw)


def _codes(link):
    return [check.code for check in link.checks]


def test_composition_des_deux_cotes() -> None:
    linked = compose(_facts(), target="kr@b", pilot=PILOT, machine="b", local_name="a")
    assert _codes(linked) == [CheckCode.STRESS_LINKED] and linked.state is LinkState.ACTIVE
    assert linked.machine == "b" and linked.peer == "a"
    assert compose(_facts(pilots=()), target="kr@c", pilot=PILOT, machine="c", local_name="a").state \
        is LinkState.ABSENT
    half = compose(_facts(pilots=()), target="kr@b", pilot=PILOT, machine="b", local_name="a")
    assert _codes(half) == [CheckCode.STRESS_HALF_LINKED] and half.state is LinkState.BROKEN
    other = compose(_facts(), target="kr@c", pilot=PILOT, machine="c", local_name="a")
    assert other.state is LinkState.BROKEN  # la machine accepte ce pilote, le pilote l'a oubliee
    closed = PilotState(PILOT.root, FP, 9650, PILOT.machines, "ufw", True)
    assert compose(_facts(), target="kr@b", pilot=closed, machine="b", local_name="a").state is LinkState.DEGRADED
    nft = PilotState(PILOT.root, FP, 9650, PILOT.machines, "nftables", False, True)
    assert CheckCode.STRESS_NEEDS_OMEGA_FIRE in _codes(
        compose(_facts(), target="kr@b", pilot=nft, machine="b", local_name="a"))
    assert compose(_facts(), target="kr@b", pilot=None, machine="b", local_name="a").state is LinkState.ABSENT
    assert compose(_facts(readable=False), target="kr@b", pilot=PILOT, machine="b",
                   local_name="a").state is LinkState.UNVERIFIABLE


def test_plan_relier_et_delier() -> None:
    helpers = [Helper("b", "kr@b", "/home/kr/omega-stress", "m1"), Helper("c", "kr@c", "/srv/stress")]
    steps = relink_plan(PILOT, helpers, Accord.ALL, [["/opt/fire/omega-fire.sh", "port", "ouvrir"]])
    kinds = [(s.where, s.helper, s.argv[1:3] if s.where is not StepWhere.ROOT else s.argv[1:2]) for s in steps]
    assert kinds[0] == (StepWhere.LOCAL, "b", ("coordinateur", "retirer-machine"))  # ancien acces remplace
    assert kinds[1] == (StepWhere.LOCAL, "b", ("coordinateur", "ajouter-machine"))
    assert kinds[2] == (StepWhere.REMOTE, "b", ("worker", "relier"))
    assert [s.where for s in steps[-2:]] == [StepWhere.ROOT, StepWhere.LOCAL]
    assert "--fait" in steps[-1].argv and needs_root(steps)
    assert all("secret" not in shown(step) for step in steps)
    assert shown(steps[2]).startswith("ssh kr@b /home/kr/omega-stress/omega-stress.sh worker relier")
    assert shown(steps[-2]).startswith("sudo ")
    assert not needs_root(relink_plan(PILOT, helpers, Accord.ASK))


class FakeRunner:
    def __init__(self, fail_remote_for: str = "") -> None:
        self.calls: list[tuple[str, tuple[str, ...], bytes]] = []
        self.fail = fail_remote_for

    def local(self, argv, data=b""):
        self.calls.append(("local", tuple(argv), data))
        if "ajouter-machine" in argv:
            return 0, json.dumps({"id": "new-id", "secret": "S3CRET", "fingerprint": FP, "port": 9650}).encode(), ""
        if "--commandes" in argv:
            return 0, json.dumps({"backend": "ufw", "commands": [["ufw", "allow"]]}).encode(), ""
        return 0, b"", ""

    def remote(self, target, argv, data=b""):
        self.calls.append((target, tuple(argv), data))
        return (1, b"", "refused") if target == self.fail else (0, b"", "")


class FakeSudo:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def capture(self, argv):
        self.calls.append(tuple(argv))
        return 0, b"", ""


def test_execution_du_plan() -> None:
    runner = FakeRunner(fail_remote_for="kr@c")
    rescanned: list[str] = []
    tools = DistributedTools(runner, lambda: PILOT, lambda host: "192.168.1.7", rescanned.append)
    pilot = PilotState(PILOT.root, FP, 9650, PILOT.machines, "ufw", True)
    steps = plan(pilot, [Helper("b", "kr@b", "/b"), Helper("c", "kr@c", "/c")], Accord.ASK, runner)
    sudo = FakeSudo()
    results = run_plan(steps, tools, sudo)
    relier = next(call for call in runner.calls if call[0] == "kr@b")
    assert "192.168.1.7:9650" in relier[1] and "new-id" in relier[1]
    assert relier[2] == b"S3CRET\n" and "S3CRET" not in " ".join(relier[1])  # secret par l'entree standard
    assert sudo.calls == [("ufw", "allow")]
    assert [r.ok for r in results if r.helper == "c"] == [True, False]
    assert all(r.ok for r in results if r.helper != "c")
    assert rescanned == ["kr@b", "kr@c"]
    assert not run_plan(steps, tools, None)[-2].ok  # pas de root sans sudo -v prealable


def test_delier() -> None:
    runner = FakeRunner()
    tools = DistributedTools(runner, lambda: PILOT, lambda host: "x")
    results = unlink(PILOT, Helper("b", "kr@b", "/b", "m1"), tools)
    assert all(r.ok for r in results)
    assert [c[1][1:3] for c in runner.calls] == [("worker", "retirer-pilote"), ("coordinateur", "retirer-machine")]


def test_releve_distant(tmp_path: Path) -> None:
    root = tmp_path / "omega-stress"
    root.mkdir()
    launcher = root / "omega-stress.sh"
    launcher.write_text("#!/bin/sh\necho '{\"authorization\": null}'\n")
    launcher.chmod(0o755)
    row = RegistryRow("b", "omega-stress", str(root), "", "", "2.0.0", AppState.DETECTED)
    (link,) = stress_helper_links([row, row])
    assert link.kind is LinkKind.DISTRIBUTED_LOAD
    assert json.loads(link.checks[0].detail) == {"authorization": None}
    (missing,) = stress_helper_links([RegistryRow("b", "omega-stress", str(tmp_path / "x"), "", "", "",
                                                  AppState.DETECTED)])
    assert missing.checks[0].detail == ""


STRESS = Path.home() / "DEV" / "STRESS" / "omega-stress"


@pytest.mark.skipif(not (STRESS / ".venv").is_dir(), reason="omega-stress de developpement absent")
def test_bout_en_bout_avec_le_vrai_omega_stress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pilote et machine qui aide = le vrai omega-stress, chacun dans son var/ ; faux ssh qui execute ici."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "ssh").write_text(
        "#!/usr/bin/env bash\n"
        'while [ "${1:-}" = "-o" ]; do shift 2; done\n'
        '[ "$1" = "--" ] && shift\n'
        'export OMEGA_STRESS_VAR_DIR="$FAKE_ROOT/machines/$1"\n'
        "shift\n"
        'exec bash -c "$*"\n')
    (fake / "ssh").chmod(0o755)
    monkeypatch.setenv("FAKE_ROOT", str(tmp_path))
    monkeypatch.setenv("PATH", f"{fake}:{os.environ['PATH']}")
    pilot_var = tmp_path / "pilote"
    launcher = str(STRESS / "omega-stress.sh")

    class PilotRunner(StressRunner):
        def local(self, argv, data=b""):
            env = {**os.environ, "OMEGA_STRESS_VAR_DIR": str(pilot_var)}
            done = subprocess.run(list(argv), input=data, capture_output=True, env=env, timeout=60, check=False)
            return done.returncode, done.stdout, done.stderr.decode()[-200:]

    runner = PilotRunner()

    def read_pilot():
        code, output, _ = runner.local([launcher, "coordinateur", "etat", "--format", "json"])
        return pilot_from_json(str(STRESS), last_json(output)) if code == 0 else None

    tools = DistributedTools(runner, read_pilot, lambda host: "127.0.0.1")
    pilot = read_pilot()
    assert pilot is not None
    steps = relink_plan(pilot, [Helper("b", "kr@b", str(STRESS))], Accord.ALL)
    results = run_plan(steps, tools, None)
    assert all(r.ok for r in results), results
    code, output, _ = runner.remote("kr@b", [launcher, "worker", "etat", "--format", "json"])
    facts = facts_link(str(STRESS), json.dumps(last_json(output)))
    after = read_pilot()
    assert after is not None and after.machine_for("kr@b", str(STRESS))
    link = compose(facts, target="kr@b", pilot=after, machine="b", local_name="a")
    assert CheckCode.STRESS_LINKED in _codes(link)
    assert link.checks[0].detail == "tout"
    assert all(r.ok for r in unlink(after, Helper("b", "kr@b", str(STRESS),
                                                  after.machine_for("kr@b", str(STRESS))), tools))
    final = read_pilot()
    assert final is not None and not final.machines


async def test_ecran_charge_distribuee() -> None:
    """Ecran ouvert depuis Synchronisation : machines du reseau qui ont omega-stress, cases, plan affiche."""
    from types import SimpleNamespace

    from omega_lib.terminal.models import RenderProfile

    from omega_connect.application.remote_actions import RemoteTools
    from omega_connect.domain.parc import MachineEntry
    from omega_connect.domain.remote import RemoteFailure
    from omega_connect.interfaces.tui.app import OmegaConnectApp
    from omega_connect.interfaces.tui.screens.confirm import ConfirmScreen
    from omega_connect.interfaces.tui.screens.distributed_load import DistributedLoadScreen

    link = compose(_facts(pilots=()), target="kr@c", pilot=PILOT, machine="c", local_name="a")
    entry = MachineEntry("c", False, "", (), "fp-c", ("c",), "kr@c", True, (link,))
    parc = SimpleNamespace(load=lambda: (entry,), save=lambda _e: None)
    remote = RemoteTools(scanner=SimpleNamespace(scan=lambda _t: (RemoteFailure.UNREACHABLE, "")),
                         parc=parc)  # type: ignore[arg-type]
    tools = DistributedTools(FakeRunner(), lambda: PILOT, lambda host: "x")
    from tests.test_dashboard import _report

    app = OmegaConnectApp(verify=_report, version="t", render_profile=RenderProfile.COMPLETE,
                          refresh_seconds=3600, splash=False)
    async with app.run_test(size=(140, 50)) as pilot:
        screen = DistributedLoadScreen(tools=tools, remote=remote, sudo=FakeSudo())
        await app.push_screen(screen)
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        table = screen.query_one("#distributed-table")
        assert table.row_count == 1
        screen.action_choose_row()
        await pilot.pause()
        assert not screen.query_one("#link").disabled
        await pilot.click("#link")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)


async def test_ecran_deux_installations_et_ancienne_version() -> None:
    """Retour de l'auteur (2026-11-21) : craftdark a deux omega-stress, dont un ancien -> plantage DuplicateKey.
    Une ligne par installation ; l'ancienne version est signalee et ne se coche pas."""
    from types import SimpleNamespace

    from omega_lib.terminal.models import RenderProfile
    from tests.test_dashboard import _report

    from omega_connect.application.remote_actions import RemoteTools
    from omega_connect.domain.parc import MachineEntry
    from omega_connect.domain.remote import RemoteFailure
    from omega_connect.interfaces.tui.app import OmegaConnectApp
    from omega_connect.interfaces.tui.screens.distributed_load import DistributedLoadScreen

    new = compose(facts_link("/home/kr/omega-stress", json.dumps({"authorization": None})), target="kr@c",
                  pilot=PILOT, machine="craftdark", local_name="a")
    old = compose(facts_link("/home/kr/omega-stress-old", None, old_version="1.6.0"), target="kr@c",
                  pilot=PILOT, machine="craftdark", local_name="a")
    entry = MachineEntry("craftdark", False, "", (), "fp-c", ("c",), "kr@c", True, (new, old))
    remote = RemoteTools(scanner=SimpleNamespace(scan=lambda _t: (RemoteFailure.UNREACHABLE, "")),
                         parc=SimpleNamespace(load=lambda: (entry,), save=lambda _e: None))  # type: ignore[arg-type]
    app = OmegaConnectApp(verify=_report, version="t", render_profile=RenderProfile.COMPLETE,
                          refresh_seconds=3600, splash=False)
    async with app.run_test(size=(140, 50)) as pilot:
        screen = DistributedLoadScreen(tools=DistributedTools(FakeRunner(), lambda: PILOT, lambda h: "x"),
                                       remote=remote, sudo=FakeSudo(), preselect=entry.label)
        await app.push_screen(screen)
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        table = screen.query_one("#distributed-table")
        assert table.row_count == 2
        chosen = {(entry.label, "/home/kr/omega-stress")}
        assert screen._chosen == chosen  # l'ancienne n'est pas cochee
        table.move_cursor(row=1)
        screen.action_choose_row()
        assert screen._chosen == chosen
        assert "1.6.0" in str(table.get_row_at(1)[3])


def test_scan_ne_lance_jamais_une_version_trop_ancienne(tmp_path: Path) -> None:
    root = tmp_path / "old"
    root.mkdir()
    marker = tmp_path / "lance"
    launcher = root / "omega-stress.sh"
    launcher.write_text(f"#!/bin/sh\ntouch {marker}\n")
    launcher.chmod(0o755)
    (link,) = stress_helper_links([RegistryRow("b", "omega-stress", str(root), "", "", "1.6.0", AppState.DETECTED)])
    assert link.instance == "1.6.0" and not marker.exists()


def test_copie_embarquee_par_omega_suite_aide_si_seule() -> None:
    """Decision de l'auteur (2026-11-22) : l'omega-stress d'omega-suite aide comme un autonome ; s'il y a aussi un
    omega-stress autonome sur la machine, c'est lui qui aide (une seule aide par machine)."""
    from omega_connect.domain.distributed_load import helper_roots

    suite = "/home/kr/omega-suite"
    embedded = RegistryRow("c", "omega-stress", f"{suite}/vendor/omega-stress", "", "", "2.0.0", AppState.DETECTED,
                           (), suite, "1.7.0")
    alone = RegistryRow("c", "omega-stress", "/home/kr/omega-stress", "", "", "2.0.0", AppState.LINKED)
    assert helper_roots([embedded]) == {f"{suite}/vendor/omega-stress": "2.0.0"}
    assert helper_roots([embedded, alone]) == {"/home/kr/omega-stress": "2.0.0"}
    assert helper_roots([RegistryRow("c", "omega-fire", "/f", "", "", "3.6.2", AppState.LINKED)]) == {}


def test_omega_stress_toujours_lance_depuis_son_dossier(tmp_path: Path) -> None:
    """Essai reel (2026-11-21) : lance depuis le dossier d'omega-connect, omega-stress ecrivait la liaison
    dans le var/ de celui-ci ; par SSH, dans ~/var. Le lanceur est maintenant toujours lance de son dossier."""
    from omega_connect.infrastructure.stress.runner import _folder

    root = tmp_path / "omega-stress"
    root.mkdir()
    launcher = root / "omega-stress.sh"
    launcher.write_text("#!/bin/sh\npwd\n")
    launcher.chmod(0o755)
    code, output, _error = StressRunner().local([str(launcher), "coordinateur", "etat"])
    assert code == 0 and output.decode().strip() == str(root)
    assert _folder(["/home/kr/omega-stress/omega-stress.sh", "worker"]) == "/home/kr/omega-stress"
    assert _folder(["ufw", "allow"]) == ""


def test_compte_rendu_du_pare_feu() -> None:
    """Retour de l'auteur (2026-11-21) : « qui a ouvert le port, quelle regle, quel pare-feu »."""
    from omega_connect.application.distributed_actions import firewall_lines

    answer = json.dumps({"ok": True, "port": 9650, "lignes": [
        {"cible": "nftables", "source": "192.168.1.0/24", "etat": "ajoutee", "detail": "#12"},
        {"cible": "ufw", "source": "192.168.1.0/24", "etat": "deja", "detail": ""}]}).encode()
    assert firewall_lines(answer, ["omega-fire.sh", "port", "ouvrir"]) == (
        "nftables · 192.168.1.0/24 · ajoutee · #12", "ufw · 192.168.1.0/24 · deja")
    assert firewall_lines(b"Rule added", ["ufw", "allow", "from", "x"]) == ("ufw allow from x",)

    class Sudo(FakeSudo):
        def capture(self, argv):
            self.calls.append(tuple(argv))
            return 0, answer, ""

    runner = FakeRunner()
    tools = DistributedTools(runner, lambda: PILOT, lambda host: "x")
    pilot = PilotState(PILOT.root, FP, 9650, PILOT.machines, "omega-fire", True)
    results = run_plan(relink_plan(pilot, [], Accord.ASK, [["omega-fire.sh", "port", "ouvrir"]]), tools, Sudo())
    assert results[0].firewall[0].endswith("#12")
    fait = next(call for call in runner.calls if "--fait" in call[1])
    assert "--par" in fait[1] and json.loads(fait[2])["outputs"][0] == answer.decode()
