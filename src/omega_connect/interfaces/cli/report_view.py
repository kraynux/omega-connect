# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Rendus du rapport complet : texte (francais de reference), JSON (jamais traduit, versionne) et HTML autonome
(une seule page, styles en ligne, theme d'export d'omega-lib). Tout texte venant de la machine est echappe."""
from __future__ import annotations

import html
from collections.abc import Iterable
from importlib import resources
from typing import Any

from omega_lib.synchro.models import ReadStatus
from omega_lib.synchro.policies import parse_utc
from omega_lib.synchro.registry import CreatedKind, ZoneState, registry_to_dict
from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES

from omega_connect.application.report import FullReport
from omega_connect.domain.detection import DetectedInstallation, DetectionReport
from omega_connect.domain.fleet import AppState, RegistryRow, Todo, space_status, todo
from omega_connect.domain.links import CheckStatus, Link, LinkState, VerificationReport
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.problems import ProblemKind, problems
from omega_connect.domain.versions import CONTRACT_VERSIONS
from omega_connect.interfaces.cli.detection_view import (
    SHEET_LABELS,
    SOURCE_LABELS,
    TOKEN_LABELS,
    note_text,
)
from omega_connect.interfaces.cli.enroll_view import SPACE_LABELS, STATE_MARKS
from omega_connect.interfaces.cli.enroll_view import STATE_LABELS as APP_STATE_LABELS
from omega_connect.interfaces.cli.verification_view import (
    LINK_LABELS,
    STATE_LABELS,
    check_text,
    fix_lines,
    verification_to_dict,
)
from omega_connect.interfaces.cli.verification_view import render_text as render_verification
from omega_connect.shared.i18n import N_, _

REPORT_FORMAT = "omega-connect-rapport"
REPORT_SCHEMA_VERSION = 2
"""2 (2026-11-11) : machine, applications de toutes les machines, machines du reseau, « a faire »."""
KIND_LABELS = {CreatedKind.GROUP: N_("groupe"), CreatedKind.DIRECTORY: N_("dossier"),
               CreatedKind.MEMBER: N_("membre du groupe"),
               CreatedKind.SERVICE_GROUP: N_("groupe donné au service (par omega-serv)")}
"""Une seule liste pour le rapport et l'ecran Detail (un type de creation oublie faisait planter le rapport le
2026-11-10, juste apres la premiere synchronisation reelle) ; un test exige un libelle pour chaque type."""
ZONE_STATE_LABELS = {ZoneState.ACTIVE: N_("active (synchronisée)"), ZoneState.FROZEN: N_("figée (plus synchronisée)")}


def local_time(text: str) -> str:
    moment = parse_utc(text)
    return moment.astimezone().strftime("%d/%m/%Y %H:%M:%S") if moment is not None else text


def export_name(report: FullReport, extension: str) -> str:
    stamp = (report.generated_at.replace("-", "").replace(":", "").replace("T", "-").rstrip("Z"))
    return f"omega-connect-rapport-{stamp}.{extension}"


def _counts(links: Iterable[Link]) -> dict[LinkState, int]:
    counts = dict.fromkeys(LinkState, 0)
    for link in links:
        counts[link.state] += 1
    return counts


def _zone_status_text(report: FullReport) -> str:
    if not report.zone_present:
        return _("Pas encore d'espace partagé sur cette machine ({zone}) : la Synchronisation le prépare.").format(
            zone=report.zone_path)
    if report.registry.status is ReadStatus.UNREADABLE:
        return _("Espace partagé {zone} présent, lisible par root et le groupe omega-synchro seulement (rapport "
                 "fait sans sudo ; le groupe compte après une reconnexion).").format(zone=report.zone_path)
    if report.registry.value is None:
        return _("Espace partagé {zone} : registre {status} ({detail}).").format(
            zone=report.zone_path, status=report.registry.status.value, detail=report.registry.detail or "?")
    registry = report.registry.value
    return _("Espace partagé {zone} — {state} — mis à jour le {date}.").format(
        zone=registry.zone, state=_(ZONE_STATE_LABELS[registry.state]), date=local_time(registry.updated_at))


def _all_links(report: FullReport) -> tuple[Link, ...]:
    return report.verification.links + tuple(link for machine in report.machines for link in machine.links)


def _state_summary(rows: Iterable[RegistryRow]) -> str:
    counts = {state: 0 for state in AppState}
    for row in rows:
        counts[row.state] += 1
    return ", ".join(f"{STATE_MARKS[state]} {counts[state]} {_(APP_STATE_LABELS[state])}"
                     for state in AppState if counts[state]) or _("aucune")


def _is_local(report: FullReport, row: RegistryRow) -> bool:
    return row.machine == (report.machine or "local")


def update_text(report: FullReport, row: RegistryRow) -> str:
    if row.state is AppState.INCOMPLETE:
        what = _("{tool} {version} : installation inachevée → « Réinstaller l'application »").format(
            tool=row.tool, version=row.version or "?")
    else:
        what = _("{tool} {version} → {minimum} ou plus récent : « Mettre à jour l'application »").format(
            tool=row.tool, version=row.version or "?", minimum=CONTRACT_VERSIONS.get(row.tool, "?"))
    if _is_local(report, row):
        what = _("{tool} {version} : à mettre à jour sur ce poste, section « Mise à jour » du README de "
                 "l'outil").format(tool=row.tool, version=row.version or "?")
    return what


def _repair_lines(report: FullReport) -> list[str]:
    """Une ligne par ecart a reparer : machine, liaison, ce qui ne va pas, et qui le corrige."""
    local_rows = tuple(row for row in report.rows if _is_local(report, row))
    lines = []
    for problem in problems(report.machine or "local", report.verification.links, local_rows, report.machines):
        if problem.kind is not ProblemKind.REPAIR or problem.link is None:
            continue
        link = problem.link
        name = _(LINK_LABELS[link.kind]) + (f" « {link.instance} »" if link.instance else "")
        for check in link.checks:
            if check.status not in (CheckStatus.WARNING, CheckStatus.FAILURE):
                continue
            if check.repair is not None:
                how = _("corrigé par l'outil lui-même (menu Réparer)")
            elif check.fix and problem.local:
                how = _("commande à lancer sur ce poste : {command}").format(command=check.fix)
            elif check.fix:
                how = _("commande lancée sur la machine par le menu Réparer : {command}").format(command=check.fix)
            else:
                how = _("aucune correction connue")
            lines.append(f"{problem.machine} — {name} : {check_text(check)} — {how}")
    return lines


def _todo_sections(report: FullReport, plan: Todo) -> list[tuple[str, list[str]]]:
    """(titre, lignes) de « A faire », dans l'ordre des gestes."""
    sections: list[tuple[str, list[str]]] = []
    if plan.unreachable:
        sections.append((_("Machines qui ne répondent plus — Scanner → « Rescanner les machines connues »"),
                         list(plan.unreachable)))
    if plan.update:
        sections.append((_("À réinstaller ou à mettre à jour — Registre, bouton sous la ligne"),
                         [f"{row.machine} — {update_text(report, row)}" for row in plan.update]))
    repairs = _repair_lines(report)
    if repairs:
        sections.append((_("À réparer — menu Réparer"), repairs))
    if plan.sync:
        sections.append((_("À synchroniser — menu Synchronisation"),
                         [_("{machine} — {tool} : {state}").format(machine=row.machine, tool=row.tool,
                                                                  state=_(APP_STATE_LABELS[row.state]))
                          for row in plan.sync]))
    return sections


