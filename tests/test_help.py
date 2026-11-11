# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lot F : Aide exhaustive (une section par menu), export HTML, Contact et support."""
from __future__ import annotations

from pathlib import Path

from omega_lib.terminal.models import RenderProfile
from textual.widgets import Button, Collapsible
from zone_fakes import AT, FakeSystem, _detection

from omega_connect.application.report import ReportTools
from omega_connect.application.zone_actions import ZoneTools
from omega_connect.domain.links import VerificationReport
from omega_connect.infrastructure.exports.writer import FileExportWriter
from omega_connect.interfaces.cli.help_view import help_text, render_help_html
from omega_connect.interfaces.tui.app import OmegaConnectApp
from omega_connect.interfaces.tui.help_content import SECTIONS
from omega_connect.interfaces.tui.menu import MENU
from omega_connect.interfaces.tui.screens.help import HelpScreen
from omega_connect.interfaces.tui.screens.home import HomeScreen

MENU_TITLES = {"registry": "Registre", "scanner": "Scanner", "links": "Liaisons", "synchronisation": "Synchronisation",
               "dashboard": "Dashboard", "repair": "Réparer", "report": "Rapport", "settings": "Réglages",
               "help": "Aide"}


def test_every_menu_entry_has_its_section_and_no_internal_jargon():
    """« Exhaustive et explicite » : chaque menu a sa section ; les mots sont ceux de l'interface."""
    titles = " ".join(title for title, _body in SECTIONS)
    for entry in MENU:
        if entry.key != "quit":
            assert MENU_TITLES[entry.key] in titles, entry.key
    text = help_text().replace("omega-jeton.json", "")  # nom reel du fichier : il faut pouvoir le trouver
    import re

    for word in ("jeton", "zone neutre", "fiche", "« verifier »", "relisez"):
        assert not re.search(rf"\b{re.escape(word)}\b", text), word
    for part in ("Mettre à jour l'application", "Réinstaller l'application", "Tout réparer", "Copier les commandes",
                 "Synchroniser la sélection", "var/settings.json", "Contact et support", "Release GitHub"):
        assert part in text, part


def test_help_html_is_a_standalone_page_with_every_section():
    page = render_help_html("0.1.0", "omega-base")
    assert page.startswith("<!DOCTYPE html>") and 'class="terminal-header"' in page and "<script" not in page
    assert "<strong>Scanner</strong>" in page and "[b]" not in page
    import html

    assert all(html.escape(title) in page for title, _body in SECTIONS)


async def test_help_screen_sections_export_and_contact(tmp_path: Path):
    system = FakeSystem(tmp_path / "machine")
    detection = _detection()
    exports = tmp_path / "exports"
    zone = ZoneTools(inspector=system, runner=system, subject=None, now=lambda: AT,  # type: ignore[arg-type]
                     interactive=lambda: False)
    app = OmegaConnectApp(verify=lambda: VerificationReport(detection, ()), version="0.1.0",
                          render_profile=RenderProfile.COMPLETE, refresh_seconds=0, zone=zone,
                          detect=lambda: detection, splash=False,
                          report=ReportTools(lambda: None, FileExportWriter(exports)))  # type: ignore[arg-type]
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        await pilot.press("a")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, HelpScreen)
        collapsibles = list(screen.query(Collapsible))
        assert len(collapsibles) == len(SECTIONS) + 2 and not collapsibles[0].collapsed
        assert all(item.collapsed for item in collapsibles[1:])
        assert screen.query_one("#contact", Button).disabled  # pas de services en test
        screen.query_one("#export-html", Button).press()
        await pilot.pause()
        exported = list(exports.glob("omega-connect-aide-*.html"))
        assert len(exported) == 1 and "Démarrage rapide" in exported[0].read_text(encoding="utf-8")


async def test_help_actions_fit_and_back_returns(tmp_path: Path):
    """Retour utilisateur 2026-11-11 : theme puis Exporter, en dessous Contact et Retour ; tout visible sans
    defilement de cote ; Retour ramene a l'ecran precedent."""
    system = FakeSystem(tmp_path / "machine")
    detection = _detection()
    zone = ZoneTools(inspector=system, runner=system, subject=None, now=lambda: AT,  # type: ignore[arg-type]
                     interactive=lambda: False)
    app = OmegaConnectApp(verify=lambda: VerificationReport(detection, ()), version="0.1.0",
                          render_profile=RenderProfile.COMPLETE, refresh_seconds=0, zone=zone,
                          detect=lambda: detection, splash=False,
                          report=ReportTools(lambda: None, FileExportWriter(tmp_path / "e")))  # type: ignore[arg-type]
    from textual.widgets import Select

    async with app.run_test(size=(80, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        screen = app.screen
        theme = screen.query_one("#export-theme", Select).region
        export, contact, back = (screen.query_one(f"#{name}", Button).region
                                 for name in ("export-html", "contact", "back"))
        assert theme.y <= export.y < theme.bottom and theme.x < export.x  # theme puis Exporter, meme ligne
        assert contact.y == back.y >= theme.bottom and contact.x < back.x  # en dessous : Contact, Retour
        assert all(region.right <= 80 for region in (theme, export, contact, back))
        await pilot.click("#back")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
