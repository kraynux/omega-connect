# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Programme envoye par omega-connect sur une machine distante (lots R2 et R3). Rien n'y est installe : il arrive en
memoire (scan, plan) ou dans un dossier prive efface a la fin (lancement), et n'importe jamais Textual ni rich.

- `scan` (par defaut) : lecture seule, voir `remote_scan` ;
- `plan` : lecture seule, sans sudo : outils trop anciens, plan de `reparer` et de `synchroniser` tels que la ligne
  de commande les affiche ; un document JSON (`omega-connect-plan-distant` v1) ;
- `run <dossier>` : dans un terminal (ssh -t), la personne voit tout et tape elle-meme son mot de passe : mises a
  jour (`updates.json`, archives deja verifiees), puis `reparer --oui`, puis `synchroniser --oui` ; resultat ecrit
  dans `<dossier>/result.json` (`omega-connect-resultat-distant` v1), relu puis efface par omega-connect."""
from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import socket
import sys
from pathlib import Path

from omega_connect.domain.updates import (
    Purpose,
    RemotePlan,
    RemoteResult,
    RemoteStepResult,
    StepName,
    manual_from_dict,
    plan_to_dict,
    purpose_from_dict,
    result_to_dict,
    updates_from_dict,
)

UPDATES_FILE = "updates.json"
RESULT_FILE = "result.json"


def _hostname() -> str:
    return (socket.gethostname() or "?").split(".")[0][:64]


def _wiring():  # type: ignore[no-untyped-def]
    from omega_connect.app.main import build_detect, build_repair, build_verify, build_zone
    from omega_connect.app.remote_scan import FAIL2BAN_DIR_ENV, HOME_ENV, TEST_DIRS_ENV

    overrides = {key: os.environ[name] for key, name in TEST_DIRS_ENV.items() if os.environ.get(name)}
    home = os.environ.get(HOME_ENV)
    detect = build_detect(home=Path(home) if home else None, **overrides)  # type: ignore[arg-type]
    zone = build_zone()
    fail2ban = os.environ.get(FAIL2BAN_DIR_ENV)
    verify = build_verify(detect, zone=zone, **({"fail2ban_dir": fail2ban} if fail2ban else {}))
    return detect, verify, zone, build_repair()


def plan_mode() -> int:
    from omega_lib.infrastructure.synchro.install_token import read_machine_fingerprint

    from omega_connect.application.enroll_actions import EnrollTools, enroll_plan
    from omega_connect.application.repair_actions import repair_plan
    from omega_connect.application.zone_actions import needs_elevation
    from omega_connect.domain.versions import outdated_roots
    from omega_connect.interfaces.cli.enroll_view import render_enroll_plan
    from omega_connect.interfaces.cli.main import DetectRequest
    from omega_connect.interfaces.cli.repair_view import render_repair_plan

    detect, verify, zone, repair = _wiring()
    request = DetectRequest(manual_paths=[], with_sheets=True)
    report = verify(request)
    repairs = repair_plan(report, repair)
    facts = zone.inspector.inspect(elevated=False)
    enroll = EnrollTools(zone=zone, repair=repair, detect=lambda: detect(request))
    enrolls = enroll_plan(facts, report.detection, enroll, None)
    old = outdated_roots(report.detection.installations)
    unreadable = needs_elevation(facts)
    repair_work = bool(repairs.steps) or repairs.offers_zone
    sync_work = not dataclasses.replace(repairs, outdated=()).empty or not enrolls.empty or unreadable
    manual = tuple(dict.fromkeys(finding.check.fix for finding in repairs.manual if finding.check.fix))
    plan = RemotePlan(_hostname(), read_machine_fingerprint(), tuple(old[root] for root in sorted(old)),
                      render_repair_plan(repairs, as_root=repair.as_root),
                      render_enroll_plan(enrolls, as_root=zone.as_root), unreadable, bool(old) or sync_work,
                      sync_work, repair_work, manual)
    sys.stdout.write(json.dumps(plan_to_dict(plan), ensure_ascii=False))
    sys.stdout.flush()
    return 0


def _cli(argv: list[str]) -> int:
    from omega_connect.interfaces.cli.main import run

    detect, verify, zone, repair = _wiring()
    try:
        return run(argv, detect, verify, zone=zone, repair=repair, machine=_hostname())
    except SystemExit as stop:  # argparse
        return int(stop.code or 0) if isinstance(stop.code, int) else 2


def _write_result(session: Path, steps: list[RemoteStepResult]) -> None:
    path = session / RESULT_FILE
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(result_to_dict(RemoteResult(tuple(steps))), handle, ensure_ascii=False)


def run_mode(directory: str) -> int:
    from omega_connect.infrastructure.remote.apply_update import UpdateError, apply_update
    from omega_connect.shared.i18n import _

    session = Path(directory)
    steps: list[RemoteStepResult] = []
    print(_("omega-connect — machine {machine}").format(machine=_hostname()), flush=True)
    try:
        document = json.loads((session / UPDATES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = {}
    orders = updates_from_dict(document) or ()
    purpose = purpose_from_dict(document)
    for order in orders:
        print("", flush=True)
        print(_("== Mise à jour de {tool} vers {version} ({root})").format(tool=order.tool, version=order.version,
                                                                         root=order.root), flush=True)
        try:
            aside = apply_update(order, session)
        except (UpdateError, OSError) as error:
            print(_("✗ {tool} : {error}").format(tool=order.tool, error=error), flush=True)
            steps.append(RemoteStepResult(StepName.UPDATE, 1, order.tool, str(error)))
            _write_result(session, steps)
            return 1
        print(_("✓ {tool} {version} installé.").format(tool=order.tool, version=order.version), flush=True)
        steps.append(RemoteStepResult(StepName.UPDATE, 0, order.tool, aside))
    if purpose is Purpose.UPDATE:  # « Mettre a jour l'application » : rien d'autre
        _write_result(session, steps)
        return 0
    commands = [(StepName.REPAIR, ["reparer", "--oui"])]
    if purpose is Purpose.SYNC:
        commands.append((StepName.ENROLL, ["synchroniser", "--oui"]))
    for name, argv in commands:
        print("", flush=True)
        code = _cli(argv)
        steps.append(RemoteStepResult(name, code))
        _write_result(session, steps)
        if code != 0:
            return code
    announced = manual_from_dict(document) if purpose is Purpose.REPAIR else ()
    if announced:
        code = _run_manual(announced, steps)
        _write_result(session, steps)
        return code
    _write_result(session, steps)
    return 0


def _current_manual() -> tuple[str, ...]:
    from omega_connect.application.repair_actions import repair_plan
    from omega_connect.interfaces.cli.main import DetectRequest

    _detect, verify, _zone, repair = _wiring()
    plan = repair_plan(verify(DetectRequest(manual_paths=[], with_sheets=True)), repair)
    return tuple(dict.fromkeys(finding.check.fix for finding in plan.manual if finding.check.fix))


def _run_manual(announced: tuple[str, ...], steps: list[RemoteStepResult]) -> int:
    """Commandes annoncees ET encore necessaires (recalculees ici, apres les corrections des outils) ; une
    commande qui n'etait pas annoncee n'est jamais lancee."""
    from omega_connect.infrastructure.remote.apply_update import run_shell
    from omega_connect.shared.i18n import _

    still = set(_current_manual())
    print("", flush=True)
    for command in announced:
        if command not in still:
            print(_("· déjà réglé : {command}").format(command=command), flush=True)
            continue
        code = run_shell(command)
        steps.append(RemoteStepResult(StepName.MANUAL, code, detail=command))
        if code != 0:
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    mode = arguments[0] if arguments else "scan"
    if mode == "plan":
        return plan_mode()
    if mode == "run" and len(arguments) == 2:
        return run_mode(arguments[1])
    if mode == "scan":
        from omega_connect.app.remote_scan import main as scan

        return scan()
    sys.stderr.write("omega-connect: mode inconnu\n")
    return 2


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(main())
    sys.exit(130)