def _tools_text(detection: DetectionReport) -> str:
    """Les applications de cette machine, en clair (sans le vocabulaire de la commande `detecter`)."""
    lines = []
    for item in detection.installations:
        sheet = item.sheet.sheet if item.sheet is not None else None
        version = item.version or (item.token.version if item.token is not None else "") or "?"
        lines.append(f"  {item.tool or _('application inconnue')} {version} — {item.root}")
        lines.append("    " + _("propriétaire : {owner} ; trouvée par : {sources}").format(
            owner=item.owner or "?", sources=", ".join(_(SOURCE_LABELS[source]) for source in item.sources)))
        card = _(TOKEN_LABELS[item.token_status]) + (
            f" ({item.token.installation_id[:8]}…)" if item.token is not None else "")
        lines.append("    " + _("carte d'identité : {card}").format(card=card))
        if sheet is not None:
            what = _("instance {instance}").format(instance=sheet.instance)
            if sheet.service is not None:
                what += f" · {sheet.service.unit or sheet.service.manager} ({sheet.service.state or '?'})"
            lines.append("    " + _("description : {what}").format(what=what))
        elif item.sheet is not None:
            lines.append("    " + _("description : {what}").format(
                what=_(SHEET_LABELS.get(item.sheet.status, N_("non obtenue")))))
    notes = [note_text(note) for note in detection.scan_notes]
    if notes:
        lines.append("  " + _("Remarques :"))
        lines += [f"    - {note}" for note in notes]
    return "\n".join(lines) if lines else "  " + _("Aucune application omega trouvée.")


