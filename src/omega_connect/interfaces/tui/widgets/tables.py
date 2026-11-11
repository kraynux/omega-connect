# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tableaux qui occupent l'ecran (retour de l'auteur, 2026-11-10 : « la fenetre interieure n'englobe pas l'ecran,
il y a un ascenseur alors qu'il reste beaucoup de place ; pour traiter plusieurs machines c'est trop complique ») :
la derniere colonne s'etire jusqu'au bord ; la hauteur suit l'ecran (feuille de style, en `vh`), jamais `1fr` dans
un panneau qui defile (piege connu : tableau reduit a l'en-tete)."""
from __future__ import annotations

from typing import Any

from textual.widgets import DataTable

SCROLLBAR_WIDTH = 2


def stretch_last_column(table: DataTable[Any]) -> None:
    """Largeur de la derniere colonne = place restante (au moins son contenu)."""
    columns = list(table.columns.values())
    if not columns or table.size.width <= 0:
        return
    last = columns[-1]
    others = sum(column.get_render_width(table) for column in columns[:-1])
    padding = 2 * table.cell_padding
    available = table.size.width - others - padding - SCROLLBAR_WIDTH
    wanted = max(last.content_width, available)
    if last.auto_width or last.width != wanted:
        last.auto_width = False
        last.width = wanted
        table._require_update_dimensions = True  # noqa: SLF001 - pas d'API publique pour redimensionner une colonne
        table.refresh(layout=True)


class WideTable(DataTable[Any]):
    """DataTable dont la derniere colonne prend la place restante, et la garde quand l'ecran change de taille ou
    que le contenu change."""

    _refit_pending = False

    def on_resize(self) -> None:
        self._schedule_refit()

    def add_row(self, *cells: Any, **options: Any) -> Any:
        key = super().add_row(*cells, **options)
        self._schedule_refit()
        return key

    def _schedule_refit(self) -> None:
        if not self._refit_pending:
            self._refit_pending = True
            self.call_after_refresh(self._refit)

    def _refit(self) -> None:
        self._refit_pending = False
        stretch_last_column(self)
