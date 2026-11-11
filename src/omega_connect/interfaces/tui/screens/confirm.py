# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Confirmation simple (titre, explication, oui / non), au cadre des autres confirmations de la suite."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Middle, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static


class ConfirmScreen(Screen[bool]):
    def __init__(self, *, title: str, text: str, yes: str, no: str) -> None:
        super().__init__()
        self._title, self._text, self._yes, self._no = title, text, yes, no

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(classes="omega-confirm-box omega-trust-box"):
            yield Static(self._title, classes="omega-confirm-title")
            yield Static(self._text, id="confirm-text")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button(self._yes, id="confirm", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button(self._no, id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")
