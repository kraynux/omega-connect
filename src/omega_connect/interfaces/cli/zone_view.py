# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Affichage des plans du lot D (`etablir`, `retirer`) : chaque commande est montree telle qu'elle sera lancee,
avant tout accord. Partage par la ligne de commande et l'interface."""
from __future__ import annotations

import shlex

from omega_lib.synchro.constants import ZONE_GROUP

from omega_connect.application.zone_actions import ApplyResult
from omega_connect.domain.zone import FileRole, NoteCode, Operation, OperationKind, PlanAction, PlanNote, ZonePlan
from omega_connect.shared.i18n import N_, _

PLAN_TITLES = {
    PlanAction.ESTABLISH: N_("Établir la zone neutre {zone}"),
    PlanAction.REMOVE_ALL: N_("Tout retirer : défaire ce que le registre de {zone} liste"),
    PlanAction.FREEZE: N_("Garder la zone {zone} (liens figés)"),
    PlanAction.REMOVE_TOOL: N_("Retirer un outil désinstallé de la zone {zone}"),
}
NOTE_MESSAGES = {
    NoteCode.ZONE_UNSAFE: N_("{subject} n'est pas un vrai dossier (lien symbolique ou fichier) : rien n'est fait."),
    NoteCode.ZONE_FOREIGN: N_("{subject} existe déjà sans registre d'omega-connect : rien n'est fait. Vérifiez ce "
                              "dossier, puis supprimez-le vous-même s'il est inutile."),
    NoteCode.ZONE_UNREADABLE: N_("{subject} n'a pas pu être lu, même avec sudo : rien n'est fait."),
    NoteCode.REGISTRY_DAMAGED: N_("registre {subject} abîmé ({detail}) : rien n'est fait tant qu'il n'est pas réparé."),
    NoteCode.NOT_ESTABLISHED: N_("aucune zone en {subject} : rien à retirer."),
    NoteCode.TARGET_NOT_FOUND: N_("« {subject} » ne désigne aucun outil du registre (nom, dossier ou 8 premiers "
                                  "caractères de l'identifiant)."),
    NoteCode.TARGET_STILL_INSTALLED: N_("{subject} ({detail}) est toujours installé : il serait relié de nouveau à "
                                        "la prochaine actualisation. Désinstallez-le d'abord."),
    NoteCode.STILL_INSTALLED_SKIPPED: N_("{subject} ({detail}) est toujours installé : laissé dans la zone."),
    NoteCode.NOT_LINKED: N_("{subject} n'est pas relié : jeton {detail} (voir « verifier »)."),
    NoteCode.DUPLICATE_SKIPPED: N_("{subject} n'est pas relié : identifiant {detail} en double."),
    NoteCode.TOOL_GONE: N_("{subject} ({detail}) est au registre mais introuvable : « retirer {detail} » "
                           "l'enlèvera."),
    NoteCode.RELOGIN: N_("{subject} devra se reconnecter pour que le groupe omega-synchro compte (lecture de la "
                         "zone)."),
    NoteCode.NOTHING_TO_DO: N_("la zone {subject} est à jour : rien à faire."),
    NoteCode.UNKNOWN_FILES_KEPT: N_("{subject} n'a pas été créé par omega-connect : gardé, ainsi que son dossier."),
    NoteCode.GROUP_KEPT: N_("le groupe {subject} est gardé (pas créé par omega-connect, ou zone pas vide)."),
    NoteCode.SERVICE_GROUP_KEPT: N_("le service {subject} a toujours le groupe omega-synchro, mais omega-serv est "
                                    "introuvable pour le lui retirer : le groupe et la zone sont gardés (sans lui, "
                                    "le service ne démarrerait plus). Lancez « omega-serv synchro groupe-service "
                                    "retirer --service-name {subject} » depuis son dossier, puis relancez."),
    NoteCode.SERVICE_RESTART: N_("le service {subject} ({detail}) prendra en compte le groupe omega-synchro à son "
                                 "prochain redémarrage : omega-connect ne le redémarre pas."),
    NoteCode.FOREIGN_DIRECTORY_IGNORED: N_("{subject} figure au registre mais hors de la zone : ignoré."),
    NoteCode.ALREADY_FROZEN: N_("la zone est déjà figée : rien à faire."),
}


