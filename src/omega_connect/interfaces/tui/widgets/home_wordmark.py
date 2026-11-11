# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Bandeau OMEGA-CONNECT en haut du menu principal : variante sur deux lignes d'ascii.txt (« ou »), OMEGA au-dessus
de CONNECT, caracteres non modifies. La variante sur une ligne (98 colonnes) ne tient pas dans un terminal de 80.
Placement calcule comme l'ecran de demarrage : OMEGA et le trait d'union centres sur l'axe de CONNECT (demi-colonne
en trop a gauche). Couleurs d'ascii.txt : ligne 1 vif, ligne 2 clair, ligne 3 vif ; le trait d'union « ══ » vif."""
from __future__ import annotations

from textual.content import Content, Span
from textual.widgets import Static

OMEGA_LETTERS = (
    "┌╦═══╦┐ ┌╦═╦═╦┐ ┌╦═══╦┐ ┌╦═══╦┐ ┌╦═══╦┐",
    "│║   ║│ │║ ║ ║│ ├╬══    │║  ═╦┐ ├╬═══╬┤",
    "└╩═══╩┘ └╩   ╩┘ └╩═══╩┘ └╩═══╩┘ └╩   ╩┘",
)
CONNECT = (
    "┌╦═══╦┐ ┌╦═══╦┐ ┌╦═╗ ╦┐ ┌╦═╗ ╦┐ ┌╦═══╦┐ ┌╦═══╦┐ ┌═╤╦╤═┐",
    "│║      │║   ║│ │║ ║ ║│ │║ ║ ║│ ├╬══    │║        │║│",
    "└╩═══╩┘ └╩═══╩┘ └╩ ╚═╩┘ └╩ ╚═╩┘ └╩═══╩┘ └╩═══╩┘   ╧╩╧",
)
ROW_COLORS = ("$accent", "$foreground", "$accent")
AXIS = (len(CONNECT[0]) - 1) // 2


def _on_axis(text: str) -> str:
    return " " * (AXIS - len(text) // 2) + text


OMEGA = tuple(_on_axis(line) for line in OMEGA_LETTERS)
HYPHEN = _on_axis("══")


def wordmark_content() -> Content:
    lines = [*OMEGA, HYPHEN, *CONNECT]
    colors = [*ROW_COLORS, "$accent", *ROW_COLORS]
    spans, offset = [], 0
    for line, color in zip(lines, colors, strict=True):
        start = len(line) - len(line.lstrip(" "))
        spans.append(Span(offset + start, offset + len(line), color))
        offset += len(line) + 1
    return Content("\n".join(lines), spans)


class HomeWordmark(Static):
    def __init__(self) -> None:
        super().__init__(wordmark_content(), classes="omega-home-wordmark")
