# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ligne de commande d'omega-connect (spec etape 3, §3). Lot A : `detecter` ; lot B : `verifier` ;
lot D : `etablir`, `retirer` (commandes root affichees, accord, puis sudo commande par commande) ; lot E :
`reparer` (commandes des outils proprietaires, puis plan d'`etablir` pour la zone).

L'interface n'importe jamais l'infrastructure : la composition (app/main.py) lui passe les fonctions deja
cablees."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES

from omega_connect.application.enroll_actions import EnrollTools, enroll_plan, run_enroll
from omega_connect.application.remote_actions import RemoteTools, failed, forget_machine, scan_remote
from omega_connect.application.remote_sync import (
    PlanFailure,
    PrepareFailure,
    RemoteSyncTools,
    finish_machine,
    machine_plan,
    prepare_machine,
    run_prepared,
)
from omega_connect.application.repair_actions import RepairTools, repair_plan, run_steps
from omega_connect.application.report import FullReport
from omega_connect.application.zone_actions import (
    ZoneTools,
    apply_plan,
    establish_plan,
    needs_elevation,
    remove_all_plan,
    remove_tool_plan,
)
from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.fleet import registry_rows, space_status
from omega_connect.domain.links import VerificationReport
from omega_connect.domain.parc import MachineEntry, match_machine
from omega_connect.domain.remote import HostKey, RemoteFailure, RemoteTarget, parse_target
from omega_connect.domain.updates import Purpose
from omega_connect.domain.zone import ZoneFacts, ZonePlan
from omega_connect.interfaces.cli.detection_view import render_text, report_to_dict
from omega_connect.interfaces.cli.enroll_view import render_enroll_plan, render_enroll_result, render_rows
from omega_connect.interfaces.cli.remote_sync_view import (
    plan_failure_text,
    prepare_failure_text,
    render_machine_plan,
    render_sync_outcome,
)
from omega_connect.interfaces.cli.remote_view import outcome_text, suggestions_text, trust_question
from omega_connect.interfaces.cli.repair_view import render_repair_plan, render_repair_result, repair_step_line
from omega_connect.interfaces.cli.report_view import (
    export_name,
    render_report_html,
    render_report_text,
)
from omega_connect.interfaces.cli.report_view import report_to_dict as full_report_to_dict
from omega_connect.interfaces.cli.verification_view import render_text as render_verification
from omega_connect.interfaces.cli.verification_view import verification_to_dict
from omega_connect.interfaces.cli.zone_view import render_plan, render_result, step_line
from omega_connect.ports.export import ExportWriter
from omega_connect.ports.fleet import ParcStore
from omega_connect.shared.i18n import _


@dataclass(frozen=True)
class DetectRequest:
    manual_paths: list[str]
    with_sheets: bool


DetectFunction = Callable[[DetectRequest], DetectionReport]
VerifyFunction = Callable[[DetectRequest], VerificationReport]
DashboardFunction = Callable[[DetectRequest], int]
"""Ouvre le tableau de bord (interface) ; code de sortie."""
Ask = Callable[[str], str]
ReportFunction = Callable[[DetectRequest], FullReport]




def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omega-connect",
        description=_("Interconnecteur de la suite omega : détecte les outils installés, vérifie et "
                      "attribue les droits entre eux."),
    )
    commands = parser.add_subparsers(dest="command", required=True, title=_("commandes"),
                                     metavar=_("COMMANDE"))
    detect = commands.add_parser("detecter", help=_(
        "Cherche les outils omega installés (lecture seule, sans root)."), description=_(
        "Cherche les outils omega installés : registre d'omega-serv, services systemd / OpenRC / runit, "
        "HOME (3 niveaux), /srv (2 niveaux) et chemins saisis. Ne suit jamais un lien symbolique ni un "
        "montage réseau. Lit le jeton de chaque installation et demande sa fiche à l'outil, sous le "
        "compte propriétaire du dossier."))
    detect.add_argument("--chemin", action="append", default=[], metavar=_("DOSSIER"),
                        help=_("Dossier d'installation à examiner en plus (option répétable)."))
    detect.add_argument("--sans-fiche", action="store_true",
                        help=_("Ne demande pas la fiche aux outils (plus rapide, aucune commande lancée)."))
    detect.add_argument("--format", choices=("texte", "json"), default="texte",
                        help=_("texte (défaut, traduit) ou json (pour les scripts, jamais traduit)."))

    verify = commands.add_parser("verifier", help=_(
        "Vérifie les liens existants entre outils (lecture seule, sans root)."), description=_(
        "Détecte les outils (avec leur fiche), puis contrôle chaque lien : journaux d'omega-serv et de magnet "
        "lus par les jails d'omega-jail, pont fail2ban vers la liste noire, liste protégée, droits de la liste "
        "noire, fichiers d'omega-jail dans fail2ban, jetons. Chaque écart affiche la commande qui le "
        "corrigerait, sans jamais la lancer. Code de sortie : 0 sans écart, 1 si un lien est cassé ou "
        "dégradé."))
    verify.add_argument("--chemin", action="append", default=[], metavar=_("DOSSIER"),
                        help=_("Dossier d'installation à examiner en plus (option répétable)."))
    verify.add_argument("--detail", action="store_true", help=_("Affiche aussi les contrôles conformes."))
    verify.add_argument("--format", choices=("texte", "json"), default="texte",
                        help=_("texte (défaut, traduit) ou json (pour les scripts, jamais traduit)."))

    dashboard = commands.add_parser("tableau", help=_(
        "Ouvre le tableau de bord (défaut sans commande) : outils, liens et leur état, en lecture seule."),
        description=_("Tableau de bord en lecture seule : outils et instances, état de chaque lien, contrôles et "
                      "commandes de correction (jamais lancées). Nouvelle vérification à intervalle régulier "
                      "tant que l'écran est ouvert."))
    dashboard.add_argument("--chemin", action="append", default=[], metavar=_("DOSSIER"),
                           help=_("Dossier d'installation à examiner en plus (option répétable)."))

    establish = commands.add_parser("etablir", help=_(
        "Crée la zone neutre et y recopie jetons et fiches (root, après accord)."), description=_(
        "Crée le groupe omega-synchro et la zone neutre (/var/lib/omega-synchro, 2750), vous ajoute au groupe, "
        "recopie le jeton et la fiche de chaque outil détecté, et inscrit tout au registre. Relancée, elle "
        "actualise les copies. Chaque commande est affichée avant d'être lancée avec sudo."))
    establish.add_argument("--chemin", action="append", default=[], metavar=_("DOSSIER"),
                           help=_("Dossier d'installation à examiner en plus (option répétable)."))
    _plan_options(establish)

    remove = commands.add_parser("retirer", help=_(
        "Défait ce qu'omega-connect a créé : un outil désinstallé, ou toute la zone (root, après accord)."),
        description=_("« retirer CIBLE » enlève de la zone un outil désinstallé (nom, dossier ou 8 premiers "
                      "caractères de l'identifiant). « retirer --tout » défait exactement ce que le registre liste, "
                      "ou garde la zone telle quelle (liens figés). Chaque commande est affichée avant d'être "
                      "lancée avec sudo."))
    remove.add_argument("cible", nargs="?", metavar=_("CIBLE"), help=_("Outil à retirer de la zone."))
    remove.add_argument("--tout", action="store_true", help=_("Toute la zone (question : garder ou tout retirer)."))
    choice = remove.add_mutually_exclusive_group()
    choice.add_argument("--garder-zone", action="store_true",
                        help=_("Avec --tout : garder la zone, liens figés (rien n'est supprimé)."))
    choice.add_argument("--effacer", action="store_true", help=_("Avec --tout : tout retirer, sans question."))
    _plan_options(remove)

    scan = commands.add_parser("scanner", help=_(
        "Recherche les applications omega de cette machine et met à jour le registre (lecture seule)."),
        description=_("Lecture seule, sans mot de passe : chaque application trouvée, son service et son état "
                      "(Détectée, Inscrite, Reliée, À réparer, Ancienne version, Installation inachevée). Le "
                      "résultat est enregistré dans le registre du parc (var/parc.json)."))
    scan.add_argument("cible", nargs="?", metavar=_("UTILISATEUR@MACHINE"), help=_(
        "Machine distante à scanner par SSH avec vos clés (rien n'y est installé) ; sans cible : cette machine."))
    scan.add_argument("--chemin", action="append", default=[], metavar=_("DOSSIER"),
                      help=_("Dossier d'installation à examiner en plus (option répétable)."))
    scan.add_argument("--retirer", metavar=_("MACHINE"), help=_(
        "Retire une machine distante du registre (nom, adresse ou utilisateur@adresse) ; rien n'est modifié sur "
        "elle."))
    scan.add_argument("--liste", action="store_true", help=_(
        "Liste les machines que cet ordinateur sait déjà joindre (profils Unison, ~/.ssh/config, known_hosts)."))

    enroll = commands.add_parser("synchroniser", aliases=["inscrire"], help=_(
        "Remet en place les liens de ce qui est installé : cartes d'identité, espace partagé, accès des services — "
        "un seul plan."),
        description=_("Une seule action (décision de l'auteur) : recrée les cartes d'identité qui manquent "
                      "(commande de chaque outil, sous son compte), prépare l'espace partagé, y recopie les cartes "
                      "et donne l'accès aux services. Tout est affiché avant d'agir ; un seul mot de passe "
                      "administrateur. Sans CIBLE : toutes les applications de la machine."))
    enroll.add_argument("cibles", nargs="*", metavar=_("CIBLE"),
                        help=_("Application à synchroniser : nom (omega-fire) ou dossier ; plusieurs possibles."))
    enroll.add_argument("--chemin", action="append", default=[], metavar=_("DOSSIER"),
                        help=_("Dossier d'installation à examiner en plus (option répétable)."))
    enroll.add_argument("--machine", action="append", default=[], metavar=_("MACHINE"), help=_(
        "Machine distante déjà scannée (nom, adresse ou utilisateur@machine ; option répétable) : réparer puis "
        "synchroniser, sans rien taper là-bas (une application trop ancienne : mettre-a-jour d'abord)."))
    enroll.add_argument("--toutes-machines", action="store_true",
                        help=_("Toutes les machines distantes du registre, une à une (un mot de passe par machine)."))
    _plan_options(enroll)

    update = commands.add_parser("mettre-a-jour", help=_(
        "Met à jour les applications trop anciennes d'une machine distante, depuis leur Release GitHub (rien "
        "d'autre)."), description=_(
        "Archive prise sur GitHub, empreinte vérifiée avec sha.txt, puis installée sur la machine (comme la "
        "section « Mise à jour » du README de l'outil). Ne répare ni ne synchronise : voir synchroniser."))
    update.add_argument("--machine", action="append", default=[], metavar=_("MACHINE"),
                        help=_("Machine distante déjà scannée (nom, adresse ou utilisateur@machine ; répétable)."))
    update.add_argument("--toutes-machines", action="store_true",
                        help=_("Toutes les machines distantes du registre, une à une."))
    _plan_options(update)

    repair = commands.add_parser("reparer", help=_(
        "Corrige les écarts trouvés par verifier avec la commande de l'outil qui les possède (root, après accord)."),
        description=_(
            "Ne corrige que ce qu'un outil sait corriger lui-même (omega-jail --apply --update, omega-serv service "
            "permissions, synchro jeton de chaque outil) et ce que le registre de la zone dit qu'omega-connect a "
            "créé (plan d'etablir, affiché à son tour). omega-connect ne réécrit jamais le fichier d'un autre "
            "outil : le reste est affiché, à faire à la main. Chaque commande est affichée avant d'être lancée."))
    repair.add_argument("--chemin", action="append", default=[], metavar=_("DOSSIER"),
                        help=_("Dossier d'installation à examiner en plus (option répétable)."))
    repair.add_argument("--machine", action="append", default=[], metavar=_("MACHINE"),
                        help=_("Machine distante déjà scannée : réparée depuis ici, rien à taper là-bas (répétable)."))
    repair.add_argument("--toutes-machines", action="store_true",
                        help=_("Toutes les machines distantes du registre, une à une."))
    _plan_options(repair)

    report = commands.add_parser("rapport", help=_(
        "Rapport complet : outils, jetons, fiches, liens et tous leurs contrôles, zone et registre (lecture seule)."),
        description=_("Tout ce qu'omega-connect sait à cet instant, en lecture seule et sans root : outils et "
                      "instances, jetons, fiches, chaque lien avec tous ses contrôles et les commandes de correction, "
                      "remarques de la recherche, zone neutre et son registre. Affiché, ou enregistré dans "
                      "var/exports/ avec --enregistrer."))
    report.add_argument("--chemin", action="append", default=[], metavar=_("DOSSIER"),
                        help=_("Dossier d'installation à examiner en plus (option répétable)."))
    report.add_argument("--format", choices=("texte", "json", "html"), default="texte",
                        help=_("texte (défaut, traduit), json (jamais traduit) ou html (page autonome)."))
    report.add_argument("--theme", choices=sorted(EXPORT_PALETTES), default=DEFAULT_EXPORT_THEME,
                        help=_("Thème de la page HTML."))
    report.add_argument("--enregistrer", action="store_true",
                        help=_("Enregistre dans var/exports/ au lieu d'afficher, et donne le chemin."))
    return parser


