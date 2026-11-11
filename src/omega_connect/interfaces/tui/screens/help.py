# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Aide (menu Maintenance, touche a ; lot F) : modele d'omega-log — une section repliable par menu (sa fonction et
le detail), demarrage rapide deplie, raccourcis, notions ; « Exporter l'aide en HTML » (theme au choix, dans le
dossier des exports) et « Contact et support » (ecrans partages d'omega-lib, D-016)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Collapsible, Footer, Header, Select, Static

from omega_connect.interfaces.cli.help_view import render_help_html
from omega_connect.interfaces.tui.help_content import QUICKSTART, SECTIONS, SHORTCUTS
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.ports.export import ExportWriter
from omega_connect.shared.i18n import _


def _shortcuts() -> str:
    width = max(len(_(key)) for key, _what in SHORTCUTS)
    return "\n".join(f"[b]{_(key):<{width}}[/b]  {_(what)}" for key, what in SHORTCUTS)


class HelpScreen(OmegaScreen):
    def __init__(self, *, version: str, writer: ExportWriter | None,
                 contact: Callable[[], Screen[Any]] | None = None) -> None:
        super().__init__()
        self._version = version
        self._writer = writer
        self._contact = contact

    def compose(self) -> ComposeResult:
        settings = getattr(self.app, "settings", None)
        theme = settings.export_theme() if settings is not None else DEFAULT_EXPORT_THEME
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("AIDE"), classes="omega-title")
            yield Static(_("Chaque menu, sa fonction et le détail. Cliquez sur un titre pour l'ouvrir."),
                         classes="omega-hint")
            with Collapsible(title=_("Démarrage rapide"), collapsed=False):
                yield Static(_(QUICKSTART))
            with Collapsible(title=_("Raccourcis"), collapsed=True):
                yield Static(_shortcuts())
            for title, body in SECTIONS:
                with Collapsible(title=_(title), collapsed=True):
                    yield Static(_(body))
        # Retour utilisateur 2026-11-11 : le choix du theme, puis Exporter ; en dessous Contact et support, Retour.
        # La liste des themes a une largeur fixe (en largeur libre elle repoussait Retour hors de l'ecran).
        with Vertical(id="help-actions"):
            with Horizontal(classes="omega-actions omega-fixed-actions"):
                yield Select([(name, name) for name in EXPORT_PALETTES], value=theme, allow_blank=False,
                             id="export-theme")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter l'aide en HTML"), id="export-html", variant="primary",
                                 disabled=self._writer is None)
            with Horizontal(classes="omega-actions omega-fixed-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Contact et support"), id="contact", disabled=self._contact is None)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-html" and self._writer is not None:
            theme = str(self.query_one("#export-theme", Select).value)
            name = f"omega-connect-aide-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.html"
            try:
                path = self._writer.save(name, render_help_html(self._version, theme))
            except OSError as error:
                self.app.notify(str(error), severity="error")
                return
            self.app.notify(_("Aide exportée : {path}").format(path=path))
        elif event.button.id == "contact" and self._contact is not None:
            self.app.push_screen(self._contact())
        elif event.button.id == "back":
            self.action_back()
