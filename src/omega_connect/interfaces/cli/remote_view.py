# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Messages du scanner distant (lot R2) : chaque echec dit quoi faire, en mots simples ; jamais « erreur 255 »."""
from __future__ import annotations

from collections import Counter

from omega_connect.application.remote_actions import RemoteOutcome
from omega_connect.domain.parc import MachineEntry, find_machine
from omega_connect.domain.remote import HostCheck, RemoteFailure, Suggestion, SuggestionSource
from omega_connect.interfaces.cli.enroll_view import STATE_LABELS
from omega_connect.shared.i18n import N_, _

SUGGESTION_LABELS = {
    SuggestionSource.UNISON: N_("Unison"),
    SuggestionSource.SSH_CONFIG: N_("~/.ssh/config"),
    SuggestionSource.KNOWN_HOSTS: N_("connue de SSH"),
}


def sources_text(suggestion: Suggestion) -> str:
    return " + ".join(_(SUGGESTION_LABELS[source]) for source in suggestion.sources)


def last_scan_text(suggestion: Suggestion, machines: tuple[MachineEntry, ...]) -> str:
    known = find_machine(machines, address=suggestion.target.host)
    if known is None:
        return _("jamais scannée")
    state = _("répond") if known.reachable else _("injoignable")
    return _("{machine} — {count} application(s), {state}").format(machine=known.name, count=len(known.rows),
                                                                  state=state)


def suggestions_text(suggestions: tuple[Suggestion, ...], machines: tuple[MachineEntry, ...]) -> str:
    if not suggestions:
        return _("Aucune machine trouvée dans vos profils Unison, ~/.ssh/config ou known_hosts.")
    return "\n".join(f"  · {item.target.text:<40} {sources_text(item):<28} {last_scan_text(item, machines)}"
                     for item in suggestions)


FAILURE_MESSAGES = {
    RemoteFailure.UNREACHABLE: N_("{target} ne répond pas (machine éteinte, ou réseau coupé) : {detail}"),
    RemoteFailure.UNKNOWN_NAME: N_("Le nom « {host} » est inconnu sur ce réseau. Utilisez l'adresse de la machine "
                                   "(par exemple utilisateur@192.168.1.109), ou déclarez ce nom dans /etc/hosts ou "
                                   "dans ~/.ssh/config (Host {host} / HostName <adresse>)."),
    RemoteFailure.NO_SSH_SERVER: N_("{host} répond, mais aucun serveur SSH n'y écoute (port 22). Sur cette machine : "
                                    "installez et démarrez openssh (sudo systemctl enable --now sshd) ; ou, s'il "
                                    "écoute sur un autre port, indiquez-le dans ~/.ssh/config (Host {host} / Port …)."),
    RemoteFailure.AUTHENTICATION: N_("{target} refuse vos clés SSH. Ajoutez votre clé publique sur cette machine "
                                     "(ssh-copy-id {target}), ou chargez-la dans l'agent SSH si elle est protégée "
                                     "par une phrase secrète (ssh-add). omega-connect ne demande jamais de mot de "
                                     "passe."),
    RemoteFailure.UNKNOWN_HOST: N_("{target} n'est pas encore connue : sa clé doit d'abord être acceptée."),
    RemoteFailure.CHANGED_HOST: N_("La clé de {target} a CHANGÉ depuis la dernière connexion : scan refusé. Si la "
                                   "machine a été réinstallée, retirez l'ancienne clé (ssh-keygen -R {host}) puis "
                                   "recommencez ; sinon, quelqu'un se fait peut-être passer pour elle."),
    RemoteFailure.NO_PYTHON: N_("{target} n'a pas Python 3 (3.10 ou plus récent) : le scanner ne peut pas y "
                                "tourner. Rien n'a été installé."),
    RemoteFailure.SCAN_FAILED: N_("Le scan de {target} a échoué ({detail}). Rien n'a été modifié là-bas."),
    RemoteFailure.NO_SSH: N_("Pas de client SSH sur cette machine (commande {detail}) : installez openssh."),
}


def failure_text(outcome_failure: RemoteFailure, target: str, host: str, detail: str) -> str:
    return _(FAILURE_MESSAGES[outcome_failure]).format(target=target, host=host, detail=detail or "?")


def trust_question(check: HostCheck) -> str:
    lines = [_("{target} n'a jamais été jointe depuis ce compte. Vérifiez que l'empreinte de sa clé est bien la "
               "sienne (sur la machine : ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub) :").format(
        target=check.target.text), ""]
    lines.extend(f"  {fingerprint}" for fingerprint in check.fingerprints)
    lines += ["", _("En lui faisant confiance, elle est ajoutée à votre ~/.ssh/known_hosts.")]
    return "\n".join(lines)


def outcome_text(outcome: RemoteOutcome) -> str:
    target = outcome.target
    if outcome.scan is None:
        text = failure_text(outcome.failure or RemoteFailure.SCAN_FAILED, target.text, target.host, outcome.detail)
        if outcome.entry is not None and not outcome.entry.reachable:
            text += "\n" + _("Ses applications restent dans le registre, marquées « Injoignable ».")
        return text
    scan = outcome.scan
    label = outcome.entry.label if outcome.entry is not None else scan.hostname
    lines = [_("{machine} : {count} application(s) omega trouvée(s).").format(machine=label, count=len(scan.rows))]
    for state, count in sorted(Counter(row.state for row in scan.rows).items(), key=lambda item: item[0].value):
        lines.append(f"  · {count} {_(STATE_LABELS[state])}")
    return "\n".join(lines)


def machines_text(machines: tuple[MachineEntry, ...]) -> str:
    remote = [machine for machine in machines if not machine.local]
    if not remote:
        return _("Aucune machine distante pour l'instant.")
    lines = []
    for machine in remote:
        state = _("répond") if machine.reachable else _("injoignable")
        lines.append(_("  · {machine} — {count} application(s), dernier scan {date} ({state})").format(
            machine=machine.label, count=len(machine.rows), date=machine.scanned_at or "?", state=state))
    return "\n".join(lines)