def render_report(report: FullReport, file_format: str, theme: str = DEFAULT_EXPORT_THEME) -> tuple[str, str]:
    """Contenu et extension d'un rapport (ligne de commande et interface)."""
    if file_format == "json":
        return json.dumps(full_report_to_dict(report), indent=2, ensure_ascii=False) + "\n", "json"
    if file_format == "html":
        return render_report_html(report, theme), "html"
    return render_report_text(report), "txt"


def _plan_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--simulation", action="store_true",
                        help=_("Affiche seulement les commandes, sans rien lancer."))
    parser.add_argument("--oui", action="store_true",
                        help=_("Lance sans demander l'accord (les commandes restent affichées)."))


def _read_zone(tools: ZoneTools) -> tuple[ZoneFacts, bool]:
    """Zone lue sous votre compte ; avec sudo (lecture seule) si la session ne peut pas la lire."""
    facts = tools.inspector.inspect(elevated=False)
    if not needs_elevation(facts):
        return facts, False
    print(_("Votre session n'a pas encore le groupe omega-synchro (il ne compte qu'après une reconnexion) : "
            "lecture de la zone avec sudo (find, stat, cat)."))
    if not tools.runner.authenticate():
        print(_("Authentification sudo refusée ou annulée : rien n'est fait."), file=sys.stderr)
        return facts, False
    return tools.inspector.inspect(elevated=True), True


