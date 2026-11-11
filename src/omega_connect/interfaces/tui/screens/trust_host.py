# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""« Faire confiance à cette machine ? » (lot R2) : empreinte de la clé montrée, accord explicite ; rien n'est
accepté en silence. Renvoie True si la personne fait confiance."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Middle, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from omega_connect.domain.remote import HostCheck
from omega_connect.interfaces.cli.remote_view import trust_question
from omega_connect.shared.i18n import _


class TrustHostScreen(Screen[bool]):
    def __init__(self, check: HostCheck) -> None:
        super().__init__()
        self._check = check

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(classes="omega-confirm-box omega-trust-box"):
            yield Static(_("FAIRE CONFIANCE À CETTE MACHINE ?"), classes="omega-confirm-title")
            yield Static(trust_question(self._check), id="trust-text")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Faire confiance"), id="trust", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Annuler"), id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "trust")