def _machine_line(machine: MachineEntry) -> str:
    state = _("répond") if machine.reachable else _("injoignable")
    line = _("{machine} — {target} — {state} — dernier scan {date} — {apps} application(s), {links} "
             "liaison(s)").format(machine=machine.label, target=machine.target or "?", state=state,
                                  date=local_time(machine.scanned_at) if machine.scanned_at else "?",
                                  apps=len(machine.rows), links=len(machine.links))
    if machine.last_error:
        line += " — " + _("dernière erreur : {error}").format(error=machine.last_error)
    return line


# ---- texte ----------------------------------------------------------------------------------------

def render_report_text(report: FullReport) -> str:
    rule = "=" * 78
    machine = report.machine or "?"
    lines = [rule, _("OMEGA-CONNECT {version} — RAPPORT COMPLET").format(version=report.version),
             _("Établi le {date} depuis {machine}, machines du réseau rescannées (lecture seule, sans "
               "root).").format(date=local_time(report.generated_at), machine=machine), rule, ""]
    links = _all_links(report)
    counts = _counts(links)
    link_summary = ", ".join(f"{counts[state]} {_(STATE_LABELS[state])}" for state in LinkState if counts[state])
    lines += [_("BILAN"),
              "  " + _("{machines} machine(s) : {machine} et {remote} du réseau.").format(
                  machines=1 + len(report.machines), machine=machine, remote=len(report.machines)),
              "  " + _("{count} application(s) : {summary}.").format(count=len(report.rows),
                                                                     summary=_state_summary(report.rows)),
              "  " + _("{count} liaison(s) : {summary}.").format(count=len(links), summary=link_summary or "0"),
              "  " + _("Espace partagé de {machine} : {state}.").format(
                  machine=machine, state=_(SPACE_LABELS[space_status(report.verification)])), ""]
    plan = todo(report.rows)
    lines.append(_("À FAIRE"))
    if plan.empty and not _repair_lines(report):
        lines.append("  " + _("Rien à faire : toutes les applications sont à jour et reliées."))
    for title, items in _todo_sections(report, plan):
        lines.append("  " + title + " :")
        lines += [f"    · {item}" for item in items]
    lines.append("")
    lines.append(_("REGISTRE — APPLICATIONS PAR MACHINE"))
    for row in report.rows:
        service = f" « {row.instance} »" if row.instance else ""
        lines.append(f"  {STATE_MARKS[row.state]} {_(APP_STATE_LABELS[row.state]):<23} {row.machine:<26} "
                     f"{row.tool}{service} {row.version or '?'} — {row.root}")
    if not report.rows:
        lines.append("  " + _("Aucune application omega trouvée."))
    lines += ["", _("MACHINES DU RÉSEAU")]
    lines += [f"  · {_machine_line(entry)}" for entry in report.machines] or [
        "  " + _("Aucune (Scanner → machine distante, pour en ajouter).")]
    lines += ["", _("APPLICATIONS DE {machine} EN DÉTAIL").format(machine=machine.upper()),
              _tools_text(report.verification.detection), ""]
    lines += [_("LIAISONS DE {machine} (tous les contrôles)").format(machine=machine.upper()),
              render_verification(report.verification, with_details=True, bare=True), ""]
    for entry in report.machines:
        lines.append(_("LIAISONS DE {machine} (réseau, scan du {date})").format(
            machine=entry.label.upper(), date=local_time(entry.scanned_at) if entry.scanned_at else "?"))
        if entry.links:
            lines.append(render_verification(VerificationReport(DetectionReport("", ()), entry.links),
                                             with_details=True, bare=True))
        else:
            lines.append("  " + _("Aucune liaison relevée."))
        lines.append("")
    lines += [_("ESPACE PARTAGÉ (omega-synchro) DE {machine} ET SON REGISTRE").format(machine=machine.upper()),
              "  " + _zone_status_text(report)]
    registry = report.registry.value
    if registry is not None:
        lines.append("  " + _("Créé par omega-connect :"))
        lines += [f"    - {_(KIND_LABELS[item.kind])} {item.target} ({local_time(item.at)})"
                  for item in registry.created] or ["    " + _("rien")]
        lines.append("  " + _("Applications reliées :"))
        lines += [f"    - {item.tool} « {item.instance} » {item.root} ({item.installation_id[:8]}, "
                  f"{item.version}, {_('reliée le')} {local_time(item.linked_at)})"
                  for item in registry.installations] or ["    " + _("aucune")]
    return "\n".join(lines) + "\n"