def _carry_out(plan: ZonePlan, facts: ZoneFacts, tools: ZoneTools, args: argparse.Namespace, ask: Ask,
               authenticated: bool) -> int:
    print(render_plan(plan, as_root=tools.as_root))
    if plan.refused:
        return 1
    if not plan.operations or args.simulation:
        return 0
    refused = _agree(args, tools, ask,
                     _("Lancer ces {count} commande(s) en root ? [o/N] ").format(count=len(plan.operations)))
    if refused is not None:
        return refused
    if not authenticated and not tools.runner.authenticate():
        print(_("Authentification sudo refusée ou annulée : rien n'a été lancé."), file=sys.stderr)
        return 1
    total = len(plan.operations)
    result = apply_plan(plan, facts, tools.runner,
                        lambda index, operation, outcome: print(step_line(index, total, operation, outcome.ok,
                                                                          outcome.error)))
    print(render_result(result, plan))
    return 0 if result.ok else 1


def _keep_zone(args: argparse.Namespace, tools: ZoneTools, ask: Ask) -> bool | None:
    if args.garder_zone or args.effacer:
        return bool(args.garder_zone)
    if not tools.interactive():
        print(_("Pas de terminal pour poser la question : relancez avec --garder-zone ou --effacer."),
              file=sys.stderr)
        return None
    answer = ask(_("Garder la zone (liens figés) [g], tout retirer [t], ou annuler [a] ? ")).strip().lower()
    if answer in ("g", "garder"):
        return True
    if answer in ("t", "tout"):
        return False
    return None


