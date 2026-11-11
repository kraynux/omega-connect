# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Affichage de `verifier` : texte (francais de reference, traduit au lot F) et JSON (jamais traduit,
versionne, pour les scripts et la future interface)."""
from __future__ import annotations

from typing import Any

from omega_connect.domain.links import (
    Check,
    CheckCode,
    CheckStatus,
    Link,
    LinkKind,
    LinkState,
    RepairKind,
    VerificationReport,
)
from omega_connect.interfaces.cli.detection_view import report_to_dict
from omega_connect.shared.i18n import N_, _

REPORT_FORMAT = "omega-connect-verification"
REPORT_SCHEMA_VERSION = 1

LINK_LABELS = {
    LinkKind.SERV_LOGS: N_("Journaux d'omega-serv → jails fail2ban"),
    LinkKind.MAGNET_LOGS: N_("Journaux magnet (omega-waf) → jails fail2ban"),
    LinkKind.BRIDGE: N_("Pont fail2ban → liste noire d'omega-serv"),
    LinkKind.PROTECTED_LIST: N_("Liste protégée → jails et pont"),
    LinkKind.BLOCKLIST: N_("Liste noire d'omega-serv (droits)"),
    LinkKind.FAIL2BAN_FILES: N_("Fichiers d'omega-jail dans fail2ban"),
    LinkKind.TOKENS: N_("Cartes d'identité"),
    LinkKind.ZONE: N_("Espace partagé (omega-synchro)"),
}
STATE_LABELS = {
    LinkState.ACTIVE: N_("OK"),
    LinkState.DEGRADED: N_("à réparer"),
    LinkState.ABSENT: N_("absent"),
    LinkState.BROKEN: N_("à réparer (bloquant)"),
    LinkState.UNVERIFIABLE: N_("non vérifiable"),
}
STATE_MARKS = {
    LinkState.ACTIVE: "✔", LinkState.DEGRADED: "!", LinkState.ABSENT: "–", LinkState.BROKEN: "✘",
    LinkState.UNVERIFIABLE: "?",
}
CHECK_MARKS = {
    CheckStatus.OK: "✔", CheckStatus.INFO: "·", CheckStatus.WARNING: "!", CheckStatus.FAILURE: "✘",
    CheckStatus.UNVERIFIABLE: "?",
}
UNVERIFIABLE_WITHOUT_ROOT = N_("{subject} : non vérifiable sans root — le dossier qui le contient n'est lisible que "
                               "par root ({detail}).")
CHECK_MESSAGES = {
    CheckCode.FAIL2BAN_NOT_INSTALLED: N_("fail2ban n'est pas installé : aucun jail ne protège cette instance."),
    CheckCode.FAIL2BAN_UNREADABLE: N_("dossiers de fail2ban illisibles ({detail}) : non vérifiable sans root."),
    CheckCode.JAIL_TOOL_MISSING: N_("omega-jail n'est pas installé : aucun jail fail2ban ne lit les journaux "
                                    "d'omega-serv."),
    CheckCode.NO_JAIL: N_("aucun jail d'omega-jail pour cette instance."),
    CheckCode.NO_JAIL_FILES: N_("omega-jail n'a encore posé aucun fichier dans fail2ban."),
    CheckCode.FUNCTION_OFF: N_("fonction {subject} désactivée : rien à relier."),
    CheckCode.SHEET_MISSING: N_("non vérifiable : l'outil n'a pas fourni sa description (version trop ancienne, "
                                "ou refusée) — voir le Registre."),
    CheckCode.JAIL_DISABLED: N_("jail {subject} désactivé (enabled = false)."),
    CheckCode.JAIL_FILTER_MISSING: N_("jail {subject} : filtre {detail} introuvable dans filter.d — fail2ban "
                                      "refuse de démarrer."),
    CheckCode.JAIL_LOG_OK: N_("journal {subject} présent ({detail})."),
    CheckCode.JAIL_LOG_MISSING: N_("journal {subject} absent (jail {detail}) : fail2ban refuse de démarrer tant "
                                   "qu'il manque."),
    CheckCode.JAIL_LOG_UNKNOWN: UNVERIFIABLE_WITHOUT_ROOT,
    CheckCode.JAIL_LOG_ROOT_OWNED: N_("journal {subject} appartient à root ({detail}) : le service omega-serv ne "
                                      "peut plus y écrire."),
    CheckCode.JAIL_LOG_RIGHTS: N_("journal {subject} : droits {detail} ; le service omega-serv risque de ne pas "
                                  "pouvoir y écrire."),
    CheckCode.JAIL_PATH_DIFFERS: N_("jail {subject} ne lit pas le fichier qu'écrit l'instance ({detail}) : il ne "
                                    "bannira jamais."),
    CheckCode.JAIL_SOURCE_OFF: N_("jail {subject} : la fonction qui écrit son journal ({detail}) est désactivée, "
                                  "le jail reste sans effet."),
    CheckCode.JAIL_NO_INSTANCE: N_("jail {subject} lit {detail} : aucune instance omega-serv détectée à cet "
                                   "endroit."),
    CheckCode.FUNCTION_NOT_COVERED: N_("journal {subject} ({detail}) : fonction active mais aucun jail ne le lit."),
    CheckCode.MAGNET_LOG_ONLY: N_("omega-waf est en mode log-only (il note les attaques sans bannir), mais le "
                                  "jail {subject} posé par omega-jail dans fail2ban bannit, lui, au niveau "
                                  "réseau. omega-connect indique l'état et relie les outils ; il ne se substitue "
                                  "pas à fail2ban."),
    CheckCode.BRIDGE_ACTION_OK: N_("pont {subject} vers la liste noire de cette instance ({detail})."),
    CheckCode.BRIDGE_ACTION_MISSING: N_("aucun pont vers la liste noire de cette instance : un ban derrière "
                                        "Tailscale reste sans effet."),
    CheckCode.BRIDGE_NO_SERVCLI: N_("pont {subject} sans omega-serv (installé quand omega-serv était "
                                    "introuvable) : aucun ban relayé."),
    CheckCode.BRIDGE_UNKNOWN_ACTION: N_("jail {subject} utilise l'action {detail}, absente d'action.d : fail2ban "
                                        "refuse de démarrer."),
    CheckCode.BRIDGE_WRONG_TARGET: N_("jail {subject} relaie ses bans vers une autre instance ({detail})."),
    CheckCode.BRIDGE_TARGET_MISSING: N_("pont {subject} : l'instance visée a disparu ({detail})."),
    CheckCode.BRIDGE_TARGET_NOT_DETECTED: N_("pont {subject} : l'instance visée ({detail}) n'a pas été détectée "
                                             "(autre compte ?)."),
    CheckCode.JAIL_WITHOUT_BRIDGE: N_("jail {subject} sans pont vers la liste noire."),
    CheckCode.BRIDGE_SCRIPT_OK: N_("script du pont {subject} conforme ({detail})."),
    CheckCode.BRIDGE_SCRIPT_MISSING: N_("script du pont {subject} absent : aucun ban n'est relayé."),
    CheckCode.BRIDGE_SCRIPT_UNKNOWN: UNVERIFIABLE_WITHOUT_ROOT,
    CheckCode.BRIDGE_SCRIPT_UNSAFE: N_("script du pont {subject} modifiable par un autre compte que root "
                                       "({detail}), alors que fail2ban le lance en root."),
    CheckCode.BRIDGE_SCRIPT_RIGHTS: N_("script du pont {subject} : droits {detail} au lieu de root:root 0755."),
    CheckCode.PROTECTED_LIST_UNKNOWN: N_("non vérifiable : la description d'omega-serv ne donne pas sa liste protégée "
                                         "({detail} ; version antérieure à 2.6.1 ?), comparaison impossible."),
    CheckCode.PROTECTED_JAIL_OK: N_("jail {subject} : ignoreip identique à la liste protégée d'omega-serv."),
    CheckCode.PROTECTED_JAIL_DIFFERS: N_("jail {subject} : ignoreip différent de la liste protégée d'omega-serv "
                                         "(en plus « + », en moins « - » : {detail})."),
    CheckCode.PROTECTED_BRIDGE_OK: N_("pont {subject} : réseaux exemptés identiques à la liste protégée "
                                      "d'omega-serv."),
    CheckCode.PROTECTED_BRIDGE_DIFFERS: N_("pont {subject} : réseaux exemptés différents de la liste protégée "
                                           "d'omega-serv (en plus « + », en moins « - » : {detail})."),
    CheckCode.BLOCKLIST_OFF: N_("liste noire désactivée : rien à relier."),
    CheckCode.BLOCKLIST_NOT_CREATED: N_("liste noire {subject} pas encore créée (aucun ban jusqu'ici)."),
    CheckCode.BLOCKLIST_OK: N_("liste noire {subject} conforme ({detail})."),
    CheckCode.BLOCKLIST_UNKNOWN: UNVERIFIABLE_WITHOUT_ROOT,
    CheckCode.BLOCKLIST_ROOT_OWNED: N_("liste noire {subject} appartient à root ({detail}) : le service ne peut "
                                       "plus la lire et le site répond en erreur."),
    CheckCode.BLOCKLIST_GROUP: N_("liste noire {subject} : mauvais groupe ({detail}) ; le service ne peut pas "
                                  "la lire."),
    CheckCode.BLOCKLIST_MODE: N_("liste noire {subject} : droits {detail}, il faut au moins 0660 (lecture et "
                                 "écriture pour le groupe du service)."),
    CheckCode.BLOCKLIST_OWNER: N_("liste noire {subject} : propriétaire inattendu ({detail})."),
    CheckCode.FILES_OK: N_("{subject} fichier(s) d'omega-jail conforme(s)."),
    CheckCode.FILE_UNREADABLE: N_("{subject} : non vérifiable sans root — fichier illisible pour votre compte."),
    CheckCode.FILE_UNSAFE: N_("{subject} modifiable par un autre compte que root ({detail}), alors que fail2ban "
                              "le lit en root."),
    CheckCode.FILE_RIGHTS: N_("{subject} : droits {detail} au lieu de root:root 0644."),
    CheckCode.JAIL_FILE_DAMAGED: N_("{subject} abîmé ({detail}) : fail2ban risque de refuser de démarrer."),
    CheckCode.BRIDGE_ACTION_DAMAGED: N_("{subject} : action du pont abîmée ou modifiée à la main (ligne "
                                       "actionban introuvable)."),
    CheckCode.TOKEN_OK: N_("{subject} : carte d'identité présente (identifiant {detail}…)."),
    CheckCode.TOKEN_MISSING: N_("{subject} ({detail}) : pas encore de carte d'identité."),
    CheckCode.TOKEN_TOOL_TOO_OLD: N_("{subject} ({detail}) : version trop ancienne : ni carte d'identité ni "
                                     "description."),
    CheckCode.TOKEN_INSTALL_INCOMPLETE: N_("{subject} ({detail}) : installation inachevée (environnement Python ou "
                                           "carte d'identité manquants) : à réinstaller."),
    CheckCode.TOKEN_UNREADABLE: N_("{subject} : non vérifiable, carte d'identité illisible pour votre compte "
                                   "(droits du fichier ou du dossier : {detail})."),
    CheckCode.TOKEN_DAMAGED: N_("{subject} : carte d'identité abîmée ({detail})."),
    CheckCode.TOKEN_NEWER: N_("{subject} : carte d'identité d'une version plus récente qu'omega-connect ({detail})."),
    CheckCode.TOKEN_RIGHTS: N_("{subject} : droits {detail} au lieu de 0644 (ou 0664), au nom du propriétaire du "
                               "dossier."),
    CheckCode.TOKEN_DUPLICATE: N_("identifiant {subject} en double : {detail} (dossier copié à la main ?)."),
    CheckCode.ZONE_ABSENT: N_("espace partagé {subject} pas encore préparé : la Synchronisation le prépare."),
    CheckCode.ZONE_UNSAFE: N_("{subject} n'est pas un vrai dossier (lien symbolique ou fichier) : rien n'y est lu."),
    CheckCode.ZONE_FOREIGN: N_("{subject} existe sans registre : créé à la main ou par autre chose qu'omega-connect "
                               "(rien n'y sera fait)."),
    CheckCode.ZONE_UNREADABLE: N_("{subject} : non vérifiable, illisible pour votre compte ({detail})."),
    CheckCode.ZONE_AWAITING_RELOGIN: N_("en attente de reconnexion : {subject} est déjà membre du groupe "
                                        "omega-synchro, mais la session ouverte ne le sait pas encore. {detail} "
                                        "sera vérifié après la prochaine connexion (ou Registre → « Lire avec "
                                        "sudo »)."),
    CheckCode.ZONE_NOT_MEMBER_UNREADABLE: N_("{subject} : non vérifiable, lisible par root et le groupe omega-synchro "
                                             "seulement, et {detail} n'en est pas membre."),
    CheckCode.ZONE_REGISTRY_DAMAGED: N_("registre {subject} abîmé ({detail}) : rien n'est retiré tant qu'il n'est "
                                        "pas réparé."),
    CheckCode.ZONE_FROZEN: N_("espace partagé figé : gardé tel quel, plus synchronisé."),
    CheckCode.ZONE_DIRECTORY_OK: N_("{detail} dossier(s) de l'espace partagé conformes (root:omega-synchro 2750)."),
    CheckCode.ZONE_DIRECTORY_MISSING: N_("dossier {subject} manquant."),
    CheckCode.ZONE_DIRECTORY_RIGHTS: N_("{subject} : {detail} au lieu de root:omega-synchro 2750."),
    CheckCode.ZONE_GROUP_MISSING: N_("groupe {subject} absent alors que l'espace partagé existe."),
    CheckCode.ZONE_MEMBER_OK: N_("{subject} est membre du groupe omega-synchro."),
    CheckCode.ZONE_MEMBER_MISSING: N_("{subject} n'est pas membre du groupe omega-synchro : l'espace partagé lui "
                                      "est illisible."),
    CheckCode.ZONE_RELOGIN: N_("{subject} est membre du groupe omega-synchro ; cela comptera à la prochaine "
                               "connexion."),
    CheckCode.ZONE_COPY_OK: N_("carte d'identité de {subject} à jour dans l'espace partagé ({detail})."),
    CheckCode.ZONE_COPY_MISSING: N_("carte d'identité {subject} absente de l'espace partagé."),
    CheckCode.ZONE_COPY_STALE: N_("carte d'identité de {subject} périmée dans l'espace partagé ({detail}) : "
                                  "version, racine ou contrats changés."),
    CheckCode.ZONE_COPY_RIGHTS: N_("{subject} : {detail} au lieu de root:omega-synchro 0640."),
    CheckCode.ZONE_NOT_LINKED: N_("{subject} ({detail}) installé mais pas encore dans l'espace partagé."),
    CheckCode.ZONE_TOOL_GONE: N_("{subject} ({detail}) relié à l'espace partagé mais introuvable : "
                                 "désinstallé, ou carte d'identité recréée."),
    CheckCode.ZONE_SERVICE_GROUP_OK: N_("le service {subject} ({detail}) a le groupe omega-synchro (complément "
                                        "systemd posé par omega-serv)."),
    CheckCode.ZONE_SERVICE_GROUP_MISSING: N_("le service {subject} ({detail}) tourne sous un compte dédié sans le "
                                             "groupe omega-synchro : il ne pourra pas lire l'espace partagé. "
                                             "La Synchronisation demande à omega-serv de le lui donner."),
}


def check_text(check: Check) -> str:
    return _(CHECK_MESSAGES[check.code]).format(subject=check.subject, detail=check.detail or "?")


def fix_lines(check: Check) -> list[str]:
    if not check.fix:
        return []
    if (check.repair is not None and check.repair.kind is RepairKind.ZONE) or check.fix.endswith(" etablir"):
        return [_("correction : Synchronisation (omega-connect synchroniser)")]
    if check.fix_account:
        return [_("correction (compte {account}) : {command}").format(account=check.fix_account, command=check.fix)]
    return [_("correction : {command}").format(command=check.fix)]


def _link_lines(link: Link, with_details: bool) -> list[str]:
    state = link.state
    lines = [f"  {STATE_MARKS[state]} {_(STATE_LABELS[state]):<15} {_(LINK_LABELS[link.kind])}"]
    hidden = 0
    for check in link.checks:
        if check.status is CheckStatus.OK and not with_details:
            hidden += 1
            continue
        lines.append(f"      {CHECK_MARKS[check.status]} {check_text(check)}")
        lines.extend(f"          {line}" for line in fix_lines(check))
    if hidden:
        lines.append("      " + _("{count} contrôle(s) conforme(s) (--detail pour les voir)").format(count=hidden))
    return lines


def render_text(report: VerificationReport, *, with_details: bool = False, bare: bool = False) -> str:
    """`bare` (rapport) : les liaisons seules, sans l'en-tete ni la conclusion propres a la commande `verifier`."""
    lines = [] if bare else [_("Vérification des liens entre outils omega (lecture seule, rien n'est modifié)"), ""]
    groups: dict[tuple[str, str], list[Link]] = {}
    for link in report.links:
        groups.setdefault((link.root, link.instance), []).append(link)
    for (root, instance), links in groups.items():
        if root:
            lines.append(_("omega-serv « {instance} » — {root}").format(instance=instance, root=root))
        elif links[0].kind in (LinkKind.FAIL2BAN_FILES, LinkKind.TOKENS, LinkKind.ZONE):
            lines.append(_("Machine"))
        else:
            lines.append(_("Hors des instances détectées"))
        for link in links:
            lines.extend(_link_lines(link, with_details))
        lines.append("")
    counts = {state: sum(1 for link in report.links if link.state is state) for state in LinkState}
    summary = ", ".join(f"{counts[state]} {_(STATE_LABELS[state])}" for state in LinkState if counts[state])
    lines.append(_("Bilan : {summary}.").format(summary=summary or "0"))
    if bare:
        return "\n".join(lines)
    if report.has_problems:
        lines.append(_("Les corrections ne sont jamais lancées par « verifier » : relisez-les avant de les "
                       "exécuter."))
        repairable = sum(1 for link in report.links for check in link.checks
                         if check.repair is not None and check.status in (CheckStatus.WARNING, CheckStatus.FAILURE))
        if repairable:
            lines.append(_("{count} écart(s) corrigeable(s) par « reparer » (commandes des outils, affichées "
                           "avant tout lancement).").format(count=repairable))
    return "\n".join(lines)


def _check_to_dict(check: Check) -> dict[str, str]:
    return {"code": check.code.value, "status": check.status.value, "subject": check.subject,
            "detail": check.detail, "fix": check.fix, "fix_account": check.fix_account,
            "repair": check.repair.kind.value if check.repair is not None else ""}


def verification_to_dict(report: VerificationReport) -> dict[str, Any]:
    return {
        "format": REPORT_FORMAT, "schema_version": REPORT_SCHEMA_VERSION,
        "links": [{"kind": link.kind.value, "instance": link.instance, "root": link.root,
                   "machine": link.machine, "peer": link.peer, "provenance": link.provenance.value,
                   "state": link.state.value, "checks": [_check_to_dict(check) for check in link.checks]}
                  for link in report.links],
        "detection": report_to_dict(report.detection),
    }