# ---- JSON -----------------------------------------------------------------------------------------

def _row_to_dict(report: FullReport, row: RegistryRow) -> dict[str, Any]:
    return {"machine": row.machine, "local": _is_local(report, row), "tool": row.tool, "root": row.root,
            "instance": row.instance, "service_state": row.service_state, "version": row.version,
            "state": row.state.value, "findings": len(row.findings)}


def report_to_dict(report: FullReport) -> dict[str, Any]:
    registry = report.registry.value
    plan = todo(report.rows)
    return {
        "format": REPORT_FORMAT, "schema_version": REPORT_SCHEMA_VERSION,
        "omega_connect_version": report.version, "generated_at": report.generated_at, "machine": report.machine,
        "summary": {state.value: count for state, count in _counts(_all_links(report)).items()},
        "applications_summary": {state.value: sum(1 for row in report.rows if row.state is state)
                                 for state in AppState},
        "todo": {"update": [_row_to_dict(report, row) for row in plan.update],
                 "repair": [_row_to_dict(report, row) for row in plan.repair],
                 "sync": [_row_to_dict(report, row) for row in plan.sync],
                 "unreachable": list(plan.unreachable)},
        "applications": [_row_to_dict(report, row) for row in report.rows],
        "machines": [{"name": entry.name, "label": entry.label, "target": entry.target,
                      "fingerprint": entry.fingerprint, "addresses": list(entry.addresses),
                      "scanned_at": entry.scanned_at, "reachable": entry.reachable, "last_error": entry.last_error,
                      "applications": len(entry.rows),
                      "links": verification_to_dict(VerificationReport(DetectionReport("", ()), entry.links))["links"]}
                     for entry in report.machines],
        "verification": verification_to_dict(report.verification),
        "zone": {"path": report.zone_path, "present": report.zone_present,
                 "registry_status": report.registry.status.value, "registry_detail": report.registry.detail,
                 "registry": registry_to_dict(registry) if registry is not None else None},
    }


# ---- HTML -----------------------------------------------------------------------------------------
# Meme cadre que les rapports HTML d'omega-fire (« fenetre de terminal » : fond, conteneur et panneaux superposes,
# cartes, tableaux, badges, pied de page). Feuilles reprises telles quelles dans report_styles/ : base.css et une
# palette par theme d'export d'omega-lib (memes variables CSS).

STYLES = "omega_connect.interfaces.cli.report_styles"
STATE_BADGES = {LinkState.ACTIVE: "success", LinkState.DEGRADED: "warning", LinkState.BROKEN: "danger",
                LinkState.ABSENT: "neutral", LinkState.UNVERIFIABLE: "info"}
APP_BADGES = {AppState.LINKED: "success", AppState.ENROLLED: "info", AppState.DETECTED: "warning",
              AppState.TO_FIX: "danger", AppState.OLD_VERSION: "neutral", AppState.INCOMPLETE: "warning",
              AppState.UNREACHABLE: "danger"}
CHECK_BADGES = {CheckStatus.OK: "success", CheckStatus.INFO: "neutral", CheckStatus.WARNING: "warning",
                CheckStatus.FAILURE: "danger", CheckStatus.UNVERIFIABLE: "info"}