def _agree(args: argparse.Namespace, tools: ZoneTools, ask: Ask, question: str) -> int | None:
    """None : accord donne (ou --oui) ; sinon le code de sortie."""
    if args.oui:
        return None
    if not tools.interactive():
        print(_("Pas de terminal pour demander l'accord : relancez avec --oui, ou --simulation."), file=sys.stderr)
        return 2
    if ask(question).strip().lower() not in ("o", "oui", "y", "yes"):
        print(_("Abandon : rien n'a été lancé."))
        return 1
    return None


def _repair_command(args: argparse.Namespace, detect: DetectFunction, verify: VerifyFunction, tools: ZoneTools,
                    repair: RepairTools, ask: Ask) -> int:
    request = DetectRequest(manual_paths=list(args.chemin), with_sheets=True)
    plan = repair_plan(verify(request), repair)
    print(render_repair_plan(plan, as_root=tools.as_root))
    if plan.steps and not args.simulation:
        refused = _agree(args, tools, ask, _("Lancer ces {count} commande(s) ? [o/N] ").format(count=len(plan.steps)))
        if refused is not None:
            return refused
        if plan.needs_root and not tools.runner.authenticate():
            print(_("Authentification sudo refusée ou annulée : rien n'a été lancé."), file=sys.stderr)
            return 1
        total = len(plan.steps)
        result = run_steps(plan.steps, repair.runner,
                           lambda index, step, outcome: print(repair_step_line(index, total, step, outcome)))
        print(render_repair_result(result))
        if not result.ok:
            return 1
    if not plan.offers_zone:
        return 0
    print(_("Zone neutre : plan d'« etablir » (seulement ce que le registre dit avoir créé)."))
    facts, authenticated = _read_zone(tools)
    detection = detect(request)
    zone_plan = establish_plan(facts, detection, tools.subject.subject(), tools.now())
    return _carry_out(zone_plan, facts, tools, args, ask, authenticated)


