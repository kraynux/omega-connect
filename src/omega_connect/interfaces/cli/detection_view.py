# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Affichage du rapport de detection : texte (francais de reference, traduit au lot F) et JSON (jamais
traduit, versionne, pour les scripts et la future interface)."""
from __future__ import annotations

from typing import Any

from omega_lib.synchro.codec import sheet_to_dict, token_to_dict
from omega_lib.synchro.models import CapabilityState, ReadStatus

from omega_connect.domain.detection import (
    DetectedInstallation,
    DetectionReport,
    NoteKind,
    ScanNote,
    Source,
)
from omega_connect.shared.i18n import N_, _

REPORT_FORMAT = "omega-connect-detection"
REPORT_SCHEMA_VERSION = 1

SOURCE_LABELS = {
    Source.SERV_REGISTRY: N_("registre omega-serv"),
    Source.SYSTEMD: N_("systemd"),
    Source.OPENRC: N_("OpenRC"),
    Source.RUNIT: N_("runit"),
    Source.HOME: N_("dossier personnel"),
    Source.SRV: N_("/srv"),
    Source.MANUAL: N_("chemin saisi"),
}
TOKEN_LABELS = {
    ReadStatus.OK: N_("présent"),
    ReadStatus.ABSENT: N_("absent"),
    ReadStatus.UNREADABLE: N_("illisible (droits)"),
    ReadStatus.INVALID: N_("abîmé"),
    ReadStatus.INCOMPATIBLE: N_("d'une version plus récente qu'omega-connect"),
}
SHEET_LABELS = {
    ReadStatus.ABSENT: N_("non fournie (version de l'outil trop ancienne ?)"),
    ReadStatus.UNREADABLE: N_("non obtenue"),
    ReadStatus.INVALID: N_("illisible"),
    ReadStatus.INCOMPATIBLE: N_("d'une version plus récente qu'omega-connect"),
}
STATE_LABELS = {
    CapabilityState.ACTIVE: N_("active"),
    CapabilityState.DISABLED: N_("désactivée"),
    CapabilityState.ABSENT: N_("absente"),
    CapabilityState.UNKNOWN: N_("inconnue"),
}
NOTE_LABELS = {
    NoteKind.REGISTRY_UNREADABLE: N_("registre des instances omega-serv illisible : {detail}"),
    NoteKind.REGISTERED_INSTANCE_MISSING: N_("instance omega-serv enregistrée mais dossier disparu : {detail}"),
    NoteKind.SERVICE_FILE_UNREADABLE: N_("fichier de service illisible : {detail}"),
    NoteKind.SERVICE_ROOT_MISSING: N_("service {detail} : dossier d'installation introuvable"),
    NoteKind.SEARCH_STOPPED: N_("recherche arrêtée (trop de dossiers) dans {detail}"),
    NoteKind.NETWORK_MOUNT_SKIPPED: N_("montage réseau non parcouru : {detail}"),
    NoteKind.MANUAL_NOT_FOUND: N_("dossier introuvable : {detail}"),
    NoteKind.MANUAL_NOT_OMEGA: N_("aucun outil omega dans : {detail}"),
}
TOKEN_HINT = N_("créez-le sous le compte {owner} : {command}")


def _short(identifier: str) -> str:
    return f"{identifier[:8]}…" if len(identifier) > 8 else identifier


def note_text(note: ScanNote) -> str:
    return _(NOTE_LABELS[note.kind]).format(detail=note.detail)


def _installation_lines(item: DetectedInstallation) -> list[str]:
    lines = [f"{item.tool or _('outil inconnu')} — {item.root}"]
    sources = ", ".join(_(SOURCE_LABELS[s]) for s in item.sources)
    lines.append("  " + _("trouvé par : {sources}").format(sources=sources))
    details = [_("propriétaire : {owner}").format(owner=item.owner or "?")]
    if item.service_names:
        details.append(_("service : {names}").format(names=", ".join(item.service_names)))
    lines.append("  " + " · ".join(details))
    if item.token is not None:
        lines.append("  " + _("jeton : présent (identifiant {identifier}, version {version})").format(
            identifier=_short(item.token.installation_id), version=item.token.version))
    else:
        lines.append("  " + _("jeton : {state}").format(state=_(TOKEN_LABELS[item.token_status])))
        if item.token_status is ReadStatus.ABSENT and item.tool:
            launcher = {"omega-serv": "omega-serv.sh", "omega-fire": "omega-fire.sh",
                        "omega-jail": "omega-jail.sh"}.get(item.tool)
            if launcher:
                lines.append("    " + _(TOKEN_HINT).format(
                    owner=item.owner or "?", command=f"{item.root}/{launcher} synchro jeton"))
    if item.sheet is not None:
        sheet = item.sheet.sheet
        if sheet is None:
            text = _("fiche : {state}").format(state=_(SHEET_LABELS.get(item.sheet.status, N_("non obtenue"))))
            if item.sheet.detail:
                text += " — " + _("détail technique : {detail}").format(detail=item.sheet.detail)
            lines.append("  " + text)
        else:
            head = [_("fiche : instance {instance}").format(instance=sheet.instance)]
            if sheet.service is not None:
                head.append(_("service {manager} ({state})").format(
                    manager=sheet.service.manager, state=sheet.service.state or "?"))
            if sheet.partial:
                head.append(_("partielle (sans root)"))
            lines.append("  " + " · ".join(head))
            states = " · ".join(f"{name} {_(STATE_LABELS[state])}"
                                for name, state in sorted(sheet.capabilities.items()))
            lines.append("    " + _("fonctions : {states}").format(states=states))
    return lines


def render_text(report: DetectionReport) -> str:
    lines = [_("Détection des outils omega (HOME examiné : {home})").format(home=report.home), ""]
    if not report.installations:
        lines.append(_("Aucun outil omega trouvé. Indiquez un dossier avec --chemin."))
    for item in report.installations:
        lines.extend(_installation_lines(item))
        lines.append("")
    for duplicate in report.duplicates:
        lines.append(_("Identifiant en double {identifier} : {roots} (dossier copié à la main ?). "
                       "Ces installations ne sont pas fusionnées ; ouvrez la copie une fois pour lui "
                       "donner un nouvel identifiant.").format(
            identifier=_short(duplicate.installation_id), roots=", ".join(duplicate.roots)))
    if report.scan_notes:
        lines.append(_("Remarques sur la recherche :"))
        lines.extend(f"  - {note_text(note)}" for note in report.scan_notes)
    count = len(report.installations)
    lines.append(_("{count} installation(s) trouvée(s).").format(count=count))
    return "\n".join(lines)


def report_to_dict(report: DetectionReport) -> dict[str, Any]:
    return {
        "format": REPORT_FORMAT, "schema_version": REPORT_SCHEMA_VERSION, "home": report.home,
        "installations": [{
            "root": item.root, "tool": item.tool, "sources": [s.value for s in item.sources],
            "owner": item.owner, "services": list(item.service_names),
            "token_status": item.token_status.value,
            "token": token_to_dict(item.token) if item.token is not None else None,
            "sheet_status": item.sheet.status.value if item.sheet is not None else None,
            "sheet": sheet_to_dict(item.sheet.sheet) if item.sheet is not None and item.sheet.sheet else None,
            "sheet_detail": item.sheet.detail if item.sheet is not None else "",
        } for item in report.installations],
        "duplicates": [{"installation_id": d.installation_id, "roots": list(d.roots)} for d in report.duplicates],
        "notes": [{"kind": n.kind.value, "detail": n.detail} for n in report.scan_notes],
    }
