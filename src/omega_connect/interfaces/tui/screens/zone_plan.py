# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan d'une action root (lot D) : chaque commande affichee telle qu'elle sera lancee, puis, sur accord,
authentification sudo sur le vrai terminal et execution une a une dans un fil, avec l'avancement."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Static

from omega_connect.application.zone_actions import ApplyResult, ZoneTools, apply_plan
from omega_connect.domain.zone import CommandOutcome, Operation, ZoneFacts, ZonePlan
from omega_connect.interfaces.cli.zone_view import (
    PLAN_TITLES,
    command_line,
    describe,
    note_text,
    render_result,
    step_line,
)
from omega_connect.interfaces.tui.screens._base import SUDO_MESSAGE, OmegaScreen, suspended
from omega_connect.shared.i18n import _


def plan_text(plan: ZonePlan, *, as_root: bool) -> Text:
    text = Text()
    for number, operation in enumerate(plan.operations, start=1):
        text.append(f"{number:>2}. {describe(operation)}\n", style="bold")
        text.append(f"    {command_line(operation, as_root=as_root)}\n")
    if not plan.operations:
        text.append(_("Aucune commande.") + "\n", style="dim")
    return text


class ZonePlanScreen(OmegaScreen):
    """Renvoie (dismiss) True si des commandes ont ete lancees : l'ecran appelant se rafraichit."""

    def __init__(self, *, plan: ZonePlan, facts: ZoneFacts, tools: ZoneTools, authenticated: bool) -> None:
        super().__init__()
        self._plan = plan
        self._facts = facts
        self._tools = tools
        self._authenticated = authenticated or tools.as_root
        self._ran = False
        self._applying = False

    def compose(self) -> ComposeResult:
        plan = self._plan
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_(PLAN_TITLES[plan.action]).format(zone=plan.zone).upper(), classes="omega-title")
            yield Static(_("Commandes lancées une à une en root avec sudo, dans cet ordre. Rien n'est lancé avant "
                           "« Lancer ». Au premier échec tout s'arrête, et le registre garde la trace de ce qui a "
                           "été créé."), classes="omega-hint")
            yield Static(_("COMMANDES"), classes="omega-subtitle")
            yield Static(plan_text(plan, as_root=self._tools.as_root), id="plan-commands")
            yield Static(_("REMARQUES"), classes="omega-subtitle", id="plan-notes-title")
            yield Static("\n".join(f"· {note_text(note)}" for note in plan.notes), id="plan-notes")
            yield Static(_("AVANCEMENT"), classes="omega-subtitle", id="plan-progress-title")
            yield Static("", id="plan-progress")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Lancer avec sudo"), id="run", variant="error",
                             disabled=plan.refused or not plan.operations)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Annuler"), id="back", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#plan-notes-title", Static).display = bool(self._plan.notes)
        self.query_one("#plan-progress-title", Static).display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self._start()
        elif event.button.id == "back":
            self.action_back()

    def action_back(self) -> None:
        if not self._applying:
            self.dismiss(self._ran)  # type: ignore[arg-type]

    def _start(self) -> None:
        if self._applying or self._ran:
            return
        if not self._authenticated:
            with suspended(self.app, SUDO_MESSAGE):
                self._authenticated = self._tools.runner.authenticate()
            if not self._authenticated:
                self.app.notify(_("Authentification sudo refusée ou annulée : rien n'a été lancé."), severity="error")
                return
        self._applying = True
        self.query_one("#run", Button).disabled = True
        self.query_one("#back", Button).disabled = True
        self.query_one("#plan-progress-title", Static).display = True
        self.run_worker(self._apply, thread=True, group="zone", exclusive=True)

    def _apply(self) -> None:
        total = len(self._plan.operations)

        def step(index: int, operation: Operation, outcome: CommandOutcome) -> None:
            self.app.call_from_thread(self._progress, step_line(index, total, operation, outcome.ok, outcome.error))

        try:
            result = apply_plan(self._plan, self._facts, self._tools.runner, step)
        except Exception as exc:  # noqa: BLE001 - l'interface ne plante jamais pendant une action
            self.app.call_from_thread(self._finish, None, str(exc) or type(exc).__name__)
            return
        self.app.call_from_thread(self._finish, result, "")

    def _progress(self, line: str) -> None:
        with_progress = self.query_one("#plan-progress", Static)
        previous = str(with_progress.render())
        with_progress.update(f"{previous}\n{line}" if previous else line)
        self.query_one(VerticalScroll).scroll_end(animate=False)

    def _finish(self, result: ApplyResult | None, error: str) -> None:
        self._applying = False
        self._ran = True
        try:
            back = self.query_one("#back", Button)
        except NoMatches:
            return
        back.disabled = False
        back.label = _("Fermer")
        message = render_result(result, self._plan) if result is not None else _("Erreur : {message}").format(
            message=error)
        self._progress("\n" + message)
        if result is not None and result.ok:
            self.app.notify(message.splitlines()[0])
        else:
            self.app.notify(message.splitlines()[0], severity="error")