def _scan_command(args: argparse.Namespace, verify: VerifyFunction, tools: ZoneTools, parc: ParcStore | None,
                  machine: str) -> int:
    from datetime import datetime, timezone

    from omega_lib.synchro.policies import format_utc

    report = verify(DetectRequest(manual_paths=list(args.chemin), with_sheets=True))
    facts = tools.inspector.inspect(elevated=False)
    rows = registry_rows(report, facts, machine)
    print(render_rows(rows, space_status(report), machine), end="")
    if parc is not None:
        try:
            parc.save(MachineEntry(machine, True, format_utc(datetime.now(timezone.utc)), rows))
        except OSError as error:
            print(_("Registre du parc non enregistré : {error}").format(error=error), file=sys.stderr)
    return 0


def _remote_scan_command(text: str, remote: RemoteTools, interactive: Callable[[], bool], ask: Ask) -> int:
    target = parse_target(text)
    if target is None:
        print(_("Saisissez utilisateur@machine (nom ou adresse), sans espace ni option."), file=sys.stderr)
        return 2
    check = remote.scanner.check_host(target)
    if check.key is HostKey.UNKNOWN:
        print(trust_question(check))
        if not interactive():
            print(_("Pas de terminal pour demander la confiance : rien n'a été fait."), file=sys.stderr)
            return 2
        if ask(_("Faire confiance à cette machine ? [o/N] ")).strip().lower() not in ("o", "oui", "y", "yes"):
            print(_("Rien n'a été fait."))
            return 1
        if not remote.scanner.trust(check):
            print(_("Impossible d'ajouter la clé à ~/.ssh/known_hosts."), file=sys.stderr)
            return 1
    elif check.key is not HostKey.KNOWN:
        outcome = failed(target, check.failure or RemoteFailure.UNREACHABLE, check.detail, remote)
        print(outcome_text(outcome), file=sys.stderr)
        return 1
    outcome = scan_remote(target, remote)
    print(outcome_text(outcome), file=sys.stdout if outcome.ok else sys.stderr)
    return 0 if outcome.ok else 1


