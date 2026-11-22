# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Applications omega qu'omega-connect reconnait (decision de l'auteur, 2026-11-22 : l'Installer propose tous les
outils publies, il faut donc les reconnaitre ensuite au Registre et dans l'Updater).

- `CONTRACT_TOOLS` (omega-lib, `TOOL_LAUNCHERS`) : outils a carte d'identite et liaisons (omega-serv, omega-fire,
  omega-jail, omega-stress) ; Synchronisation, Reparer et Liaisons les concernent.
- `OTHER_LAUNCHERS` : outils sans liaison (aucune carte d'identite a attendre d'eux) ; reconnus a leur lanceur et a
  leur paquet, etat « Installee », mis a jour et installes comme les autres.
omega-waf n'en fait pas partie : module Lua sans archive ni install.sh."""
from __future__ import annotations

from omega_lib.synchro.constants import TOOL_LAUNCHERS

CONTRACT_TOOLS = frozenset(TOOL_LAUNCHERS)
OTHER_LAUNCHERS: dict[str, str] = {
    tool: f"{tool}.sh" for tool in ("omega-suite", "omega-log", "omega-scan", "omega-check", "omega-deep",
                                    "omega-fold", "omega-track", "omega-fuzz", "omega-connect")
}
ALL_LAUNCHERS: dict[str, str] = {**TOOL_LAUNCHERS, **OTHER_LAUNCHERS}
INSTALLABLE_TOOLS: tuple[str, ...] = (
    "omega-serv", "omega-fire", "omega-jail", "omega-stress", "omega-log", "omega-suite", "omega-scan",
    "omega-check", "omega-deep", "omega-fold", "omega-track", "omega-fuzz", "omega-connect")
"""Ordre de l'Installer : les outils a liaisons d'abord."""


def has_contracts(tool: str) -> bool:
    """Carte d'identite et liaisons attendues de cet outil."""
    return tool in CONTRACT_TOOLS


def package_name(tool: str) -> str:
    return tool.replace("-", "_")
