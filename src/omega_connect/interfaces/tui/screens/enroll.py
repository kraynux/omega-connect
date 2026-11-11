# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan de synchronisation (« Inscrire » du lot R1, ecran Synchronisation) : les deux etapes affichees avant
d'agir — cartes d'identite, puis espace partage — un seul mot de passe, puis l'avancement ligne a ligne. Une
commande non annoncee n'est jamais lancee."""
from __future__ import annotations

import contextlib

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Static

from omega_connect.application.enroll_actions import EnrollResult, EnrollTools, run_enroll
from omega_connect.domain.enroll import EnrollPlan
from omega_connect.domain.repair import RepairStep, StepOutcome
from omega_connect.domain.zone import CommandOutcome, Operation
from omega_connect.interfaces.cli.enroll_view import render_enroll_plan, render_enroll_result
from omega_connect.interfaces.cli.repair_view import repair_step_line
from omega_connect.interfaces.cli.zone_view import step_line
from omega_connect.interfaces.tui.screens._base import SUDO_MESSAGE, OmegaScreen, suspended
from omega_connect.shared.i18n import _


class EnrollScreen(OmegaScreen):
    """Renvoie (dismiss) True si quelque chose a ete lance : le registre se met a jour."""

    def __init__(self, *, plan: EnrollPlan, tools: EnrollTools, authenticated: bool) -> None:
        super().__init__()
        self._plan = plan
        self._tools = tools
        self._authenticated = authenticated or tools.zone.as_root
        self._working = False
        self._ran = False

    def compose(self) -> ComposeResult:
        plan = self._plan
        runnable = not plan.empty and not plan.space.refused
        label = _("Lancer (mot de passe administrateur)") if plan.needs_root and not self._authenticated \
            else _("Lancer")
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("SYNCHRONISER"), classes="omega-title")
            yield Static(_("Tout ce qui sera fait, dans l'ordre. Rien n'est lancé avant « Lancer » ; au premier "
                           "échec, tout s'arrête et ce qui a été créé reste noté."), classes="omega-hint")
            yield Static(render_enroll_plan(plan, as_root=self._tools.zone.as_root), id="enroll-plan")
            yield Static(_("AVANCEMENT"), classes="omega-subtitle", id="enroll-progress-title")
            yield Static("", id="enroll-progress")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(label, id="run", variant="error", disabled=not runnable)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Annuler"), id="back", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#enroll-progress-title", Static).display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self._start()
        elif event.button.id == "back":
            self.action_back()

    def action_back(self) -> None:
        if not self._working:
            self.dismiss(self._ran)  # type: ignore[arg-type]

    def _start(self) -> None:
        if self._working or self._ran:
            return
        if self._plan.needs_root and not self._authenticated:
            with suspended(self.app, SUDO_MESSAGE):
                self._authenticated = self._tools.zone.runner.authenticate()
            if not self._authenticated:
                self.app.notify(_("Authentification refusée ou annulée : rien n'a été lancé."), severity="error")
                return
        self._working = True
        self.query_one("#run", Button).disabled = True
        self.query_one("#back", Button).disabled = True
        self.query_one("#enroll-progress-title", Static).display = True
        self.run_worker(self._apply, thread=True, group="enroll", exclusive=True)

    def _apply(self) -> None:
        total_cards = len(self._plan.cards)

        def card(index: int, step: RepairStep, outcome: StepOutcome) -> None:
            self.app.call_from_thread(self._progress, repair_step_line(index, total_cards, step, outcome))

        def space(index: int, operation: Operation, outcome: CommandOutcome) -> None:
            self.app.call_from_thread(self._progress, step_line(index, len(self._plan.space.operations) or 1,
                                                                operation, outcome.ok, outcome.error))

        try:
            result = run_enroll(self._plan, self._tools, on_card=card, on_space=space)
        except Exception as exc:  # noqa: BLE001 - l'interface ne plante jamais pendant une action
            self.app.call_from_thread(self._finish, None, str(exc) or type(exc).__name__)
            return
        self.app.call_from_thread(self._finish, result, "")

    def _progress(self, line: str) -> None:
        with contextlib.suppress(NoMatches):
            progress = self.query_one("#enroll-progress", Static)
            previous = str(progress.render())
            progress.update(f"{previous}\n{line}" if previous else line)
            self.query_one(VerticalScroll).scroll_end(animate=False)

    def _finish(self, result: EnrollResult | None, error: str) -> None:
        self._working = False
        self._ran = True
        with contextlib.suppress(NoMatches):
            back = self.query_one("#back", Button)
            back.disabled = False
            back.label = _("Fermer")
        message = render_enroll_result(result) if result is not None else _("Erreur : {message}").format(
            message=error)
        self._progress("\n" + message)
        ok = result is not None and result.ok
        self.app.notify(message.splitlines()[0], severity="information" if ok else "error")
