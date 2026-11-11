# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Indicateur d'attente (demande de l'auteur, 2026-11-10) : animation de Textual (`LoadingIndicator`, comme les
ecrans de progression d'omega-fire et d'omega-log) suivie d'une phrase, affiche pendant un travail long
(generation du rapport, synchronisation, lecture du registre, preparation des commandes)."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import LoadingIndicator, Static


class Busy(Horizontal):
    DEFAULT_CLASSES = "omega-busy"

    def __init__(self, text: str = "", *, id: str | None = None) -> None:  # noqa: A002 - nom Textual
        super().__init__(id=id)
        self._text = text

    def compose(self) -> ComposeResult:
        yield LoadingIndicator()
        yield Static(self._text, classes="omega-busy-text")

    def on_mount(self) -> None:
        self.display = False

    def show(self, text: str | None = None) -> None:
        if text is not None:
            self.query_one(".omega-busy-text", Static).update(text)
        self.display = True

    def hide(self) -> None:
        self.display = False
