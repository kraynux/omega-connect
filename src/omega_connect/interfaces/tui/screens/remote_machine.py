# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Synchroniser une machine distante (lot R3 ; ETUDE_REFONTE §16 : rien a taper sur la machine distante).

Plan calcule sur la machine (sans sudo) et affiche ; « Lancer » : archives prises sur GitHub et verifiees, envoyees,
puis l'interface laisse la place au terminal : la machine y demande elle-meme son mot de passe sudo (une fois), les
mises a jour et commandes s'affichent ; Entree ramene a l'interface, qui montre le resultat et rescanne la machine."""
from __future__ import annotations

import contextlib

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Static

from omega_connect.application.remote_actions import scan_remote
from omega_connect.application.remote_sync import (
    MachinePlan,
    PlanFailure,
    Prepared,
    PrepareFailure,
    RemoteSyncTools,
    SyncOutcome,
    finish_machine,
    machine_plan,
    prepare_machine,
    run_prepared,
)
from omega_connect.domain.remote import RemoteTarget
from omega_connect.domain.updates import Purpose
from omega_connect.interfaces.cli.remote_sync_view import (
    plan_failure_text,
    prepare_failure_text,
    reinstall_only,
    render_machine_plan,
    render_sync_outcome,
)
from omega_connect.interfaces.tui.screens._base import OmegaScreen, copy_commands, suspended
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.shared.i18n import N_, _

TERMINAL_MESSAGE = N_("omega-connect — synchronisation de {machine}. La machine demande elle-même son mot de passe "
                      "sudo (il ne s'affiche pas pendant la saisie) ; omega-connect ne le voit jamais.")
BACK_PROMPT = N_("Terminé. Appuyez sur Entrée pour revenir à omega-connect… ")


class RemoteMachineScreen(OmegaScreen):
    """Renvoie True si quelque chose a ete lance (la file « toutes les machines » continue)."""

    def __init__(self, *, target: RemoteTarget, tools: RemoteSyncTools, position: str = "",
                 purpose: Purpose = Purpose.SYNC) -> None:
        super().__init__()
        self._purpose = purpose
        self._target = target
        self._tools = tools
        self._position = position
        self._plan: MachinePlan | None = None
        self._ran = False
        self._working = False

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            if self._purpose is Purpose.UPDATE:
                title = _("METTRE À JOUR L'APPLICATION — {machine}").format(machine=self._target.text)
                hint = _("Seulement les applications trop anciennes de cette machine : dernière version prise sur "
                         "leur Release GitHub (empreinte vérifiée), installée comme le dit leur README. Rien "
                         "d'autre ; rien n'est fait avant « Lancer ».")
            elif self._purpose is Purpose.REPAIR:
                title = _("RÉPARER — {machine}").format(machine=self._target.text)
                hint = _("Corrections faites par les outils eux-mêmes, lancées SUR la machine depuis ici : rien à "
                         "y taper. Ce qu'aucun outil ne sait faire se copie (« Copier les commandes »). Rien "
                         "n'est fait avant « Lancer ».")
            else:
                title = _("SYNCHRONISER — {machine}").format(machine=self._target.text)
                hint = _("Plan calculé sur la machine elle-même, sans sudo : réparer puis synchroniser. Aucune mise "
                         "à jour ici (Registre → « Mettre à jour l'application ») ; rien n'est fait avant "
                         "« Lancer ».")
            yield Static(f"{title}  {self._position}".strip(), classes="omega-title")
            yield Static(hint, classes="omega-hint")
            yield Busy(id="busy")
            yield Static("", id="machine-plan")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Lancer"), id="launch", variant="primary", disabled=True)
            with Container(classes="omega-btn-frame", id="copy-frame"):
                yield Button(_("Copier les commandes"), id="copy")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#copy-frame").display = False
        self._busy(_("Calcul du plan sur {machine}…").format(machine=self._target.text))
        tools, target = self._tools, self._target

        def collect() -> None:
            try:
                result = machine_plan(target, tools, self._purpose)
            except Exception as exc:  # noqa: BLE001 - jamais planter l'interface
                self.app.call_from_thread(self._text, _("Erreur : {message}").format(message=exc))
                return
            self.app.call_from_thread(self._show_plan, result)

        self.run_worker(collect, thread=True, group="remote-plan", exclusive=True)

    def _busy(self, text: str | None) -> None:
        self._working = text is not None
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()
            self.query_one("#launch", Button).disabled = text is not None or self._plan is None \
                or not self._plan.needs_work or self._ran

    def _text(self, text: str) -> None:
        self._busy(None)
        with contextlib.suppress(NoMatches):
            self.query_one("#machine-plan", Static).update(text)

    def _show_plan(self, result: MachinePlan | PlanFailure) -> None:
        if isinstance(result, PlanFailure):
            self._text(plan_failure_text(result))
            return
        self._plan = result
        self._text(render_machine_plan(result))
        if not result.needs_work:
            # Rien a faire la-bas : le registre (dernier scan) peut etre perime ; rescan, la liste se met a jour.
            tools = self._tools

            def rescan() -> None:
                with contextlib.suppress(Exception):
                    scan_remote(result.target, tools.remote)

            self.run_worker(rescan, thread=True, group="remote-rescan", exclusive=True)
        with contextlib.suppress(NoMatches):
            update_label = _("Réinstaller sur {machine}") if reinstall_only(result) else \
                _("Mettre à jour sur {machine}")
            label = {Purpose.UPDATE: update_label, Purpose.REPAIR: _("Réparer {machine}")}.get(
                self._purpose, _("Synchroniser {machine}"))
            self.query_one("#copy-frame").display = bool(result.plan.manual_commands)
            self.query_one("#launch", Button).label = label.format(machine=result.plan.hostname)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "launch" and self._plan is not None and not self._working:
            self._launch(self._plan)
        elif event.button.id == "copy" and self._plan is not None:
            copy_commands(self.app, self._plan.plan.manual_commands)
        elif event.button.id == "back":
            self.action_back()

    def action_back(self) -> None:
        if not self._working:
            self.dismiss(self._ran)  # type: ignore[arg-type]

    def _launch(self, plan: MachinePlan) -> None:
        self._busy(_("Téléchargement et vérification des archives, envoi vers {machine}…").format(
            machine=plan.plan.hostname))
        tools = self._tools

        def send() -> None:
            try:
                prepared = prepare_machine(plan, tools)
            except Exception as exc:  # noqa: BLE001
                self.app.call_from_thread(self._text, _("Erreur : {message}").format(message=exc))
                return
            self.app.call_from_thread(self._in_terminal, plan, prepared)

        self.run_worker(send, thread=True, group="remote-send", exclusive=True)

    def _in_terminal(self, plan: MachinePlan, prepared: Prepared | PrepareFailure) -> None:
        if isinstance(prepared, PrepareFailure):
            self._text(prepare_failure_text(prepared) + "\n\n" + render_machine_plan(plan))
            return
        self._ran = True
        with suspended(self.app, _(TERMINAL_MESSAGE).format(machine=plan.plan.hostname)):
            code = run_prepared(prepared, self._tools)
            with contextlib.suppress(EOFError, OSError):
                input("\n" + _(BACK_PROMPT))
        self._busy(_("Lecture du résultat et nouveau scan de {machine}…").format(machine=plan.plan.hostname))
        tools = self._tools

        def finish() -> None:
            try:
                outcome = finish_machine(prepared, code, tools)
            except Exception as exc:  # noqa: BLE001
                self.app.call_from_thread(self._text, _("Erreur : {message}").format(message=exc))
                return
            self.app.call_from_thread(self._show_outcome, outcome)

        self.run_worker(finish, thread=True, group="remote-finish", exclusive=True)

    def _show_outcome(self, outcome: SyncOutcome) -> None:
        self._text(render_sync_outcome(outcome))
        self.app.notify(_("{machine} : synchronisation terminée.").format(machine=outcome.target.text)
                        if outcome.ok else _("{machine} : la synchronisation n'est pas allée au bout.").format(
                            machine=outcome.target.text), severity="information" if outcome.ok else "warning")