EXTRA_CSS = """
        .exec-summary {
            background-color: var(--bg-header);
            border: 1px solid var(--border-header);
            border-radius: 4px;
            padding: 1.4rem 1.8rem;
            margin-bottom: 2rem;
            font-size: 0.9rem;
        }
        .exec-summary p + p { margin-top: 0.3rem; }
        .reco-item .value.success { color: var(--status-success-text); }
        .reco-item .value.warning { color: var(--status-warning-text); }
        .reco-item .value.danger { color: var(--status-danger-text); }
        .reco-item .value.info { color: var(--status-info-text); }
        .reco-item .value.neutral { color: var(--status-neutral-text); }
        .reco-item .value { font-size: 1.4rem; font-weight: 600; }
        td.nowrap, td:first-child { white-space: nowrap; }
        .link-card {
            background-color: var(--bg-panel);
            border: 1px solid var(--border-panel);
            border-inline-start: 3px solid var(--status-neutral-border);
            border-radius: 4px;
            padding: 1rem 1.4rem;
            margin-bottom: 0.9rem;
        }
        .link-card.success { border-inline-start-color: var(--status-success-text); }
        .link-card.warning { border-inline-start-color: var(--status-warning-text); }
        .link-card.danger { border-inline-start-color: var(--status-danger-text); }
        .link-card.info { border-inline-start-color: var(--status-info-text); }
        .link-head { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; }
        .link-name { color: var(--text-heading); font-weight: 600; }
        .link-where { color: var(--text-muted); font-size: 0.8rem; width: 100%; word-break: break-all; }
        .checks { list-style: none; margin-top: 0.6rem; }
        .checks li { font-size: 0.86rem; color: var(--text-table-cell); margin-bottom: 0.45rem; }
        .checks .badge { min-width: 7.5rem; text-align: center; margin-inline-end: 0.6rem; }
        .fix {
            display: block;
            margin: 0.3rem 0 0 8.2rem;
            padding: 0.3rem 0.7rem;
            background-color: var(--bg-table-wrapper);
            border: 1px solid var(--border-default);
            border-radius: 3px;
            color: var(--text-value);
            font-size: 0.8rem;
            word-break: break-all;
        }
        .note-list { list-style: none; }
        .note-list li::before { content: "› "; color: var(--text-accent); }
"""
CHECK_LABELS = {CheckStatus.OK: N_("conforme"), CheckStatus.INFO: N_("info"), CheckStatus.WARNING: N_("écart"),
                CheckStatus.FAILURE: N_("échec"), CheckStatus.UNVERIFIABLE: N_("non vérifiable")}


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _style(name: str) -> str:
    return resources.files(STYLES).joinpath(name).read_text(encoding="utf-8")


def _badge(kind: str, text: str) -> str:
    return f'<span class="badge badge-{kind}">{_e(text)}</span>'


def _table(headers: list[str], rows: Iterable[list[str]], *, raw_columns: frozenset[int] = frozenset()) -> str:
    """`raw_columns` : colonnes deja en HTML (badges), toutes les autres sont echappees."""
    head = "".join(f"<th>{_e(cell)}</th>" for cell in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell if index in raw_columns else _e(cell)}</td>"
                                    for index, cell in enumerate(row)) + "</tr>" for row in rows)
    return f'<div class="table-wrapper"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _tool_row(item: DetectedInstallation) -> list[str]:
    sheet = item.sheet.sheet if item.sheet is not None else None
    version = item.version or (item.token.version if item.token is not None else (
        sheet.version if sheet is not None else "?"))
    if sheet is not None:
        sheet_text = _("instance {instance}").format(instance=sheet.instance)
        if sheet.service is not None:
            sheet_text += f" · {sheet.service.unit or sheet.service.manager} ({sheet.service.state or '?'})"
        if sheet.partial:
            sheet_text += " · " + _("partielle")
    elif item.sheet is not None:
        sheet_text = _(SHEET_LABELS.get(item.sheet.status, N_("non obtenue")))
    else:
        sheet_text = "—"
    token_kind = "success" if item.token_status is ReadStatus.OK else (
        "neutral" if item.token_status is ReadStatus.ABSENT else "warning")
    token = _(TOKEN_LABELS[item.token_status])
    if item.token is not None:
        token += f" · {item.token.installation_id[:8]}"
    return [_e(item.tool or _("outil inconnu")), _e(item.root), _e(version), _e(item.owner or "?"),
            _e(", ".join(_(SOURCE_LABELS[source]) for source in item.sources)), _badge(token_kind, token),
            _e(sheet_text)]


