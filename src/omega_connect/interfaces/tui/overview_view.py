# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Texte des cadres du Dashboard (refonte, demande de l'auteur 2026-11-11), a partir de `domain/overview.py`.

Memes mots et memes symboles que le reste de l'application : etats des applications (Registre), etats des
liaisons (Liaisons, Reparer, Rapport). Aucun mot technique (controle, constat, jeton...)."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from rich.cells import cell_len
from rich.text import Text

from omega_connect.domain.fleet import AppState
from omega_connect.domain.links import LinkState
from omega_connect.domain.overview import TOP_NARROW, TOP_WIDE, Overview
from omega_connect.interfaces.cli.enroll_view import SPACE_LABELS
from omega_connect.interfaces.cli.enroll_view import STATE_LABELS as APP_LABELS
from omega_connect.interfaces.cli.enroll_view import STATE_MARKS as APP_MARKS
from omega_connect.interfaces.cli.verification_view import LINK_LABELS, STATE_LABELS, STATE_MARKS
from omega_connect.interfaces.tui.presentation import STATE_STYLE_KEYS
from omega_connect.interfaces.tui.widgets.states import STATE_STYLE_KEYS as APP_STYLE_KEYS
from omega_connect.interfaces.tui.widgets.states import SUMMARY_ORDER
from omega_connect.shared.i18n import N_, _

BAR = 12
NARROW_WIDTH = 100
NARROW_HEIGHT = 30
"""En dessous (largeur ou hauteur du terminal) : « ecran mini », les tops passent de 5 a 3."""

TITLES = {
    "machines": N_("MACHINES"),
    "applications": N_("APPLICATIONS"),
    "links": N_("LIAISONS"),
    "space": N_("ESPACE PARTAGÉ"),
    "kinds": N_("LIAISONS PAR TYPE"),
    "sides": N_("CETTE MACHINE / RÉSEAU"),
}
TOP_TITLES = {
    "top-machines": N_("TOP {count} · MACHINES À RÉPARER"),
    "top-links": N_("TOP {count} · LIAISONS À RÉPARER"),
    "top-versions": N_("TOP {count} · VERSIONS EN RETARD"),
    "top-oldest": N_("TOP {count} · SCANS LES PLUS ANCIENS"),
}


def top_size(width: int, height: int) -> int:
    return TOP_NARROW if width < NARROW_WIDTH or height < NARROW_HEIGHT else TOP_WIDE


def _pad(text: str, width: int) -> str:
    """Complete a `width` colonnes d'ecran (un ideogramme en occupe deux)."""
    return text + " " * max(0, width - cell_len(text))


def _style(styles: Mapping[str, str], key: str) -> str:
    return "dim" if key == "dim" else styles.get(key, key)


def _link_line(text: Text, state: LinkState, count: int, styles: Mapping[str, str]) -> None:
    text.append(f"{STATE_MARKS[state]} {count} {_(STATE_LABELS[state])}\n",
                style=f"bold {_style(styles, STATE_STYLE_KEYS[state])}" if count else "dim")


def _app_line(text: Text, state: AppState, count: int, styles: Mapping[str, str]) -> None:
    text.append(f"{APP_MARKS[state]} {count} {_(APP_LABELS[state])}\n",
                style=f"bold {_style(styles, APP_STYLE_KEYS[state])}" if count else "dim")


