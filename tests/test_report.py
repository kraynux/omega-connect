# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Rapport complet (menu Maintenance -> Rapport ; commande `rapport`) : texte, JSON, HTML, enregistrement dans un
dossier d'exports temporaire (jamais le vrai var/)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from omega_lib.synchro.models import ReadStatus
from omega_lib.terminal.models import RenderProfile
from textual.widgets import Button
from zone_fakes import AT, FIRE, SERV, SUBJECT, FakeSystem, _detection

from omega_connect.application.report import ReportTools, build_report
from omega_connect.application.zone_actions import apply_plan, establish_plan
from omega_connect.domain.detection import DetectedInstallation, DetectionReport, Source
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind, VerificationReport
from omega_connect.domain.zone_checks import zone_link
from omega_connect.infrastructure.exports.writer import FileExportWriter
from omega_connect.interfaces.cli.main import run
from omega_connect.interfaces.cli.report_view import (
    export_name,
    render_report_html,
    render_report_text,
    report_to_dict,
)
from omega_connect.interfaces.tui.app import OmegaConnectApp
from omega_connect.interfaces.tui.menu import MENU, Column
from omega_connect.interfaces.tui.screens.home import HomeScreen
from omega_connect.interfaces.tui.screens.quit_confirm import QuitConfirmScreen
from omega_connect.interfaces.tui.screens.report import ReportScreen
from omega_connect.interfaces.tui.widgets.busy import Busy

TRAP = "/home/k/<script>alert(1)</script>"


def _verification(system: FakeSystem) -> VerificationReport:
    detection = _detection(SERV, FIRE)
    trap = DetectedInstallation(TRAP, "omega-serv", (Source.HOME,), "k", ReadStatus.ABSENT)
    detection = DetectionReport(detection.home, (*detection.installations, trap))
    links = (
        Link(LinkKind.BLOCKLIST, "omega-serv", "/home/k/omega-serv", (
            Check(CheckCode.BLOCKLIST_MODE, CheckStatus.WARNING, "/home/k/omega-serv/var/lib/waf/blocklist.json",
                  "k:omega-serv 0600", fix="chmod 0660 x", fix_account="k"),)),
        zone_link(system.inspect(), detection, SUBJECT, "oc"),
    )
    return VerificationReport(detection, links)


@pytest.fixture
def system(tmp_path: Path) -> FakeSystem:
    fake = FakeSystem(tmp_path / "machine")
    facts = fake.inspect()
    apply_plan(establish_plan(facts, _detection(SERV, FIRE), SUBJECT, AT), facts, fake)
    return fake


def test_text_json_and_html_cover_everything(system):
    report = build_report(_verification(system), system.inspect(), version="0.1.0", now=AT)
    text = render_report_text(report)
    for part in ("RAPPORT COMPLET", "EN DÉTAIL", "(tous les contrôles)", "ESPACE PARTAGÉ (omega-synchro)",
                 "chmod 0660 x", "membre du groupe k", "omega-fire « omega-fire »", "active (synchronisée)", "BILAN",
                 "À FAIRE", "REGISTRE — APPLICATIONS PAR MACHINE", "MACHINES DU RÉSEAU"):
        assert part in text, part
    data = report_to_dict(report)
    assert data["format"] == "omega-connect-rapport" and data["schema_version"] == 2
    assert data["summary"]["degraded"] == 1 and data["zone"]["registry"]["format"] == "omega-registre"
    assert len(data["verification"]["detection"]["installations"]) == 3
    page = render_report_html(report, "light-basic")
    assert "<script>alert" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.startswith("<!DOCTYPE html>") and 'class="terminal-header"' in page and 'class="footer-note"' in page
    assert "--bg-body: #f4f5f7" in page  # palette light-basic reprise d omega-fire
    assert ".terminal-header {" in page and ".footer-note {" in page and ".table-wrapper {" in page  # cadre de base
    assert "badge badge-warning" in page and 'class="link-card warning"' in page
    assert export_name(report, "html") == "omega-connect-rapport-20261110-120000.html"


def test_unreadable_zone_is_said_not_hidden(system):
    from omega_connect.domain.zone import ZoneFacts

    hidden = ZoneFacts(system.zone, {"": system.inspect().root}, False, group_exists=True)
    report = build_report(_verification(system), hidden, version="0.1.0", now=AT)
    assert "lisible par root et le groupe omega-synchro seulement" in render_report_text(report)
    assert report_to_dict(report)["zone"]["registry"] is None


def test_cli_prints_or_saves(system, tmp_path, capsys):
    exports = tmp_path / "var" / "exports"
    writer = FileExportWriter(exports)

    def report_of(request):
        return build_report(_verification(system), system.inspect(), version="0.1.0", now=AT)

    detect = lambda request: _detection(SERV)  # noqa: E731
    assert run(["rapport", "--format", "json"], detect, report_of=report_of, writer=writer) == 0
    assert json.loads(capsys.readouterr().out)["format"] == "omega-connect-rapport"
    assert run(["rapport", "--format", "html", "--theme", "omega-neon", "--enregistrer"], detect,
               report_of=report_of, writer=writer) == 0
    assert "Rapport enregistré" in capsys.readouterr().out
    assert [path.name for path in exports.iterdir()] == ["omega-connect-rapport-20261110-120000.html"]
    with pytest.raises(ValueError):
        writer.save("../evasion.txt", "x")


def _app(system: FakeSystem, writer: FileExportWriter) -> OmegaConnectApp:
    tools = ReportTools(lambda: build_report(_verification(system), system.inspect(), version="0.1.0", now=AT),
                        writer)
    return OmegaConnectApp(verify=lambda: _verification(system), version="0.1.0",
                           render_profile=RenderProfile.COMPLETE, refresh_seconds=0, splash=False, report=tools)