def _targets(detection: DetectionReport, wanted: list[str]) -> tuple[str, ...] | None:
    if not wanted:
        return None
    cleaned = {item.rstrip("/") or item for item in wanted}
    return tuple(item.root for item in detection.installations
                 if item.tool in cleaned or item.root in cleaned)


def _enroll_command(args: argparse.Namespace, detect: DetectFunction, tools: ZoneTools, repair: RepairTools,
                    ask: Ask) -> int:
    enroll = EnrollTools(zone=tools, repair=repair,
                         detect=lambda: detect(DetectRequest(manual_paths=list(args.chemin), with_sheets=True)))
    facts, authenticated = _read_zone(tools)
    detection = enroll.detect()
    roots = _targets(detection, list(args.cibles))
    if roots == ():
        print(_("Aucune application ne correspond à : {targets}").format(targets=" ".join(args.cibles)),
              file=sys.stderr)
        return 2
    plan = enroll_plan(facts, detection, enroll, roots)
    print(render_enroll_plan(plan, as_root=tools.as_root))
    if plan.space.refused:
        return 1
    if plan.empty or args.simulation:
        return 0
    refused = _agree(args, tools, ask, _("Lancer ce plan ? [o/N] "))
    if refused is not None:
        return refused
    if plan.needs_root and not authenticated and not tools.runner.authenticate():
        print(_("Authentification refusée ou annulée : rien n'a été lancé."), file=sys.stderr)
        return 1
    cards = len(plan.cards)
    result = run_enroll(
        plan, enroll,
        on_card=lambda index, step, outcome: print(repair_step_line(index, cards, step, outcome)),
        on_space=lambda index, operation, outcome: print(step_line(index, len(plan.space.operations) or 1,
                                                                   operation, outcome.ok, outcome.error)))
    print(render_enroll_result(result))
    return 0 if result.ok else 1


def _remote_targets(args: argparse.Namespace, remote: RemoteTools) -> list[RemoteTarget] | None:
    machines = remote.parc.load()
    wanted: list[RemoteTarget] = []
    if args.toutes_machines:
        for machine in machines:
            target = parse_target(machine.target) if not machine.local and machine.target else None
            if target is not None:
                wanted.append(target)
    for text in args.machine:
        known = match_machine(machines, text)
        target = parse_target(known.target if known is not None and known.target else text)
        if target is None:
            print(_("Machine inconnue ou mal écrite : {target}").format(target=text), file=sys.stderr)
            return None
        wanted.append(target)
    unique: list[RemoteTarget] = []
    for target in wanted:
        if target not in unique:
            unique.append(target)
    return unique


