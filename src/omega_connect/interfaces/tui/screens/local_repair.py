# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Réparer (menu Maintenance ; lot E) : les écarts de `verifier` corrigés par la commande de l'outil qui les
possède, affichées avant tout lancement ; puis, si la zone a des écarts, le plan d'« Établir » (écran du plan
du lot D). Ce qu'aucun outil ne sait corriger reste affiché, à faire à la main — et se copie (« Copier les
commandes »).

Machines distantes (retour de l'auteur, 2026-11-11 : « on ne peut rien réparer depuis omega-connect ») : une machine
du registre se répare depuis ici, les commandes des outils sont lancées SUR elle ; rien à y taper."""
from __future__ import annotations

import contextlib

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_connect.application.remote_sync import RemoteSyncTools
from omega_connect.application.repair_actions import RepairResult, RepairTools, repair_plan, run_steps
from omega_connect.application.zone_actions import ZoneTools, establish_plan
from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.links import LinkState, VerificationReport
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.remote import parse_target
from omega_connect.domain.repair import RepairPlan, RepairStep, StepOutcome
from omega_connect.domain.updates import Purpose
from omega_connect.domain.zone import ZoneFacts, ZonePlan
from omega_connect.interfaces.cli.repair_view import render_repair_plan, render_repair_result, repair_step_line
from omega_connect.interfaces.tui.screens._base import SUDO_MESSAGE, OmegaScreen, copy_commands, suspended
from omega_connect.interfaces.tui.screens._zone_flow import DetectNow, ZoneFlow
from omega_connect.interfaces.tui.screens.dashboard import VerifyNow
from omega_connect.interfaces.tui.screens.remote_machine import RemoteMachineScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.states import state_summary, theme_styles
from omega_connect.interfaces.tui.widgets.tables import WideTable
from omega_connect.shared.i18n import _


def _manual_commands(plan: RepairPlan) -> list[str]:
    return [finding.check.fix for finding in plan.manual if finding.check.fix]


def _establish(facts: ZoneFacts, detection: DetectionReport | None, tools: ZoneTools) -> ZonePlan:
    assert detection is not None
    return establish_plan(facts, detection, tools.subject.subject(), tools.now())


class LocalRepairScreen(OmegaScreen):
    def __init__(self, *, verify: VerifyNow, repair: RepairTools, zone: ZoneTools, detect: DetectNow,
                 remote_sync: RemoteSyncTools | None = None) -> None:
        super().__init__()
        self._remote_sync = remote_sync
        self._machines: tuple[MachineEntry, ...] = ()
        self._verify = verify
        self._repair = repair
        self._zone = zone
        self._flow = ZoneFlow(self, zone, detect, self._after_zone, self._busy)
        self._plan: RepairPlan | None = None
        self._preparing = False
        self._repairing = False
        self._ran = False

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RÉPARER CETTE MACHINE"), classes="omega-title")
            yield Static(_("Chaque écart est corrigé par l'outil qui possède le fichier (omega-jail, omega-serv, "
                           "jeton de chaque outil), ou par « Établir » pour ce que le registre de la zone dit "
                           "qu'omega-connect a créé. omega-connect ne réécrit jamais le fichier d'un autre outil. "
                           "Rien n'est lancé avant « Lancer »."), classes="omega-hint")
            yield Busy(id="busy")
            yield Static("", id="repair-plan")
            yield Static(_("AVANCEMENT"), classes="omega-subtitle", id="repair-progress-title")
            yield Static("", id="repair-progress")
            yield Static(_("MACHINES DISTANTES"), classes="omega-subtitle", id="remote-title")
            yield Static(_("Une machine du registre se répare depuis ici : les commandes des outils sont lancées "
                           "SUR elle, son mot de passe sudo est demandé une fois, dans ce terminal."),
                         classes="omega-hint", id="remote-hint")
            yield WideTable(id="remote-machines")
            with Horizontal(classes="omega-actions", id="remote-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Réparer la machine choisie"), id="repair-machine", disabled=True)
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Lancer"), id="run", variant="error", disabled=True)
            with Container(classes="omega-btn-frame", id="zone-frame"):
                yield Button(_("Zone : établir…"), id="zone", variant="primary")
            with Container(classes="omega-btn-frame", id="copy-frame"):
                yield Button(_("Copier les commandes"), id="copy")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Analyser de nouveau"), id="again")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#repair-progress-title", Static).display = False
        self.query_one("#zone-frame").display = False
        self.query_one("#copy-frame").display = False
        table = self.query_one("#remote-machines", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Machine"), _("Liaisons à corriger"), _("Applications"), _("Dernier scan"))
        for widget in ("#remote-title", "#remote-hint", "#remote-machines", "#remote-actions"):
            self.query_one(widget).display = self._remote_sync is not None
        self._show_machines()
        self._prepare()

    def _show_machines(self) -> None:
        if self._remote_sync is None:
            return
        with contextlib.suppress(NoMatches):
            self._machines = tuple(machine for machine in self._remote_sync.remote.parc.load()
                                   if not machine.local and parse_target(machine.target) is not None)
            table = self.query_one("#remote-machines", DataTable)
            table.clear()
            styles = theme_styles(self.app)
            for machine in self._machines:
                broken = sum(1 for link in machine.links if link.state in (LinkState.DEGRADED, LinkState.BROKEN))
                table.add_row(machine.label, Text(str(broken), style=f"bold {styles.get('warning', 'yellow')}")
                              if broken else Text("0", style=styles.get("success", "green")),
                              state_summary(machine.shown_rows(), styles) or "—", machine.scanned_at or "?")
            if not self._machines:
                table.add_row(_("aucune machine distante : scannez-en une (Scanner)"), "", "", "")
            table.refresh(layout=True)
            self.query_one("#repair-machine", Button).disabled = not self._machines

    # ---- plan ----
    def _prepare(self) -> None:
        if self._preparing or self._repairing:
            return
        self._preparing = True
        self.query_one("#run", Button).disabled = True
        self._busy(_("Préparation des réparations : vérification des liens en cours…"))
        self.run_worker(self._collect, thread=True, group="repair-plan", exclusive=True)

    def _collect(self) -> None:
        try:
            report = self._verify()
            plan = repair_plan(report, self._repair)
        except Exception as exc:  # noqa: BLE001 - jamais planter l'interface
            self.app.call_from_thread(self._error, str(exc) or type(exc).__name__)
            return
        self.app.call_from_thread(self._planned, report, plan)

    def _busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()

    def _error(self, message: str) -> None:
        self._preparing = False
        self._busy(None)
        with contextlib.suppress(NoMatches):
            self.query_one("#repair-plan", Static).update(_("Erreur : {message}").format(message=message))

    def _planned(self, report: VerificationReport, plan: RepairPlan) -> None:
        self._preparing = False
        self._busy(None)
        self.app.report = report  # type: ignore[attr-defined]
        self._plan = plan
        self._ran = False
        with contextlib.suppress(NoMatches):
            self.query_one("#repair-plan", Static).update(render_repair_plan(plan, as_root=self._zone.as_root))
            run = self.query_one("#run", Button)
            run.label = _("Lancer avec sudo") if plan.needs_root and not self._zone.as_root else _("Lancer")
            run.disabled = not plan.steps
            # Zone : tout de suite s'il n'y a rien d'autre, sinon apres les commandes (un jeton cree doit etre
            # recopie).
            self.query_one("#zone-frame").display = plan.offers_zone and not plan.steps
            self.query_one("#copy-frame").display = bool(_manual_commands(plan))
            self.query_one("#repair-progress-title", Static).display = False
            self.query_one("#repair-progress", Static).update("")

    # ---- actions ----
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "run":
            self._start()
        elif button == "zone":
            self._flow.propose(_establish, with_detection=True)
        elif button == "again":
            self._prepare()
        elif button == "copy" and self._plan is not None:
            copy_commands(self.app, _manual_commands(self._plan))
        elif button == "repair-machine" and self._remote_sync is not None:
            index = self.query_one("#remote-machines", DataTable).cursor_row
            target = parse_target(self._machines[index].target) if 0 <= index < len(self._machines) else None
            if target is not None:
                self.app.push_screen(RemoteMachineScreen(target=target, tools=self._remote_sync,
                                                         purpose=Purpose.REPAIR), lambda _ran: self._show_machines())
        elif button == "back":
            self.action_back()

    def action_back(self) -> None:
        if not self._repairing:
            super().action_back()

    def _start(self) -> None:
        plan = self._plan
        if plan is None or not plan.steps or self._repairing or self._ran:
            return
        if plan.needs_root and not self._zone.as_root:
            with suspended(self.app, SUDO_MESSAGE):
                authenticated = self._zone.runner.authenticate()
            if not authenticated:
                self.app.notify(_("Authentification sudo refusée ou annulée : rien n'a été lancé."), severity="error")
                return
        self._repairing = True
        for button in ("#run", "#again", "#back"):
            self.query_one(button, Button).disabled = True
        self.query_one("#repair-progress-title", Static).display = True
        self.run_worker(lambda: self._apply(plan), thread=True, group="repair", exclusive=True)

    def _apply(self, plan: RepairPlan) -> None:
        total = len(plan.steps)

        def step(index: int, item: RepairStep, outcome: StepOutcome) -> None:
            self.app.call_from_thread(self._progress, repair_step_line(index, total, item, outcome))

        try:
            result = run_steps(plan.steps, self._repair.runner, step)
        except Exception as exc:  # noqa: BLE001 - l'interface ne plante jamais pendant une action
            self.app.call_from_thread(self._finish, None, str(exc) or type(exc).__name__)
            return
        self.app.call_from_thread(self._finish, result, "")

    def _progress(self, line: str) -> None:
        with contextlib.suppress(NoMatches):
            progress = self.query_one("#repair-progress", Static)
            previous = str(progress.render())
            progress.update(f"{previous}\n{line}" if previous else line)
            self.query_one(VerticalScroll).scroll_end(animate=False)

    def _finish(self, result: RepairResult | None, error: str) -> None:
        self._repairing = False
        self._ran = True
        with contextlib.suppress(NoMatches):
            self.query_one("#again", Button).disabled = False
            self.query_one("#back", Button).disabled = False
            message = render_repair_result(result) if result is not None else _("Erreur : {message}").format(
                message=error)
            self._progress("\n" + message)
            ok = result is not None and result.ok
            self.app.notify(message.splitlines()[0], severity="information" if ok else "error")
            if ok and self._plan is not None and self._plan.offers_zone:
                # Parcours enchaine (retour de l'auteur, 2026-11-10) : le plan d'« Etablir » s'ouvre aussitot, pour
                # relier les jetons crees ; le bouton reste la si on le ferme.
                self.query_one("#zone-frame").display = True
                self._flow.propose(_establish, with_detection=True)

    def _after_zone(self, ran: bool) -> None:
        if ran:
            self._prepare()
