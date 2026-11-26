# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Recherche et filtre par etat d'une liste (decision 2026-11-26, lot S5 : un parc d'une cinquantaine de machines
doit rester lisible). Une recherche (machine, application, dossier) et un etat ; seul l'affichage change : les
boutons « … tout » agissent toujours sur toute la liste, jamais sur la seule partie filtree."""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Select

from omega_connect.shared.i18n import _

ALL = "all"


class ListFilter(Horizontal):
    DEFAULT_CLASSES = "omega-list-filter"

    class Changed(Message):
        """La recherche ou l'etat a change : l'ecran refait seulement l'affichage."""

    def __init__(self, states: Sequence[tuple[str, str]]) -> None:
        """`states` : (libelle deja traduit, cle) ; « Tous les états » est ajoute en tete."""
        super().__init__()
        self._states = [(_("Tous les états"), ALL), *states]
        self.text = ""
        self.state = ALL

    def compose(self) -> ComposeResult:
        yield Input(placeholder=_("Rechercher : machine, application, dossier…"), id="filter-text")
        yield Select(self._states, value=ALL, allow_blank=False, id="filter-state")

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self.text = event.value.strip().lower()
        self.post_message(self.Changed())

    def on_select_changed(self, event: Select.Changed) -> None:
        event.stop()
        self.state = str(event.value)
        self.post_message(self.Changed())

    @property
    def active(self) -> bool:
        return bool(self.text) or self.state != ALL

    def matches(self, words: Iterable[str], state: str) -> bool:
        if self.state != ALL and state != self.state:
            return False
        return not self.text or any(self.text in word.lower() for word in words if word)