def _link_html(link: Link) -> str:
    kind = STATE_BADGES[link.state]
    where = (_("instance « {instance} » — {root}").format(instance=link.instance, root=link.root)
             if link.root else _("machine"))
    parts = [f'<div class="link-card {kind}"><div class="link-head">{_badge(kind, _(STATE_LABELS[link.state]))}'
             f'<span class="link-name">{_e(_(LINK_LABELS[link.kind]))}</span>'
             f'<span class="link-where">{_e(where)}</span></div><ul class="checks">']
    for check in link.checks:
        fixes = "".join(f'<code class="fix">{_e(line)}</code>' for line in fix_lines(check))
        parts.append(f"<li>{_badge(CHECK_BADGES[check.status], _(CHECK_LABELS[check.status]))}"
                     f"{_e(check_text(check))}{fixes}</li>")
    if not link.checks:
        parts.append(f"<li>{_e(_('Aucun contrôle.'))}</li>")
    parts.append("</ul></div>")
    return "".join(parts)


def _cards(items: Iterable[tuple[str, str, str]]) -> str:
    """(etiquette, valeur, couleur) -> grille de cartes, comme les rapports d'omega-fire."""
    return '<div class="reco-grid">' + "".join(
        f'<div class="reco-item"><span class="label">{_e(label)}</span>'
        f'<span class="value {kind}">{_e(value)}</span></div>' for label, value, kind in items) + "</div>"


def _links_block(links: Iterable[Link]) -> list[str]:
    blocks = [_link_html(link) for link in links]
    return blocks or [f'<div class="empty-state">{_e(_("Aucune liaison relevée."))}</div>']


