# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lignes du tableau de bord (outils, liens, controles), a partir des memes libelles que la ligne de commande :
une seule source de texte pour `verifier` et l'interface."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from omega_lib.synchro.models import ReadStatus
from omega_lib.synchro.policies import parse_utc
from rich.text import Text

from omega_connect.domain.detection import DetectedInstallation
from omega_connect.domain.links import Check, CheckStatus, Link, LinkState, Provenance, VerificationReport
from omega_connect.interfaces.cli.detection_view import SHEET_LABELS, TOKEN_LABELS, note_text
from omega_connect.interfaces.cli.verification_view import (
    CHECK_MARKS,
    LINK_LABELS,
    STATE_LABELS,
    STATE_MARKS,
    check_text,
    fix_lines,
)
from omega_connect.shared.i18n import N_, _

STATE_STYLE_KEYS = {
    LinkState.ACTIVE: "success", LinkState.DEGRADED: "warning", LinkState.BROKEN: "error",
    LinkState.ABSENT: "dim", LinkState.UNVERIFIABLE: "secondary",
}
CHECK_STYLE_KEYS = {
    CheckStatus.OK: "success", CheckStatus.INFO: "dim", CheckStatus.WARNING: "warning",
    CheckStatus.FAILURE: "error", CheckStatus.UNVERIFIABLE: "secondary",
}
MACHINE = N_("machine")
TABLE_SHEET_LABELS = {**SHEET_LABELS, ReadStatus.ABSENT: N_("non fournie (ancienne version)")}
"""Libelle court dans la table : la phrase complete de `detecter` la ferait deborder."""


def _style(styles: Mapping[str, str], key: str) -> str:
    return "dim" if key == "dim" else styles.get(key, "")


def _clock(moment: datetime | None) -> str:
    return moment.astimezone().strftime("%H:%M:%S") if moment is not None else "?"


def state_text(state: LinkState, styles: Mapping[str, str]) -> Text:
    return Text(f"{STATE_MARKS[state]} {_(STATE_LABELS[state])}", style=_style(styles, STATE_STYLE_KEYS[state]))


def tool_row(item: DetectedInstallation) -> tuple[str, str, str, str, str, str]:
    sheet = item.sheet.sheet if item.sheet is not None else None
    version = item.token.version if item.token is not None else (sheet.version if sheet is not None else "?")
    if sheet is not None and sheet.service is not None:
        service = f"{sheet.service.unit or sheet.service.manager} ({sheet.service.state or '?'})"
    else:
        service = ", ".join(item.service_names) or "—"
    token = _(TOKEN_LABELS[item.token_status])
    if item.sheet is None:
        declared = "—"
    elif sheet is None:
        declared = _(TABLE_SHEET_LABELS.get(item.sheet.status, N_("non obtenue")))
    else:
        declared = _("déclarée à {time}").format(time=_clock(parse_utc(sheet.generated_at)))
        if sheet.partial:
            declared += " " + _("(partielle)")
    instance = sheet.instance if sheet is not None and sheet.instance != item.tool else ""
    tool = f"{item.tool or _('outil inconnu')}" + (f" « {instance} »" if instance else "")
    return tool, item.root, version, service, token, declared


def problem_count(link: Link) -> int:
    return sum(1 for check in link.checks if check.status in (CheckStatus.WARNING, CheckStatus.FAILURE))


def provenance_text(link: Link, styles: Mapping[str, str]) -> Text:
    """« Local » ou « Réseau — machine (→ autre machine) », en couleur distincte (demande de l'auteur)."""
    if link.provenance is Provenance.LOCAL:
        return Text(_("Local"), style=_style(styles, "success"))
    where = link.machine + (f" → {link.peer}" if link.peer else "")
    return Text(_("Réseau — {where}").format(where=where), style=f"bold {_style(styles, 'secondary')}")


def link_row(link: Link, styles: Mapping[str, str]) -> tuple[Text, Text, str, str, str]:
    count = problem_count(link)
    if count:
        summary = _("{count} écart(s)").format(count=count)
    else:
        # Lien non verifiable : la raison d'abord (decision de l'auteur, 2026-11-10).
        first = next((check for check in link.checks if check.status is CheckStatus.UNVERIFIABLE), None) or next(
            (check for check in link.checks if check.status is not CheckStatus.OK), None)
        summary = check_text(first) if first is not None else _("conforme")
    return (state_text(link.state, styles), provenance_text(link, styles), _(LINK_LABELS[link.kind]),
            link.instance or _(MACHINE), summary)


def check_lines(link: Link, styles: Mapping[str, str], *, with_ok: bool) -> Text:
    """Controles d'un lien, chacun suivi de sa commande de correction (jamais lancee)."""
    text = Text()
    hidden = 0
    for check in link.checks:
        if check.status is CheckStatus.OK and not with_ok:
            hidden += 1
            continue
        _append_check(text, check, styles)
    if hidden:
        hint = _("{count} contrôle(s) conforme(s) : « Détail du lien » pour les voir.").format(count=hidden)
        text.append(hint + "\n", style="dim")
    if not text:
        text.append(_("Aucun contrôle pour ce lien.") + "\n", style="dim")
    return text


def _append_check(text: Text, check: Check, styles: Mapping[str, str]) -> None:
    text.append(f"{CHECK_MARKS[check.status]} ", style=_style(styles, CHECK_STYLE_KEYS[check.status]))
    text.append(check_text(check) + "\n")
    for line in fix_lines(check):
        text.append(f"    {line}\n", style="bold")


def summary_text(report: VerificationReport, styles: Mapping[str, str]) -> Text:
    text = Text()
    text.append(_("Liens : "), style="bold")
    first = True
    for state in LinkState:
        count = sum(1 for link in report.links if link.state is state)
        if not count:
            continue
        text.append("" if first else " · ")
        text.append(f"{count} {_(STATE_LABELS[state])}", style=_style(styles, STATE_STYLE_KEYS[state]))
        first = False
    if first:
        text.append("0")
    return text


def scan_lines(report: VerificationReport) -> list[str]:
    detection = report.detection
    lines = [note_text(note) for note in detection.scan_notes]
    lines.extend(_("Identifiant en double {identifier} : {roots}").format(
        identifier=duplicate.installation_id[:8], roots=", ".join(duplicate.roots))
        for duplicate in detection.duplicates)
    return lines