def _remote_enroll_command(args: argparse.Namespace, sync: RemoteSyncTools, interactive: Callable[[], bool],
                           ask: Ask, purpose: Purpose = Purpose.SYNC) -> int:
    targets = _remote_targets(args, sync.remote)
    if targets is None:
        return 2
    if not targets:
        print(_("Aucune machine distante dans le registre : scannez-en une d'abord (scanner utilisateur@machine)."),
              file=sys.stderr)
        return 2
    worst = 0
    for target in targets:
        print("")
        check = sync.remote.scanner.check_host(target)
        if check.key is not HostKey.KNOWN:
            print(_("{target} : clé de la machine pas encore acceptée, ou machine injoignable — scannez-la d'abord "
                    "(scanner {target}).").format(target=target.text), file=sys.stderr)
            worst = max(worst, 1)
            continue
        plan = machine_plan(target, sync, purpose)
        if isinstance(plan, PlanFailure):
            print(plan_failure_text(plan), file=sys.stderr)
            worst = max(worst, 1)
            continue
        print(render_machine_plan(plan), end="")
        if not plan.needs_work or args.simulation:
            continue
        if not args.oui:
            if not interactive():
                print(_("Pas de terminal pour demander l'accord : relancez avec --oui, ou --simulation."),
                      file=sys.stderr)
                return 2
            if ask(_("Lancer sur {name} ? [o/N] ").format(name=plan.plan.hostname)).strip().lower() not in (
                    "o", "oui", "y", "yes"):
                print(_("Rien n'a été lancé sur {name}.").format(name=plan.plan.hostname))
                continue
        prepared = prepare_machine(plan, sync)
        if isinstance(prepared, PrepareFailure):
            print(prepare_failure_text(prepared), file=sys.stderr)
            worst = max(worst, 1)
            continue
        code = run_prepared(prepared, sync)
        outcome = finish_machine(prepared, code, sync)
        print(render_sync_outcome(outcome))
        if not outcome.ok:
            worst = max(worst, 1)
    return worst


def _zone_command(args: argparse.Namespace, detect: DetectFunction, tools: ZoneTools, ask: Ask) -> int:
    if args.command == "retirer" and bool(args.cible) == bool(args.tout):
        print(_("Indiquez soit un outil à retirer, soit --tout."), file=sys.stderr)
        return 2
    if args.command == "retirer" and (args.garder_zone or args.effacer) and not args.tout:
        print(_("--garder-zone et --effacer vont avec --tout."), file=sys.stderr)
        return 2
    keep: bool | None = False
    if args.command == "retirer" and args.tout:
        keep = _keep_zone(args, tools, ask)
        if keep is None:
            print(_("Abandon : rien n'a été lancé."))
            return 1
    facts, authenticated = _read_zone(tools)
    if args.command == "etablir":
        detection = detect(DetectRequest(manual_paths=list(args.chemin), with_sheets=True))
        plan = establish_plan(facts, detection, tools.subject.subject(), tools.now())
    elif args.tout:
        found = None if keep else detect(DetectRequest(manual_paths=[], with_sheets=True))
        plan = remove_all_plan(facts, tools.now(), keep_zone=bool(keep), detection=found)
    else:
        detection = detect(DetectRequest(manual_paths=[], with_sheets=False))
        plan = remove_tool_plan(facts, detection, args.cible, tools.now())
    return _carry_out(plan, facts, tools, args, ask, authenticated)


