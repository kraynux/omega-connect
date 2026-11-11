# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Detail d'un lien (spec etape 3, §4) : tous ses controles, conformes compris, et la commande qui corrigerait
chaque ecart. Lecture seule : les commandes sont affichees pour etre relues, jamais lancees ici."""
from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_connect.domain.links import Link
from omega_connect.interfaces.cli.verification_view import LINK_LABELS
from omega_connect.interfaces.tui.presentation import MACHINE, check_lines, state_text
from omega_connect.interfaces.tui.screens._base import OmegaScreen, copy_commands
from omega_connect.shared.i18n import _


class LinkDetailScreen(OmegaScreen):
    def __init__(self, *, link: Link, verified_at: datetime | None) -> None:
        super().__init__()
        self._link = link
        self._verified_at = verified_at

    def compose(self) -> ComposeResult:
        link = self._link
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_(LINK_LABELS[link.kind]).upper(), classes="omega-title")
            yield Static(self._where(), classes="omega-hint")
            yield Static("", id="link-state")
            yield Static(_("CONTRÔLES"), classes="omega-subtitle")
            yield Static("", id="link-checks")
            yield Static(_("Cet écran montre. Pour corriger : menu Réparer (toutes les machines, machine du "
                           "réseau comprise) ; les commandes se copient avec « Copier les commandes »."),
                         classes="omega-hint")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame", id="copy-frame"):
                yield Button(_("Copier les commandes"), id="copy")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back", variant="primary")
        yield Footer()

    def _where(self) -> str:
        link = self._link
        place = _("instance « {instance} » — {root}").format(instance=link.instance, root=link.root) \
            if link.root else (link.instance or _(MACHINE))
        if self._verified_at is not None:
            place += " · " + _("vérifié à {time}").format(time=self._verified_at.strftime("%H:%M:%S"))
        return place

    def on_mount(self) -> None:
        styles = {key: self.app.get_css_variables().get(key, key) for key in ("success", "warning", "error",
                                                                              "secondary")}
        state = Text(_("État : "), style="bold")
        state.append_text(state_text(self._link.state, styles))
        self.query_one("#link-state", Static).update(state)
        self.query_one("#link-checks", Static).update(check_lines(self._link, styles, with_ok=True))
        self.query_one("#copy-frame").display = bool(self._commands())


    def _commands(self) -> list[str]:
        return [check.fix for check in self._link.checks if check.fix]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy":
            copy_commands(self.app, self._commands())
        elif event.button.id == "back":
            self.dismiss()
