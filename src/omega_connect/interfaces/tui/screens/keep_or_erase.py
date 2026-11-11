# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""« Tout retirer » : garder la zone (liens figes) ou tout retirer (etude, §9 ; spec etape 3, §3.5)."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Middle, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from omega_connect.shared.i18n import _


class KeepOrEraseScreen(Screen[bool | None]):
    """Renvoie True (garder la zone), False (tout retirer) ou None (annuler)."""

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(classes="omega-confirm-box"):
            yield Static(_("RETIRER LA ZONE NEUTRE ?"), classes="omega-confirm-title")
            yield Static(_("Garder : rien n'est supprimé, les outils lisent toujours les copies actuelles (liens "
                           "figés). Tout retirer : défait exactement ce que le registre liste."),
                         classes="omega-hint")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Garder la zone"), id="keep", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Tout retirer"), id="erase", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Annuler"), id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss({"keep": True, "erase": False}.get(event.button.id or ""))

    def key_escape(self) -> None:
        self.dismiss(None)
