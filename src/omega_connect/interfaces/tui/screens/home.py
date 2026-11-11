# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Menu principal « par theme » (deux colonnes, comme omega-log) ; entrees lues dans `menu.py`. Racine de la
navigation : Echap demande la confirmation de sortie."""
from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header

from omega_connect.interfaces.tui.menu import COLUMN_TITLES, MENU, Column
from omega_connect.interfaces.tui.screens.quit_confirm import QuitConfirmScreen
from omega_connect.interfaces.tui.widgets.home_wordmark import HomeWordmark
from omega_connect.shared.i18n import _

ScreenFactory = Callable[[str], "Screen[None] | None"]
"""Cle d'une entree du menu -> ecran a ouvrir (None : pas encore construit)."""


class HomeScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", _("Retour"), show=True),
        Binding("up", "focus_previous_item", _("Monter"), show=False),
        Binding("down", "focus_next_item", _("Descendre"), show=False),
    ]

    def __init__(self, *, open_screen: ScreenFactory) -> None:
        super().__init__()
        self._open_screen = open_screen

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-home-root"):
            with Center():
                yield HomeWordmark()
            with Center(), Horizontal(classes="omega-home-columns"):
                for column in Column:
                    with Vertical(classes="omega-home-menu") as box:
                        for entry in MENU:
                            if entry.column is column:
                                with Container(classes="omega-btn-frame"):
                                    yield Button(_(entry.label).upper(), id=f"menu-{entry.key}")
                    box.border_title = _(COLUMN_TITLES[column])
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        key = (event.button.id or "").removeprefix("menu-")
        entry = next((item for item in MENU if item.key == key), None)
        if entry is None:
            return
        if key == "quit":
            self.action_back()
            return
        screen = None if entry.planned else self._open_screen(key)
        if screen is not None:
            self.app.push_screen(screen)
            return
        self.app.notify(_("Écran prévu au lot {lot} de l'étape 3.").format(lot=entry.planned or "?"),
                        title=_(entry.label), severity="information")

    def action_back(self) -> None:
        self.app.push_screen(QuitConfirmScreen(), self._quit_if_confirmed)

    def _quit_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.app.exit()

    def action_focus_previous_item(self) -> None:
        self.focus_previous()

    def action_focus_next_item(self) -> None:
        self.focus_next()