def test_menu_columns_are_balanced_and_contact_lives_in_help():
    """Refonte (proposition de l'auteur) : GESTION 5 / MAINTENANCE 5, Quitter compris."""
    main = [entry.key for entry in MENU if entry.column is Column.MAIN]
    maintenance = [entry.key for entry in MENU if entry.column is Column.MAINTENANCE]
    assert main == ["registry", "scanner", "links", "synchronisation", "dashboard"]
    assert maintenance == ["repair", "report", "settings", "help", "quit"]
    assert "contact" not in main + maintenance


async def test_report_screen_exports_three_formats_and_quit_key(system, tmp_path):
    exports = tmp_path / "exports"
    app = _app(system, FileExportWriter(exports))
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        await pilot.click("#menu-report")
        for _round in range(3):
            await app.workers.wait_for_complete()
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ReportScreen) and screen.report is not None
        assert not screen.query_one(Busy).display  # indicateur d'attente cache une fois le rapport pret
        for button in ("#export-txt", "#export-json", "#export-html"):
            assert not screen.query_one(button, Button).disabled
            await pilot.click(button)
            await pilot.pause()
        assert sorted(path.suffix for path in exports.iterdir()) == [".html", ".json", ".txt"]
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, QuitConfirmScreen)


def test_every_creation_kind_has_a_label_and_the_service_group_is_reported(tmp_path):
    """2026-11-10 : juste apres la premiere synchronisation reelle, le rapport plantait (KeyError) sur la creation
    « groupe donne au service », que sa liste de libelles ne connaissait pas."""
    from omega_lib.synchro.registry import CreatedKind
    from zone_fakes import SERV_SERVICE

    from omega_connect.interfaces.cli.report_view import KIND_LABELS

    assert set(KIND_LABELS) == set(CreatedKind)
    fake = FakeSystem(tmp_path / "machine")
    facts = fake.inspect()
    assert apply_plan(establish_plan(facts, _detection(SERV_SERVICE), SUBJECT, AT), facts, fake).ok
    verification = VerificationReport(_detection(SERV_SERVICE),
                                      (zone_link(fake.inspect(), _detection(SERV_SERVICE), SUBJECT, "oc"),))
    report = build_report(verification, fake.inspect(), version="0.1.0", now=AT)
    assert "groupe donné au service (par omega-serv)" in render_report_text(report)
    assert "groupe donné au service" in render_report_html(report, "omega-base")
    assert report_to_dict(report)["zone"]["registry"]["created"]


def test_report_covers_every_machine_and_says_what_to_do(system):
    """Retour de l'auteur (2026-11-11) : « le contenu du rapport n'est plus en adéquation avec nos changements ».
    Machines du réseau, versions, installation inachevée, injoignable, et « à faire » rangé par bouton."""
    from omega_connect.domain.fleet import AppState, RegistryRow
    from omega_connect.domain.parc import MachineEntry

    old = RegistryRow("craftdark", "omega-jail", "/home/k/omega-jail", "", "", "1.1.0", AppState.OLD_VERSION)
    half = RegistryRow("craftdark", "omega-serv", "/home/k/omega-serv", "omega-serv", "", "2.6.1",
                       AppState.INCOMPLETE)
    remote_link = Link(LinkKind.BLOCKLIST, "omega-serv", "/home/k/omega-serv", (
        Check(CheckCode.BLOCKLIST_OK, CheckStatus.OK, "/home/k/omega-serv/var/b.json"),), machine="craftdark")
    craftdark = MachineEntry("craftdark", False, "2026-11-11T10:00:00Z", (old, half), "f" * 16,
                             ("192.168.1.103",), "kraynux@192.168.1.103", links=(remote_link,))
    gone = MachineEntry("hpc-109", False, "2026-11-10T10:00:00Z",
                        (RegistryRow("hpc-109", "omega-fire", "/h/f", "", "", "3.6.1", AppState.LINKED),), "e" * 16,
                        ("192.168.1.109",), "kraynux@192.168.1.109", reachable=False, last_error="unreachable")
    report = build_report(_verification(system), system.inspect(), version="0.1.0", now=AT, machine="vpc-107",
                          network=(craftdark, gone))
    text = render_report_text(report)
    for part in ("3 machine(s) : vpc-107 et 2 du réseau.",
                 "À réinstaller ou à mettre à jour — Registre, bouton sous la ligne",
                 "craftdark (192.168.1.103) — omega-jail 1.1.0 → 1.2.1 ou plus récent : « Mettre à jour l'application »",
                 "omega-serv 2.6.1 : installation inachevée → « Réinstaller l'application »",
                 "Machines qui ne répondent plus", "hpc-109 (192.168.1.109)",
                 "LIAISONS DE CRAFTDARK (192.168.1.103) (réseau", "dernière erreur : unreachable",
                 "Installation inachevée", "Injoignable"):
        assert part in text, part
    data = report_to_dict(report)
    assert data["machine"] == "vpc-107" and [m["name"] for m in data["machines"]] == ["craftdark", "hpc-109"]
    assert {row["tool"] for row in data["todo"]["update"]} == {"omega-jail", "omega-serv"}
    assert data["todo"]["unreachable"] == ["hpc-109 (192.168.1.109)"]
    assert data["applications_summary"]["incomplete"] == 1 and data["machines"][0]["links"]
    page = render_report_html(report, "omega-base")
    assert "sans votre accord" not in page and "relisez" not in text and "« verifier »" not in text
    for part in ("Machines du réseau", "À faire", "Registre — applications par machine",
                 "Liaisons de craftdark (192.168.1.103)", "◇ Installation inachevée", "injoignable"):
        assert part in page, part