def run(argv: list[str], detect: DetectFunction, verify: VerifyFunction | None = None,
        dashboard: DashboardFunction | None = None, zone: ZoneTools | None = None, ask: Ask = input,
        report_of: ReportFunction | None = None, writer: ExportWriter | None = None,
        repair: RepairTools | None = None, parc: ParcStore | None = None, machine: str = "local",
        remote: RemoteTools | None = None, remote_sync: RemoteSyncTools | None = None) -> int:
    args = build_parser().parse_args(argv or ["tableau"])
    remote_wanted = args.command == "mettre-a-jour" or (
        args.command in ("synchroniser", "inscrire", "reparer") and (args.machine or args.toutes_machines))
    if remote_wanted:
        if remote_sync is None:
            print(_("Machines distantes indisponibles ici."), file=sys.stderr)
            return 2
        if args.command == "mettre-a-jour" and not (args.machine or args.toutes_machines):
            print(_("Indiquez --machine MACHINE ou --toutes-machines."), file=sys.stderr)
            return 2
        return _remote_enroll_command(args, remote_sync,
                                      zone.interactive if zone is not None else sys.stdin.isatty, ask,
                                      {"mettre-a-jour": Purpose.UPDATE, "reparer": Purpose.REPAIR}.get(
                                          args.command, Purpose.SYNC))
    if args.command == "scanner" and args.retirer and remote is not None:
        known = match_machine(remote.parc.load(), args.retirer)
        if known is None or not forget_machine(known, remote):
            print(_("Aucune machine distante du registre ne correspond à : {target}").format(target=args.retirer),
                  file=sys.stderr)
            return 2
        print(_("{machine} retirée du registre (rien n'a été modifié sur elle).").format(machine=known.label))
        return 0
    if args.command == "scanner" and args.liste and remote is not None:
        print(suggestions_text(remote.suggest(), remote.parc.load()))
        return 0
    if args.command == "scanner" and args.cible and remote is not None:
        return _remote_scan_command(args.cible, remote, zone.interactive if zone is not None else sys.stdin.isatty,
                                    ask)
    if args.command == "scanner" and zone is not None and verify is not None:
        return _scan_command(args, verify, zone, parc, machine)
    if args.command in ("synchroniser", "inscrire") and zone is not None and repair is not None:
        return _enroll_command(args, detect, zone, repair, ask)
    if args.command == "reparer" and zone is not None and repair is not None and verify is not None:
        return _repair_command(args, detect, verify, zone, repair, ask)
    if args.command == "rapport" and report_of is not None:
        full = report_of(DetectRequest(manual_paths=list(args.chemin), with_sheets=True))
        content, extension = render_report(full, args.format, args.theme)
        if args.enregistrer and writer is not None:
            print(_("Rapport enregistré : {path}").format(path=writer.save(export_name(full, extension), content)))
        else:
            print(content, end="")
        return 0
    if args.command in ("etablir", "retirer") and zone is not None:
        return _zone_command(args, detect, zone, ask)
    if args.command == "tableau" and dashboard is not None:
        return dashboard(DetectRequest(manual_paths=list(args.chemin), with_sheets=True))
    if args.command == "detecter":
        report = detect(DetectRequest(manual_paths=list(args.chemin), with_sheets=not args.sans_fiche))
        if args.format == "json":
            print(json.dumps(report_to_dict(report), indent=2, ensure_ascii=False))
        else:
            print(render_text(report))
        return 0
    if args.command == "verifier" and verify is not None:
        verification = verify(DetectRequest(manual_paths=list(args.chemin), with_sheets=True))
        if args.format == "json":
            print(json.dumps(verification_to_dict(verification), indent=2, ensure_ascii=False))
        else:
            print(render_verification(verification, with_details=args.detail))
        return 1 if verification.has_problems else 0
    return 2  # pragma: no cover - argparse refuse deja une commande inconnue


def main_with(detect: DetectFunction, verify: VerifyFunction | None = None, argv: list[str] | None = None,
              dashboard: DashboardFunction | None = None, zone: ZoneTools | None = None,
              report: ReportFunction | None = None, writer: ExportWriter | None = None,
              repair: RepairTools | None = None, parc: ParcStore | None = None, machine: str = "local",
              remote: RemoteTools | None = None, remote_sync: RemoteSyncTools | None = None) -> int:
    return run(sys.argv[1:] if argv is None else list(argv), detect, verify, dashboard, zone, report_of=report,
               writer=writer, repair=repair, parc=parc, machine=machine, remote=remote, remote_sync=remote_sync)
