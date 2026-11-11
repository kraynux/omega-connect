# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Textes de la synchronisation d'une machine distante (lot R3), communs a la ligne de commande et a l'interface."""
from __future__ import annotations

from omega_connect.application.remote_sync import MachinePlan, PlanFailure, PrepareFailure, SyncOutcome
from omega_connect.domain.updates import Purpose, ReleaseFailure, StepName, UpdateChoice
from omega_connect.domain.versions import UpdateMode, releases_url
from omega_connect.interfaces.cli.remote_view import failure_text, outcome_text
from omega_connect.shared.i18n import N_, _

RELEASE_FAILURES = {
    ReleaseFailure.NO_RELEASE: N_("aucune version publiée sur GitHub ({url})"),
    ReleaseFailure.NETWORK: N_("GitHub ne répond pas depuis cet ordinateur (réseau)"),
    ReleaseFailure.NO_SHA: N_("l'archive n'est pas citée dans sha.txt de la Release : refusée"),
    ReleaseFailure.BAD_SHA: N_("empreinte différente de sha.txt : archive refusée, rien n'est envoyé"),
    ReleaseFailure.TOO_LARGE: N_("fichier trop volumineux pour une archive d'outil : refusé"),
    ReleaseFailure.TOO_OLD_RELEASE: N_("la dernière version publiée sur GitHub ({latest}) est encore trop ancienne"),
}
MODE_LABELS = {
    UpdateMode.OVER: N_("extraction par-dessus, puis son install.sh"),
    UpdateMode.ASIDE: N_("ancienne installation mise de côté (sudo mv), nouvelle à sa place, puis son install.sh qui "
                         "reprend réglages et données"),
}
STEP_LABELS = {StepName.UPDATE: N_("Mise à jour"), StepName.REPAIR: N_("Réparer"), StepName.MANUAL: N_("Commande"),
               StepName.ENROLL: N_("Synchroniser")}


def release_failure_text(choice: UpdateChoice, failure: ReleaseFailure) -> str:
    return _(RELEASE_FAILURES[failure]).format(url=releases_url(choice.outdated.tool), latest=choice.latest or "?")


def update_line(choice: UpdateChoice) -> str:
    item = choice.outdated
    head = f"{item.tool} {item.version or '?'}"
    if item.incomplete and choice.possible:
        return _("{tool} {version} ({root}) : réinstallation (installation inachevée) — {how}").format(
            tool=item.tool, version=choice.latest, root=item.root, how=_(MODE_LABELS[choice.mode]))
    if item.incomplete:
        head += " " + _("(installation inachevée)")
    if choice.possible:
        return _("{head} → {latest} ({root}) : {how}").format(head=head, latest=choice.latest, root=item.root,
                                                              how=_(MODE_LABELS[choice.mode]))
    reason = release_failure_text(choice, choice.failure) if choice.failure else "?"
    return _("{head} ({root}) : pas de mise à jour possible — {reason}").format(head=head, root=item.root,
                                                                                reason=reason)


def _indent(text: str) -> list[str]:
    return [f"    {line}" if line else "" for line in text.rstrip("\n").splitlines()]


def reinstall_only(plan: MachinePlan) -> bool:
    """Seulement des installations inachevees : on parle de reinstaller, jamais de mettre a jour."""
    return bool(plan.updates) and all(choice.outdated.incomplete for choice in plan.updates)


def _password_line(name: str) -> str:
    return _("Tout se passe dans ce terminal : le mot de passe sudo de {name} est demandé par la machine "
             "elle-même, une fois ; omega-connect ne le voit jamais.").format(name=name)