def render_report_html(report: FullReport, theme: str = DEFAULT_EXPORT_THEME) -> str:
    theme = theme if theme in EXPORT_PALETTES else DEFAULT_EXPORT_THEME
    verification = report.verification
    detection = verification.detection
    machine = report.machine or "?"
    links = _all_links(report)
    counts = _counts(links)
    plan = todo(report.rows)
    made = _("Établi le {date} depuis {machine}, machines du réseau rescannées (lecture seule, sans "
             "root).").format(date=local_time(report.generated_at), machine=machine)
    problems = counts[LinkState.BROKEN] + counts[LinkState.DEGRADED]
    body = [
        f'<h1>{_e(_("Rapport complet"))}<span class="cursor"></span></h1>',
        f'<div class="note-historique"><span class="note-prefix">[OMEGA-CONNECT {_e(report.version)}]</span> '
        f"{_e(made)}</div>",
        '<div class="exec-summary">',
        f"<p>{_e(_('{machines} machine(s) : {machine} et {remote} du réseau.').format(machines=1 + len(report.machines), machine=machine, remote=len(report.machines)))}</p>",  # noqa: E501
        f"<p>{_e(_('{count} application(s) : {summary}.').format(count=len(report.rows), summary=_state_summary(report.rows)))}</p>",  # noqa: E501
        f"<p>{_e(_('{count} liaison(s), dont {problems} à corriger.').format(count=len(links), problems=problems))}</p>",  # noqa: E501
        f"<p>{_e(_zone_status_text(report))}</p>",
        "</div>",
        f"<h2>{_e(_('Applications'))}</h2>",
        _cards((_(APP_STATE_LABELS[state]).upper(), str(sum(1 for row in report.rows if row.state is state)),
                APP_BADGES[state]) for state in AppState),
        f"<h2>{_e(_('À faire'))}</h2>",
    ]
    if plan.empty and not _repair_lines(report):
        body.append(f'<div class="empty-state">{_e(_("Rien à faire : toutes les applications sont à jour et reliées."))}</div>')  # noqa: E501
    for title, items in _todo_sections(report, plan):
        body.append(f'<div class="note-historique"><span class="note-prefix">{_e(title)}</span><ul class="note-list">'
                    + "".join(f"<li>{_e(item)}</li>" for item in items) + "</ul></div>")
    body.append(f"<h2>{_e(_('Registre — applications par machine'))}</h2>")
    if report.rows:
        body.append(_table([_("Machine"), _("Application"), _("Instance / service"), _("Version"), _("État"),
                            _("Dossier")],
                           ([_e(row.machine), _e(row.tool),
                             _e(row.instance + (f" ({row.service_state})" if row.service_state else "")
                                if row.instance else "—"), _e(row.version or "?"),
                             _badge(APP_BADGES[row.state],
                                    f"{STATE_MARKS[row.state]} {_(APP_STATE_LABELS[row.state])}"),
                             _e(row.root)] for row in report.rows), raw_columns=frozenset(range(6))))
    else:
        body.append(f'<div class="empty-state">{_e(_("Aucune application omega trouvée."))}</div>')
    body.append(f"<h2>{_e(_('Machines du réseau'))}</h2>")
    if report.machines:
        body.append(_table([_("Machine"), _("Connexion"), _("État"), _("Dernier scan"), _("Applications"),
                            _("Liaisons"), _("Dernière erreur")],
                           ([_e(entry.label), _e(entry.target or "?"),
                             _badge("success", _("répond")) if entry.reachable else _badge("danger", _("injoignable")),
                             _e(local_time(entry.scanned_at) if entry.scanned_at else "?"), _e(len(entry.rows)),
                             _e(len(entry.links)), _e(entry.last_error or "—")] for entry in report.machines),
                           raw_columns=frozenset(range(7))))
    else:
        body.append(f'<div class="empty-state">{_e(_("Aucune (Scanner → machine distante, pour en ajouter)."))}</div>')  # noqa: E501
    body.append(f"<h2>{_e(_('Applications de {machine} en détail').format(machine=machine))}</h2>")
    if detection.installations:
        body.append(_table([_("Application"), _("Dossier"), _("Version"), _("Propriétaire"), _("Trouvée par"),
                            _("Carte d'identité"), _("Description")],
                           (_tool_row(item) for item in detection.installations),
                           raw_columns=frozenset(range(7))))
    else:
        body.append(f'<div class="empty-state">{_e(_("Aucun outil omega trouvé."))}</div>')
    notes = [note_text(note) for note in detection.scan_notes]
    notes += [_("Identifiant en double {identifier} : {roots}").format(
        identifier=duplicate.installation_id[:8], roots=", ".join(duplicate.roots))
        for duplicate in detection.duplicates]
    if notes:
        body.append(f'<div class="note-historique"><span class="note-prefix">{_e(_("Remarques sur la recherche"))}'
                    '</span><ul class="note-list">' + "".join(f"<li>{_e(note)}</li>" for note in notes)
                    + "</ul></div>")
    body.append(f"<h2>{_e(_('Liaisons de {machine}').format(machine=machine))}</h2>")
    body.extend(_links_block(verification.links))
    for entry in report.machines:
        title = _("Liaisons de {machine} (réseau, scan du {date})").format(
            machine=entry.label, date=local_time(entry.scanned_at) if entry.scanned_at else "?")
        body.append(f"<h2>{_e(title)}</h2>")
        body.extend(_links_block(entry.links))
    body.append(f"<h2>{_e(_('Espace partagé de {machine} et son registre').format(machine=machine))}</h2>")
    body.append(f'<div class="note-historique">{_e(_zone_status_text(report))}</div>')
    registry = report.registry.value
    if registry is not None:
        body.append(_table([_("Type"), _("Élément"), _("Créé le")],
                           ([_(KIND_LABELS[item.kind]), item.target, local_time(item.at)]
                            for item in registry.created)))
        if registry.installations:
            body.append(_table([_("Application"), _("Instance"), _("Dossier"), _("Identifiant"), _("Version"),
                                _("Reliée le")],
                               ([item.tool, item.instance, item.root, item.installation_id[:8], item.version,
                                 local_time(item.linked_at)] for item in registry.installations)))
        else:
            body.append(f'<div class="empty-state">{_e(_("Aucune application reliée."))}</div>')
    footer = _("OMEGA-CONNECT {version} — rapport du {date}, établi depuis {machine}.").format(
        version=report.version, date=local_time(report.generated_at), machine=machine)
    body.append(f'<div class="footer-note">{_e(footer)}</div>')
    css = _style(f"palette_{theme}.css") + "\n" + _style("base.css") + EXTRA_CSS
    return ('<!DOCTYPE html>\n<html lang="fr" dir="ltr">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"<title>{_e(_('Rapport complet - Omega-Connect'))}</title>\n<style>\n{css}</style>\n</head>\n<body>\n"
            '<div class="container"><div class="terminal-header"><div class="terminal-dots">'
            '<span class="dot dot-close"></span><span class="dot dot-min"></span><span class="dot dot-max"></span>'
            '</div><span class="terminal-title">omega-connect -- rapport-complet</span></div>\n'
            '<div class="terminal-body">\n' + "\n".join(body) + "\n</div></div>\n</body>\n</html>\n")
