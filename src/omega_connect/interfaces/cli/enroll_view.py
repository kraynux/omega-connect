# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Affichage de la synchronisation (« Inscrire » du lot R1) et du registre, en mots simples (decision Q7 de
l'auteur) ; les commandes exactes restent montrees sous chaque etape, avant tout accord. Partage par la ligne de
commande et l'interface."""
from __future__ import annotations

from omega_connect.application.enroll_actions import EnrollResult
from omega_connect.domain.enroll import EnrollPlan
from omega_connect.domain.fleet import AppState, RegistryRow, SpaceStatus
from omega_connect.domain.versions import CONTRACT_VERSIONS as VERSION_MINIMUMS
from omega_connect.domain.zone import NoteCode
from omega_connect.interfaces.cli.repair_view import SKIP_REASONS, step_command
from omega_connect.interfaces.cli.zone_view import command_line, describe, note_text
from omega_connect.shared.i18n import N_, _

STATE_LABELS = {
    AppState.DETECTED: N_("Détectée"),
    AppState.ENROLLED: N_("Inscrite"),
    AppState.LINKED: N_("Reliée"),
    AppState.TO_FIX: N_("À réparer"),
    AppState.OLD_VERSION: N_("Ancienne version"),
    AppState.INCOMPLETE: N_("Installation inachevée"),
    AppState.UNREACHABLE: N_("Injoignable"),
}
STATE_HINTS = {
    AppState.DETECTED: N_("trouvée, sans carte d'identité : la Synchronisation la lui crée"),
    AppState.ENROLLED: N_("a sa carte d'identité, pas encore dans l'espace partagé : la Synchronisation l'y ajoute"),
    AppState.LINKED: N_("dans l'espace partagé, à jour"),
    AppState.TO_FIX: N_("un écart : Réparer le corrige"),
    AppState.OLD_VERSION: N_("trop ancienne pour avoir une carte d'identité : mettez-la à jour"),
    AppState.INCOMPLETE: N_("installée, mais son install.sh ne s'est pas terminé (environnement Python ou carte "
                            "d'identité manquants) : « Réinstaller l'application » (Registre)"),
    AppState.UNREACHABLE: N_("machine qui ne répond pas"),
}
CONTRACT_VERSIONS = VERSION_MINIMUMS
"""Premiere version de chaque outil qui a une carte d'identite (`synchro`) : `domain/versions.py`."""


def state_hint(row: RegistryRow) -> str:
    """Explication d'un etat ; pour une ancienne version, la version a installer."""
    minimum = CONTRACT_VERSIONS.get(row.tool)
    if row.state is AppState.OLD_VERSION and minimum:
        return _("trop ancienne pour avoir une carte d'identité : {tool} {version} ou plus récent requis (machine "
                 "distante : Synchronisation la met à jour depuis GitHub)").format(tool=row.tool, version=minimum)
    return _(STATE_HINTS[row.state])


STATE_MARKS = {
    AppState.DETECTED: "○", AppState.ENROLLED: "◐", AppState.LINKED: "●", AppState.TO_FIX: "▲",
    AppState.OLD_VERSION: "◌", AppState.INCOMPLETE: "◇", AppState.UNREACHABLE: "✕",
}
SPACE_LABELS = {
    SpaceStatus.NOT_PREPARED: N_("pas encore préparé — la Synchronisation le prépare"),
    SpaceStatus.READY: N_("prêt"),
    SpaceStatus.TO_FIX: N_("à corriger — la Synchronisation le remet en état"),
    SpaceStatus.READ_WITH_AUTHORIZATION: N_("prêt (lu avec votre autorisation)"),
    SpaceStatus.UNKNOWN: N_("état inconnu depuis cette session — la Synchronisation le lira avec votre autorisation"),
}


def state_label(state: AppState) -> str:
    return f"{STATE_MARKS[state]} {_(STATE_LABELS[state])}"


def render_rows(rows: tuple[RegistryRow, ...], space: SpaceStatus, machine: str) -> str:
    lines = [_("Registre — machine {machine}").format(machine=machine), ""]
    if not rows:
        lines.append(_("Aucune application omega trouvée sur cette machine."))
    for row in rows:
        service = row.instance + (f" ({row.service_state})" if row.service_state else "") if row.instance else "—"
        lines.append(f"  {state_label(row.state):<20} {row.tool:<14} {service:<28} {row.version or '?':<8} {row.root}")
    lines += ["", _("Espace partagé : {status}").format(status=_(SPACE_LABELS[space]))]
    return "\n".join(lines) + "\n"


def render_enroll_plan(plan: EnrollPlan, *, as_root: bool = False) -> str:
    lines = [_("Synchroniser : un seul plan, un seul mot de passe administrateur"), ""]
    if plan.space.refused:
        lines.extend(f"  · {note_text(note)}" for note in plan.space.notes)
        return "\n".join(lines) + "\n"
    if plan.empty:
        lines.append(_("Rien à faire : tout est déjà synchronisé."))
        return "\n".join(lines) + "\n"
    lines.append(_("1. Cartes d'identité à créer (par chaque outil, sous son compte, sans mot de passe) :"))
    if plan.cards:
        for step in plan.cards:
            lines.append(f"   · {step.tool} — {step.root}")
            lines.append(f"       {step_command(step, as_root=as_root)}")
    else:
        lines.append("   · " + _("aucune : chaque application choisie a déjà la sienne."))
    for skipped in plan.skipped:
        reason = _(SKIP_REASONS[skipped.reason]).format(root=skipped.step.root, account=skipped.step.account)
        lines.append(f"   · {reason}")
    lines += ["", _("2. Espace partagé (en administrateur, une commande après l'autre) :")]
    for number, operation in enumerate(plan.space.operations, start=1):
        lines.append(f"  {number:>2}. {describe(operation)}")
        lines.append(f"      {command_line(operation, as_root=as_root)}")
    for root in plan.pending:
        lines.append("   · " + _("Recopier la carte d'identité de {root} (créée à l'étape 1)").format(root=root))
    if not plan.space.operations and not plan.pending:
        lines.append("   · " + _("rien : l'espace partagé est déjà à jour."))
    pending = set(plan.pending)
    notes = [note for note in plan.space.notes
             if not (note.code is NoteCode.NOT_LINKED and note.subject in pending)
             and note.code is not NoteCode.NOTHING_TO_DO]
    if notes:
        lines.append("")
        lines.extend(f"  · {note_text(note)}" for note in notes)
    lines += ["", _("Une commande qui n'est pas annoncée ici n'est jamais lancée.")]
    return "\n".join(lines) + "\n"


def render_enroll_result(result: EnrollResult) -> str:
    failed = result.cards.failed
    if failed is not None:
        return _("Arrêt : la carte d'identité de {root} n'a pas pu être créée ({error}). Rien d'autre n'a été "
                 "lancé.").format(root=failed.step.root, error=failed.error or _("échec"))
    if result.space_plan is not None and result.space_plan.refused:
        return "\n".join(note_text(note) for note in result.space_plan.notes)
    if result.unannounced:
        return _("Arrêt avant l'espace partagé : le plan a changé ({step}). Rien de plus n'a été lancé ; relancez "
                 "la synchronisation pour voir le nouveau plan.").format(step=describe(result.unannounced[0]))
    space = result.space
    if space is not None and not space.ok:
        assert space.failed is not None
        return _("Arrêt à l'étape « {step} » : {error}. Ce qui a été créé est noté ; relancez la synchronisation "
                 "après avoir corrigé la cause.").format(step=describe(space.failed), error=space.error or _("échec"))
    return _("Synchronisation terminée : les applications choisies sont reliées.")
