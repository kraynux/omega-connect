# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Menu principal (refonte du parcours, proposition de l'auteur du 2026-11-10) : GESTION — Registre, Scanner,
Liaisons, Synchronisation, Dashboard | MAINTENANCE — Reparer, Rapport, Reglages, Aide, Quitter (5/5).

Liste extensible : omega-connect ira au-dela d'omega-serv et d'omega-fire (charge distribuee d'omega-stress,
par exemple) ; un nouveau theme = une entree ici et son ecran, rien d'autre a toucher dans l'accueil.
Retours de l'auteur (2026-11-10) : « Rapport » sous Registre, Contact et support dans l'Aide, « Quitter » pour
equilibrer les deux colonnes."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from omega_connect.shared.i18n import N_


class Column(str, Enum):
    MAIN = "main"
    MAINTENANCE = "maintenance"


@dataclass(frozen=True)
class MenuEntry:
    key: str
    label: str
    column: Column
    planned: str = ""
    """Lot qui construira l'ecran (vide : disponible)."""


MENU: tuple[MenuEntry, ...] = (
    MenuEntry("registry", N_("Registre"), Column.MAIN),
    MenuEntry("scanner", N_("Scanner"), Column.MAIN),
    MenuEntry("links", N_("Liaisons"), Column.MAIN),
    MenuEntry("synchronisation", N_("Synchronisation"), Column.MAIN),
    MenuEntry("dashboard", N_("Dashboard"), Column.MAIN),
    MenuEntry("repair", N_("Réparer"), Column.MAINTENANCE),
    MenuEntry("report", N_("Rapport"), Column.MAINTENANCE),
    MenuEntry("settings", N_("Réglages"), Column.MAINTENANCE),
    MenuEntry("help", N_("Aide"), Column.MAINTENANCE),
    MenuEntry("quit", N_("Quitter"), Column.MAINTENANCE),
)
"""Contact et support : dans l'Aide, comme les autres outils de la suite (lot F)."""
COLUMN_TITLES = {Column.MAIN: N_("GESTION"), Column.MAINTENANCE: N_("MAINTENANCE")}
