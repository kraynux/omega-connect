# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Vues des liens de `verifier` (meme moteur, meme rapport ; refonte R1) :

- Liaisons : les liens entre applications (l'espace partage et les cartes d'identite sont dans le Registre).
Le Dashboard est un ecran a part (screens/overview.py, vue d'ensemble)."""
from __future__ import annotations

from dataclasses import dataclass

from omega_connect.domain.links import CheckCode, Link, LinkKind, VerificationReport
from omega_connect.shared.i18n import N_

RIGHTS_CODES = frozenset({
    CheckCode.JAIL_LOG_OK, CheckCode.JAIL_LOG_ROOT_OWNED, CheckCode.JAIL_LOG_RIGHTS,
    CheckCode.BRIDGE_SCRIPT_OK, CheckCode.BRIDGE_SCRIPT_UNSAFE, CheckCode.BRIDGE_SCRIPT_RIGHTS,
    CheckCode.BLOCKLIST_OK, CheckCode.BLOCKLIST_ROOT_OWNED, CheckCode.BLOCKLIST_GROUP, CheckCode.BLOCKLIST_MODE,
    CheckCode.BLOCKLIST_OWNER, CheckCode.FILES_OK, CheckCode.FILE_UNSAFE, CheckCode.FILE_RIGHTS,
    CheckCode.TOKEN_OK, CheckCode.TOKEN_RIGHTS, CheckCode.ZONE_DIRECTORY_OK, CheckCode.ZONE_DIRECTORY_RIGHTS,
    CheckCode.ZONE_COPY_RIGHTS, CheckCode.ZONE_GROUP_MISSING, CheckCode.ZONE_MEMBER_OK,
    CheckCode.ZONE_MEMBER_MISSING, CheckCode.ZONE_RELOGIN, CheckCode.ZONE_UNREADABLE,
})


@dataclass(frozen=True)
class ViewSpec:
    key: str
    title: str
    hint: str
    kinds: frozenset[LinkKind] | None = None
    """Liens montres (None : tous)."""
    codes: frozenset[CheckCode] | None = None
    """Controles gardes dans chaque lien (None : tous) ; un lien sans controle garde disparait."""


LINKS = ViewSpec("links", N_("LIAISONS"), N_(
    "Ce qui est relié ou pas, sur toutes vos machines, avec son état (OK, à réparer, absent…). Cet écran montre : "
    "ce qui est « à réparer » se corrige dans le menu Réparer. Surlignez une ligne pour le détail."),
    frozenset({LinkKind.SERV_LOGS, LinkKind.MAGNET_LOGS, LinkKind.BRIDGE, LinkKind.PROTECTED_LIST,
               LinkKind.BLOCKLIST, LinkKind.FAIL2BAN_FILES, LinkKind.TOKENS, LinkKind.ZONE}))
VIEWS = {view.key: view for view in (LINKS,)}


def view_links(report: VerificationReport, view: ViewSpec) -> tuple[Link, ...]:
    links = [link for link in report.links if view.kinds is None or link.kind in view.kinds]
    if view.codes is not None:
        links = [Link(link.kind, link.instance, link.root, kept) for link in links
                 if (kept := tuple(check for check in link.checks if check.code in view.codes))]
    return tuple(links)