def render_machine_plan(plan: MachinePlan) -> str:
    remote = plan.plan
    if plan.purpose is Purpose.UPDATE:
        title = _("Réinstaller l'application — machine {name} ({target})") if reinstall_only(plan) else \
            _("Mettre à jour l'application — machine {name} ({target})")
        lines = [title.format(name=remote.hostname, target=plan.target.text), ""]
        if not plan.updates:
            lines.append(_("Aucune application trop ancienne sur cette machine : rien à mettre à jour."))
            return "\n".join(lines) + "\n"
        lines.append(_("Archives prises sur la Release GitHub de chaque application (empreinte vérifiée avec "
                       "sha.txt avant tout envoi) :"))
        lines.extend(f"  · {update_line(choice)}" for choice in plan.updates)
        lines.append("")
        lines.append(_("Rien d'autre n'est fait. Ensuite, pour remettre les liens en place : Synchronisation."))
        if plan.needs_work:
            lines.append(_password_line(remote.hostname))
        return "\n".join(lines) + "\n"
    if plan.purpose is Purpose.REPAIR:
        return _render_repair(plan)
    lines = [_("Synchroniser — machine {name} ({target})").format(name=remote.hostname, target=plan.target.text),
             ""]
    if remote.outdated:
        lines.append(_("Laissées de côté, trop anciennes (Registre → « Mettre à jour l'application » d'abord) :"))
        lines.extend(f"  · {item.tool} {item.version or '?'} ({item.root})" for item in remote.outdated)
        lines.append("")
    if not plan.needs_work:
        lines.append(_("Rien à synchroniser : tout ce qui peut l'être est relié sur cette machine."))
        return "\n".join(lines) + "\n"
    lines.append(_("Réparer puis synchroniser, sur la machine. Plan :"))
    lines.extend(_indent(remote.repair_text))
    lines.extend(_indent(remote.enroll_text))
    if remote.space_unreadable:
        lines.append(_("L'espace partagé de cette machine n'est lisible qu'avec sudo : il sera relu au lancement."))
    lines.append("")
    lines.append(_password_line(remote.hostname))
    return "\n".join(lines) + "\n"


def _render_repair(plan: MachinePlan) -> str:
    remote = plan.plan
    lines = [_("Réparer — machine {name} ({target})").format(name=remote.hostname, target=plan.target.text), ""]
    lines.extend(_indent(remote.repair_text))
    lines.append("")
    if plan.needs_work:
        lines.append(_("« Réparer {name} » lance ces commandes SUR la machine, depuis ici.").format(
            name=remote.hostname))
        lines.append(_password_line(remote.hostname))
    if remote.manual_commands:
        lines.append("")
        lines.append(_("Commandes qu'aucun outil ne sait lancer — lancées AUSSI sur {name} par « Réparer {name} », "
                       "une à une, après les corrections des outils (celles déjà réglées entre-temps sont "
                       "sautées) :").format(name=remote.hostname))
        lines.extend(f"      {command}" for command in remote.manual_commands)
    return "\n".join(lines) + "\n"


def plan_failure_text(failure: PlanFailure) -> str:
    return failure_text(failure.failure, failure.target.text, failure.target.host, failure.detail)


def prepare_failure_text(failure: PrepareFailure) -> str:
    if failure.release:
        lines = [_("Rien n'a été envoyé à {target} :").format(target=failure.target.text)]
        lines.extend(f"  · {choice.outdated.tool} {choice.latest} : {release_failure_text(choice, reason)}"
                     for choice, reason in failure.release)
        return "\n".join(lines)
    return failure_text(failure.failure, failure.target.text, failure.target.host, failure.detail) \
        if failure.failure else _("Envoi impossible vers {target}.").format(target=failure.target.text)


def render_sync_outcome(outcome: SyncOutcome) -> str:
    lines = [_("Résultat pour {target} :").format(target=outcome.target.text)]
    if outcome.result is None or not outcome.result.steps:
        lines.append(_("  ✗ aucun résultat rendu par la machine (connexion coupée, ou lancement interrompu ; code "
                       "{code}).").format(code=outcome.code))
    else:
        for step in outcome.result.steps:
            mark = "✓" if step.ok else "✗"
            label = _(STEP_LABELS[step.name]) + (f" {step.tool}" if step.tool else "")
            detail = ""
            if step.name is StepName.UPDATE and step.ok and step.detail:
                detail = " — " + _("ancienne installation gardée dans {path}").format(path=step.detail)
            elif step.name is StepName.MANUAL:
                detail = f" — {step.detail}" + ("" if step.ok else " " + _("(code {code})").format(code=step.code))
            elif not step.ok:
                detail = " — " + (step.detail or _("code {code}").format(code=step.code))
            lines.append(f"  {mark} {label}{detail}")
    if outcome.rescan is not None:
        lines.append(outcome_text(outcome.rescan))
    return "\n".join(lines)
