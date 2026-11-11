# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran de demarrage : logo d'ascii.txt, se ferme sur une touche ou un clic (patron de la suite omega)."""
from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Static

from omega_connect.interfaces.tui.widgets.splash_hero import SplashHero
from omega_connect.shared.i18n import _


class SplashScreen(Screen[None]):
    def __init__(self, *, version: str) -> None:
        super().__init__()
        self._version = version

    def compose(self) -> ComposeResult:
        with Middle(classes="omega-splash-middle"):
            with Center():
                yield SplashHero(self._version)
            with Center():
                yield Static(_("Appuyez sur une touche pour continuer..."), classes="omega-splash-prompt")

    def on_key(self, event: events.Key) -> None:
        event.stop()
        self.dismiss()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.dismiss()