def describe(operation: Operation) -> str:
    target, subject = operation.target, operation.subject
    if operation.kind is OperationKind.CREATE_GROUP:
        return _("Créer le groupe {group}").format(group=target)
    if operation.kind is OperationKind.CREATE_DIRECTORY:
        if operation.record is not None:
            return _("Créer le dossier {path}").format(path=target)
        return _("Remettre les droits du dossier {path}").format(path=target)
    if operation.kind is OperationKind.ADD_MEMBER:
        return _("Ajouter {user} au groupe {group}").format(user=target, group=ZONE_GROUP)
    if operation.kind is OperationKind.REMOVE_MEMBER:
        return _("Retirer {user} du groupe {group}").format(user=target, group=ZONE_GROUP)
    if operation.kind is OperationKind.DELETE_GROUP:
        return _("Supprimer le groupe {group}").format(group=target)
    if operation.kind is OperationKind.REMOVE_DIRECTORY:
        return _("Retirer le dossier {path}").format(path=target)
    if operation.kind is OperationKind.GRANT_SERVICE_GROUP:
        return _("omega-serv donne le groupe {group} à son service {service} (complément systemd)").format(
            group=ZONE_GROUP, service=target)
    if operation.kind is OperationKind.REVOKE_SERVICE_GROUP:
        return _("omega-serv retire le groupe {group} de son service {service}").format(group=ZONE_GROUP,
                                                                                         service=target)
    writing = operation.kind is OperationKind.WRITE_FILE
    if operation.role is FileRole.REGISTRY:
        return _("Écrire le registre de l'espace partagé") if writing else _("Retirer le registre de l'espace partagé")
    if operation.role is FileRole.SHEET_COPY:
        return (_("Recopier la description de {root} (ce qu'il sait faire)") if writing
                else _("Retirer la description de {root}")).format(root=subject)
    return (_("Recopier la carte d'identité de {root}") if writing
            else _("Retirer la carte d'identité de {root}")).format(root=subject)


def command_line(operation: Operation, *, as_root: bool = False) -> str:
    return ("" if as_root else "sudo ") + shlex.join(operation.argv())


def note_text(note: PlanNote) -> str:
    return _(NOTE_MESSAGES[note.code]).format(subject=note.subject, detail=note.detail or "?")


def render_plan(plan: ZonePlan, *, as_root: bool = False) -> str:
    lines = [_(PLAN_TITLES[plan.action]).format(zone=plan.zone), ""]
    if plan.operations:
        lines.append(_("Commandes qui seront lancées, une à une, en root :"))
        for number, operation in enumerate(plan.operations, start=1):
            lines.append(f"  {number:>2}. {describe(operation)}")
            lines.append(f"      {command_line(operation, as_root=as_root)}")
        lines.append("")
    if plan.notes:
        lines.extend(f"  · {note_text(note)}" for note in plan.notes)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def step_line(index: int, total: int, operation: Operation, ok: bool, error: str = "") -> str:
    mark = "✔" if ok else "✘"
    line = f"  {mark} {index + 1}/{total} {describe(operation)}"
    return line if ok else f"{line} : {error or _('échec')}"


def render_result(result: ApplyResult, plan: ZonePlan) -> str:
    if result.ok:
        return _("Terminé : {count} commande(s) lancée(s), toutes réussies.").format(count=len(result.done))
    assert result.failed is not None
    lines = [_("Arrêt à l'étape « {step} » : {error}").format(step=describe(result.failed),
                                                             error=result.error or _("échec")),
             _("{done} commande(s) sur {total} avaient réussi.").format(done=len(result.done),
                                                                        total=len(plan.operations))]
    if result.recovery is not None:
        lines.append(_("Registre réécrit pour garder la trace de ce qui a été créé.") if result.recovery_ok
                     else _("Le registre n'a pas pu être réécrit : notez ce qui a été créé ci-dessus."))
    lines.append(_("Relancez la même commande après avoir corrigé la cause : rien n'est fait deux fois."))
    return "\n".join(lines)