def ago(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return _("jamais vue")
    seconds = max(0, int((now - moment).total_seconds()))
    if seconds < 60:
        return _("à l'instant")
    if seconds < 3600:
        return _("il y a {count} min").format(count=seconds // 60)
    if seconds < 86400:
        return _("il y a {count} h").format(count=seconds // 3600)
    return _("il y a {count} j").format(count=seconds // 86400)


# ---- compteurs ---------------------------------------------------------------

def machines_card(overview: Overview, styles: Mapping[str, str]) -> Text:
    text = Text()
    text.append(_("{count} au total").format(count=len(overview.machines)) + "\n", style="bold")
    for machine in overview.local:
        text.append(_("cette machine : {name}").format(name=machine.name) + "\n")
    text.append(_("{count} sur le réseau").format(count=len(overview.network)) + "\n")
    unreachable = overview.unreachable
    text.append(f"{APP_MARKS[AppState.UNREACHABLE]} " + _("{count} injoignable(s)").format(count=unreachable),
                style=f"bold {_style(styles, 'error')}" if unreachable else "dim")
    return text


def applications_card(overview: Overview, styles: Mapping[str, str]) -> Text:
    counts = overview.app_states()
    text = Text()
    for state in SUMMARY_ORDER:
        if state is not AppState.UNREACHABLE or counts[state]:
            _app_line(text, state, counts[state], styles)
    text.rstrip()
    return text


def links_card(overview: Overview, styles: Mapping[str, str]) -> Text:
    counts = overview.link_states()
    text = Text()
    for state in LinkState:
        _link_line(text, state, counts[state], styles)
    text.rstrip()
    return text


def space_card(overview: Overview, styles: Mapping[str, str]) -> Text:
    states = overview.app_states()
    text = Text()
    text.append(_(SPACE_LABELS[overview.space]) + "\n", style="bold")
    linked = states[AppState.LINKED]
    text.append(f"{APP_MARKS[AppState.LINKED]} " + _("{count} application(s) reliée(s)").format(count=linked) + "\n",
                style=_style(styles, "success") if linked else "dim")
    waiting = states[AppState.DETECTED] + states[AppState.ENROLLED]
    text.append(f"{APP_MARKS[AppState.ENROLLED]} " + _("{count} à relier (Synchronisation)").format(count=waiting),
                style=f"bold {_style(styles, 'warning')}" if waiting else "dim")
    return text


# ---- liaisons par type, cette machine / reseau ----------------------------------

def kinds_card(overview: Overview, styles: Mapping[str, str], width: int = 0) -> Text:
    """`width` : largeur utile du cadre (0 : inconnue). La barre se raccourcit pour tenir sur la ligne ; trop
    etroit, le libelle passe sur sa propre ligne."""
    rows = overview.by_kind()
    text = Text()
    if not rows:
        text.append(_("Aucune liaison connue."), style="dim")
        return text
    label_width = max(cell_len(_(LINK_LABELS[row.kind])) for row in rows)
    digits = len(str(max(row.total for row in rows)))
    tail = 2 + (2 + 2 * digits + 1) + (2 + 1 + digits) + 1  # ecart, « x/y », « !n », marge
    bar = min(BAR, width - label_width - tail) if width else BAR
    own_line = bar < 4
    if own_line:
        bar = max(4, min(BAR, width - tail)) if width else BAR
    for row in rows:
        if own_line:
            text.append(f"{_(LINK_LABELS[row.kind])}\n")
        else:
            text.append(_pad(_(LINK_LABELS[row.kind]), label_width) + "  ")
        ok = round(bar * row.ok / row.total)
        bad = min(bar - ok, max(1, round(bar * row.to_fix / row.total))) if row.to_fix else 0
        text.append("█" * ok, style=_style(styles, "success"))
        text.append("█" * bad, style=_style(styles, "warning"))
        text.append("░" * (bar - ok - bad), style="dim")
        text.append(f"  {row.ok}/{row.total}")
        if row.to_fix:  # le symbole dit aussi « a reparer » sans couleur (profil monochrome)
            text.append(f"  {STATE_MARKS[LinkState.DEGRADED]}{row.to_fix}", style=f"bold {_style(styles, 'warning')}")
        text.append("\n")
    text.rstrip()
    return text


def sides_card(overview: Overview, styles: Mapping[str, str]) -> Text:
    """Tableau a trois colonnes. Libelles et chiffres sont des morceaux de styles differents : en arabe, chaque
    morceau est mis dans l'ordre de lecture a sa place, sans echanger les colonnes (omega_lib terminal_bidi)."""
    local, network = overview.side(True), overview.side(False)
    labels = [_("Machines"), _("Applications"), *(_(STATE_LABELS[state]) for state in LinkState)]
    width = max(cell_len(label) for label in labels) + 4
    left, right = _("Cette machine"), _("Réseau")
    column = max(cell_len(left), cell_len(right)) + 2
    text = Text()

    def cell(value: str, style: str) -> None:
        text.append(" " * (column - cell_len(value)))
        text.append(value, style=style)

    text.append(" " * width)
    cell(left, "bold")
    cell(right, "bold")
    text.append("\n")
    rows = [(labels[0], local.machines, network.machines, ""), (labels[1], local.applications,
                                                                 network.applications, "")]
    for index, state in enumerate(LinkState):
        here, there = local.states[state], network.states[state]
        style = _style(styles, STATE_STYLE_KEYS[state]) if here or there else "dim"
        rows.append((f"{STATE_MARKS[state]} {labels[2 + index]}", here, there, style))
    for label, here, there, style in rows:
        text.append(_pad(label, width), style=style or "none")
        cell(str(here), f"bold {style}".strip())
        cell(str(there), f"bold {style}".strip())
        text.append("\n")
    text.rstrip()
    return text


# ---- tops --------------------------------------------------------------------

def _empty(text: Text, message: str) -> Text:
    text.append(message, style="dim")
    return text


def top_machines_card(overview: Overview, size: int, styles: Mapping[str, str]) -> Text:
    text = Text()
    found = overview.top_machines(size)
    if not found:
        return _empty(text, _("Rien à réparer."))
    for index, machine in enumerate(found, 1):
        text.append(f"{index}. {machine.name}\n", style="bold")
        parts = []
        if machine.links_to_fix:
            parts.append(_("{count} liaison(s)").format(count=machine.links_to_fix))
        if machine.apps_to_fix:
            parts.append(_("{count} application(s)").format(count=machine.apps_to_fix))
        state = LinkState.BROKEN if machine.blocking else LinkState.DEGRADED
        text.append(f"   {STATE_MARKS[state]} " + " · ".join(parts) + "\n",
                    style=_style(styles, STATE_STYLE_KEYS[state]))
    text.rstrip()
    return text


def top_links_card(overview: Overview, size: int, styles: Mapping[str, str]) -> Text:
    text = Text()
    found = overview.top_links(size)
    if not found:
        return _empty(text, _("Aucune liaison à réparer."))
    for index, (link, machine) in enumerate(found, 1):
        text.append(f"{index}. {STATE_MARKS[link.state]} {_(LINK_LABELS[link.kind])}\n",
                    style=f"bold {_style(styles, STATE_STYLE_KEYS[link.state])}")
        text.append(f"   {machine}" + (f" · {link.instance}" if link.instance else "") + "\n", style="dim")
    text.rstrip()
    return text


def top_versions_card(overview: Overview, size: int, styles: Mapping[str, str]) -> Text:
    text = Text()
    found = overview.top_versions(size)
    if not found:
        return _empty(text, _("Aucune application en retard."))
    for index, row in enumerate(found, 1):
        text.append(f"{index}. {row.tool} {row.version or '?'}", style="bold")
        text.append(f" — {APP_MARKS[row.state]} {_(APP_LABELS[row.state])}\n",
                    style=_style(styles, APP_STYLE_KEYS[row.state]))
        text.append(f"   {row.machine}\n", style="dim")
    text.rstrip()
    return text


def top_oldest_card(overview: Overview, size: int, styles: Mapping[str, str], now: datetime) -> Text:
    text = Text()
    found = overview.top_oldest(size)
    if not found:
        return _empty(text, _("Aucune machine du réseau (menu Scanner)."))
    for index, machine in enumerate(found, 1):
        text.append(f"{index}. {machine.name}", style="bold")
        text.append(" — " + _("vue {when}").format(when=ago(machine.seen_at, now)))
        if not machine.reachable:
            text.append(f" · {APP_MARKS[AppState.UNREACHABLE]} {_(APP_LABELS[AppState.UNREACHABLE])}",
                        style=f"bold {_style(styles, 'error')}")
        text.append("\n")
    text.rstrip()
    return text
