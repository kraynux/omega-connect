# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Affichage du plan de `reparer` (lot E) : commandes des outils telles qu'elles seront lancees, avant tout
accord ; ecarts a corriger a la main ; decisions laissees a la personne. Partage par la ligne de commande et
l'interface."""
from __future__ import annotations

import shlex

from omega_connect.application.repair_actions import RepairResult
from omega_connect.domain.links import RepairKind
from omega_connect.domain.repair import Finding, RepairPlan, RepairStep, StepOutcome
from omega_connect.domain.versions import Outdated
from omega_connect.interfaces.cli.verification_view import LINK_LABELS, check_text
from omega_connect.shared.i18n import N_, _

STEP_TITLES = {
    RepairKind.TOKEN: N_("{tool} crée ou met à jour son jeton d'installation ({root})"),
    RepairKind.SERV_PERMISSIONS: N_("omega-serv répare les droits partagés avec le service {service} ({root})"),
    RepairKind.JAIL_APPLY: N_("omega-jail remet à jour ce qu'il a posé dans fail2ban (contenu et droits)"),
}
SKIP_REASONS = {
    "another-account": N_("{root} appartient au compte {account} : à lancer sous ce compte, ou avec omega-connect "
                          "en root."),
}


def describe_step(step: RepairStep) -> str:
    return _(STEP_TITLES[step.kind]).format(tool=step.tool, root=step.root, service=step.service)


def step_command(step: RepairStep, *, as_root: bool = False) -> str:
    command = shlex.join(step.argv())
    if step.needs_root:
        return command if as_root else f"sudo {command}"
    return command if not as_root else f"runuser -u {step.account} -- {command}"


def finding_line(finding: Finding) -> str:
    label = _(LINK_LABELS[finding.link.kind])
    where = f" « {finding.link.instance} »" if finding.link.instance else ""
    return f"{label}{where} : {check_text(finding.check)}"


def outdated_line(item: Outdated) -> str:
    if item.incomplete:
        return _("{tool} {version} dans {root} : environnement Python ou carte d'identité manquants").format(
            tool=item.tool, version=item.version or "?", root=item.root)
    return _("{tool} {version} dans {root} : {minimum} ou plus récent requis").format(
        tool=item.tool, version=item.version or "?", root=item.root, minimum=item.minimum or "?")


def render_repair_plan(plan: RepairPlan, *, as_root: bool = False) -> str:
    lines = [_("Réparer : corrections faites par les outils eux-mêmes"), ""]
    if plan.empty:
        lines.append(_("Rien à réparer : « verifier » ne signale aucun écart corrigeable."))
        return "\n".join(lines) + "\n"
    old = [item for item in plan.outdated if not item.incomplete]
    unfinished = [item for item in plan.outdated if item.incomplete]
    if old:
        lines.append(_("Trop ancien pour être réparé (ses commandes n'existent pas encore dans cette version) ; "
                       "à mettre à jour d'abord (Registre → « Mettre à jour l'application ») :"))
        lines.extend("  · " + outdated_line(item) for item in old)
        lines.append("")
    if unfinished:
        lines.append(_("Installation inachevée (son install.sh ne s'est pas terminé) : à réinstaller d'abord "
                       "(Registre → « Réinstaller l'application ») :"))
        lines.extend("  · " + outdated_line(item) for item in unfinished)
        lines.append("")
    if plan.steps:
        lines.append(_("Commandes qui seront lancées, une à une (arrêt au premier échec) :"))
        for number, step in enumerate(plan.steps, start=1):
            account = _("en root") if step.needs_root else _("sous le compte {account}").format(account=step.account)
            lines.append(f"  {number:>2}. {describe_step(step)} — {account}")
            lines.append(f"      {step_command(step, as_root=as_root)}")
            lines.extend(f"      · {finding_line(finding)}" for finding in step.findings)
        lines.append("")
    if plan.zone:
        lines.append(_("Zone neutre : « etablir » corrige ce que le registre dit avoir créé ; son plan sera affiché "
                       "ensuite, avant tout lancement :"))
        lines.extend(f"  · {finding_line(finding)}" for finding in plan.zone)
        lines.append("")
    if plan.relink and not plan.zone:
        lines.append(_("Ensuite : « etablir » reliera à la zone les outils dont le jeton vient d'être créé ; son plan "
                       "sera affiché avant tout lancement."))
        lines.append("")
    elif plan.zone_unreadable and not plan.zone:
        lines.append(_("Zone neutre : illisible sans sudo avant votre reconnexion, son état n'est pas connu. "
                       "« etablir » va la lire avec sudo et ne fera que ce qui manque (outils pas encore reliés, "
                       "copies, groupe du service) ; son plan sera affiché avant tout lancement."))
        lines.append("")
    if plan.skipped:
        lines.append(_("Non lancé depuis cette session :"))
        for skipped in plan.skipped:
            lines.append("  · " + _(SKIP_REASONS[skipped.reason]).format(root=skipped.step.root,
                                                                           account=skipped.step.account))
        lines.append("")
    if plan.manual:
        lines.append(_("À faire à la main (aucun outil ne sait le corriger lui-même ; omega-connect ne réécrit "
                       "jamais le fichier d'un autre outil) :"))
        for finding in plan.manual:
            lines.append(f"  · {finding_line(finding)}")
            lines.append(f"      {finding.check.fix}")
        lines.append("")
    if plan.decisions:
        lines.append(_("À décider (jamais lancé par « reparer ») :"))
        for finding in plan.decisions:
            lines.append(f"  · {finding_line(finding)}")
            lines.append(f"      {finding.check.fix}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def repair_step_line(index: int, total: int, step: RepairStep, outcome: StepOutcome) -> str:
    mark = "✔" if outcome.ok else "✘"
    line = f"  {mark} {index + 1}/{total} {describe_step(step)}"
    return line if outcome.ok else f"{line} : {outcome.error or _('échec')} ({_('code')} {outcome.code})"


def render_repair_result(result: RepairResult) -> str:
    failed = result.failed
    if failed is None:
        return _("Terminé : {count} commande(s) lancée(s), toutes réussies. Relancez « verifier » pour "
                 "constater.").format(count=len(result.outcomes))
    return "\n".join([
        _("Arrêt à l'étape « {step} » : {error}").format(step=describe_step(failed.step),
                                                         error=failed.error or _("échec")),
        _("Rien d'autre n'a été lancé. Relancez « reparer » après avoir corrigé la cause."),
    ])
