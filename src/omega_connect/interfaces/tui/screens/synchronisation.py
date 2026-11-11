# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Synchronisation (role defini par l'auteur, 2026-11-11 : « la liste de toutes les machines et services, et ca
synchronise »).

UNE seule liste : chaque application de cette machine et de chaque machine du reseau (rescannees a l'ouverture), avec
son etat (memes mots que le Registre). On coche, puis « Synchroniser la selection », ou « Synchroniser tout » :
- cette machine : un seul plan (cartes d'identite, puis espace partage), affiche avant d'agir, un mot de passe ;
- une machine du reseau : son plan calcule sur elle, lance depuis ici (un mot de passe par machine).
Les machines passent une a une. Une application trop ancienne, inachevee ou injoignable ne se coche pas : la ligne
dit ou aller. Etat de l'espace partage de cette machine en dessous (« Lire avec sudo » s'il est illisible)."""
from __future__ import annotations

import contextlib
from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_connect.application.enroll_actions import EnrollTools, enroll_plan
from omega_connect.application.remote_actions import scan_remote
from omega_connect.application.remote_sync import RemoteSyncTools
from omega_connect.domain.enroll import EnrollPlan
from omega_connect.domain.fail2ban import Presence
from omega_connect.domain.fleet import AppState, RegistryRow, SpaceStatus, registry_rows, selectable, space_status
from omega_connect.domain.links import Link, LinkKind, LinkState, VerificationReport
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.remote import parse_target
from omega_connect.domain.updates import Purpose
from omega_connect.domain.zone import ZoneFacts
from omega_connect.domain.zone_checks import zone_link
from omega_connect.interfaces.cli.enroll_view import SPACE_LABELS, state_hint
from omega_connect.interfaces.tui.presentation import check_lines
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.screens._zone_flow import ZoneFlow
from omega_connect.interfaces.tui.screens.dashboard import VerifyNow
from omega_connect.interfaces.tui.screens.enroll import EnrollScreen
from omega_connect.interfaces.tui.screens.remote_machine import RemoteMachineScreen
from omega_connect.interfaces.tui.screens.zone_detail import ZoneDetailScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.states import state_cell, theme_styles
from omega_connect.interfaces.tui.widgets.tables import WideTable
from omega_connect.shared.i18n import _

SELECTED_MARK = "☑"
UNSELECTED_MARK = "☐"
SYNCHRONISABLE = (AppState.DETECTED, AppState.ENROLLED, AppState.TO_FIX)
SPACE_NEEDS_WORK = (SpaceStatus.NOT_PREPARED, SpaceStatus.TO_FIX, SpaceStatus.UNKNOWN)
Key = tuple[str, str]
"""(machine, racine) : une ligne de la liste."""


class SynchronisationScreen(OmegaScreen):
    BINDINGS = [*OmegaScreen.BINDINGS, Binding("space", "choose_row", _("Choisir"), show=False)]

    def __init__(self, *, verify: VerifyNow, tools: EnrollTools, machine: str,
                 remote_sync: RemoteSyncTools | None = None) -> None:
        super().__init__()
        self._verify = verify
        self._tools = tools
        self._machine = machine
        self._remote_sync = remote_sync
        self._flow = ZoneFlow(self, tools.zone, tools.detect, lambda _ran: None, self._busy)
        self._report: VerificationReport | None = None
        self._rows: tuple[RegistryRow, ...] = ()
        self._entries: dict[str, MachineEntry] = {}
        """Machine du reseau de chaque ligne distante (par nom affiche)."""
        self._chosen: set[Key] = set()
        self._remote_queue: list[MachineEntry] = []
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel omega-fill"):
            yield Static(_("SYNCHRONISATION"), classes="omega-title")
            yield Static(_("Toutes vos machines et leurs applications. Cochez des lignes (Entrée ou Espace) puis "
                           "« Synchroniser la sélection », ou « Synchroniser tout ». Chaque machine a son plan, "
                           "affiché avant d'agir, et un seul mot de passe ; les machines du réseau sont "
                           "synchronisées depuis ici."), classes="omega-hint")
            yield Static("", id="sync-status", classes="omega-hint")
            yield Busy(id="busy")
            yield WideTable(id="sync-table")
            yield Static("", id="row-detail")
            yield Static("", id="space-badge")
            yield Static("", id="zone-checks")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Synchroniser tout"), id="enroll-all", variant="primary", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Synchroniser la sélection"), id="enroll-chosen", disabled=True)
            with Container(classes="omega-btn-frame", id="read-sudo-frame"):
                yield Button(_("Lire avec sudo"), id="read-sudo")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Détail"), id="detail")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sync-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(" ", _("Machine"), _("Application"), _("Instance / service"), _("État"))
        self.query_one("#read-sudo-frame").display = False
        self._load()

    # ---- lecture ----
    def _busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()

    def _load(self) -> None:
        """Toujours l'etat reel : cette machine verifiee, les machines du reseau rescannees."""
        if self._loading:
            return
        self._loading = True
        self._busy(_("Vérification de cette machine et de son espace partagé…"))
        remote = self._remote_sync.remote if self._remote_sync is not None else None

        def collect() -> None:
            try:
                report = self._verify()
                facts = self._tools.zone.inspector.inspect(elevated=False)
                machines = [entry for entry in (remote.parc.load() if remote is not None else ())
                            if not entry.local]
                for index, entry in enumerate(machines, start=1):
                    target = parse_target(entry.target)
                    if remote is None or target is None:
                        continue
                    self.app.call_from_thread(self._busy, _("Rescan des machines du réseau ({index}/{count}) : "
                                                            "{machine}…").format(index=index, count=len(machines),
                                                                                 machine=entry.label))
                    with contextlib.suppress(Exception):
                        scan_remote(target, remote)
                network = tuple(entry for entry in (remote.parc.load() if remote is not None else ())
                                if not entry.local)
            except Exception as exc:  # noqa: BLE001 - jamais planter l'interface
                self.app.call_from_thread(self._error, str(exc) or type(exc).__name__)
                return
            self.app.call_from_thread(self._show, report, facts, network, None)

        self.run_worker(collect, thread=True, group="sync", exclusive=True)

    def _error(self, message: str) -> None:
        self._loading = False
        self._busy(None)
        with contextlib.suppress(NoMatches):
            self.query_one("#sync-status", Static).update(_("Erreur : {message}").format(message=message))

    def _show(self, report: VerificationReport, facts: ZoneFacts, network: tuple[MachineEntry, ...],
              elevated_link: Link | None) -> None:
        self._loading = False
        self._busy(None)
        moment = datetime.now().astimezone()
        self.app.report = report  # type: ignore[attr-defined]
        self.app.verified_at = moment  # type: ignore[attr-defined]
        self._report = report
        self._entries = {entry.label: entry for entry in network}
        self._rows = registry_rows(report, facts, self._machine) + tuple(
            row for entry in network for row in entry.shown_rows())
        self._chosen &= {(row.machine, row.root) for row in self._rows if row.state in SYNCHRONISABLE}
        link = elevated_link or next((item for item in report.links if item.kind is LinkKind.ZONE), None)
        styles = theme_styles(self.app)
        with contextlib.suppress(NoMatches):
            status = _("{count} application(s) sur {machines} machine(s) — vérifié à {time}.").format(
                count=len(self._rows), machines=1 + len(network), time=moment.strftime("%H:%M:%S"))
            if elevated_link is not None:
                status += " " + _("Espace partagé lu avec sudo (lecture seule).")
            self.query_one("#sync-status", Static).update(status)
            badge = Text(_("Espace partagé de {machine} : ").format(machine=self._machine), style="bold")
            badge.append(_(SPACE_LABELS[space_status(report, elevated=elevated_link is not None)]))
            self.query_one("#space-badge", Static).update(badge)
            self.query_one("#zone-checks", Static).update(
                check_lines(link, styles, with_ok=False) if link is not None else "")
            unreadable = (link is not None and link.state is LinkState.UNVERIFIABLE
                          and facts.root.presence is not Presence.MISSING)
            self.query_one("#read-sudo-frame").display = unreadable
            self._fill()

    def _local(self, row: RegistryRow) -> bool:
        return row.machine not in self._entries

    def _remote_work(self) -> list[MachineEntry]:
        """Machines du reseau qui ont quelque chose a synchroniser."""
        names = dict.fromkeys(row.machine for row in self._rows
                              if not self._local(row) and row.state in SYNCHRONISABLE)
        return [self._entries[name] for name in names if name in self._entries]

    def _local_work(self) -> bool:
        local_rows = tuple(row for row in self._rows if self._local(row))
        space_work = self._report is not None and space_status(self._report) in SPACE_NEEDS_WORK
        return bool(selectable(local_rows)) or space_work

    def _fill(self) -> None:
        table = self.query_one("#sync-table", DataTable)
        row_index = table.cursor_row
        table.clear()
        styles = theme_styles(self.app)
        for row in self._rows:
            service = row.instance + (f" ({row.service_state})" if row.service_state else "") if row.instance else "—"
            mark = SELECTED_MARK if (row.machine, row.root) in self._chosen else (
                UNSELECTED_MARK if row.state in SYNCHRONISABLE else " ")
            table.add_row(mark, row.machine, row.tool, service, state_cell(row.state, styles))
        if self._rows:
            table.move_cursor(row=min(max(row_index, 0), len(self._rows) - 1))
        table.refresh(layout=True)
        self.query_one("#enroll-all", Button).disabled = not self._local_work() and not self._remote_work()
        self.query_one("#enroll-chosen", Button).disabled = not self._chosen
        self._describe_current()

    def _current(self) -> RegistryRow | None:
        try:
            index = self.query_one("#sync-table", DataTable).cursor_row
        except NoMatches:
            return None
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def _describe_current(self) -> None:
        row = self._current()
        detail = Text()
        if row is not None:
            detail.append(f"{row.machine} — {row.tool} — {row.root} : ", style="bold")
            detail.append(state_hint(row))
        self.query_one("#row-detail", Static).update(detail)

    def on_data_table_row_highlighted(self, _event: DataTable.RowHighlighted) -> None:
        self._describe_current()

    def on_data_table_row_selected(self, _event: DataTable.RowSelected) -> None:
        self.action_choose_row()

    def action_choose_row(self) -> None:
        row = self._current()
        if row is None:
            return
        if row.state not in SYNCHRONISABLE:
            self.app.notify(_("{tool} : {hint}").format(tool=row.tool, hint=state_hint(row)))
            return
        self._chosen ^= {(row.machine, row.root)}
        self._fill()

    # ---- actions ----
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "enroll-chosen":
            local = tuple(sorted(root for machine, root in self._chosen if machine not in self._entries))
            remote = [self._entries[name] for name in dict.fromkeys(machine for machine, _root in sorted(self._chosen))
                      if name in self._entries]
            self._start(local, remote)
        elif button == "enroll-all":
            self._start(None if self._local_work() else (), self._remote_work())
        elif button == "read-sudo":
            self._read_with_sudo()
        elif button == "detail":
            self.app.push_screen(ZoneDetailScreen(tools=self._tools.zone, detect=self._tools.detect),
                                 lambda _result: self._load())
        elif button == "back":
            self.action_back()

    def _start(self, local: tuple[str, ...] | None, remote: list[MachineEntry]) -> None:
        """`local` : racines choisies sur cette machine (None : toutes ; () : rien ici). Puis les machines du
        reseau, une a une."""
        self._remote_queue = list(remote)
        if local == ():
            self._next_remote()
        else:
            self._enroll(local)

    def _next_remote(self, _ran: object = None) -> None:
        if not self._remote_queue or self._remote_sync is None:
            self._remote_queue = []
            self._chosen.clear()
            self._load()
            return
        entry = self._remote_queue.pop(0)
        target = parse_target(entry.target)
        if target is None:
            self._next_remote()
            return
        self.app.push_screen(RemoteMachineScreen(target=target, tools=self._remote_sync, purpose=Purpose.SYNC),
                             self._next_remote)

    def _read_with_sudo(self) -> None:
        report = self._report

        def show(facts: ZoneFacts, _authenticated: bool) -> None:
            self._busy(None)
            if report is None or facts.root.presence is Presence.UNKNOWN or not facts.listing_known:
                return
            link = zone_link(facts, report.detection, self._tools.zone.subject.subject(), self._tools.zone.command)
            self._show(report, facts, tuple(self._entries.values()), link)

        self._busy(_("Lecture de l'espace partagé…"))
        self._flow.read_zone(show, elevate=True)

    def _enroll(self, roots: tuple[str, ...] | None) -> None:
        self._busy(_("Préparation du plan de synchronisation de {machine}…").format(machine=self._machine))

        def with_facts(facts: ZoneFacts, authenticated: bool) -> None:
            def build() -> None:
                try:
                    plan = enroll_plan(facts, self._tools.detect(), self._tools, roots)
                except Exception as exc:  # noqa: BLE001 - jamais planter l'interface
                    self.app.call_from_thread(self._error, str(exc) or type(exc).__name__)
                    return
                self.app.call_from_thread(show, plan, authenticated)

            self._busy(_("Préparation du plan de synchronisation de {machine}…").format(machine=self._machine))
            self.run_worker(build, thread=True, group="enroll-plan", exclusive=True)

        def show(plan: EnrollPlan, authenticated: bool) -> None:
            self._busy(None)
            self.app.push_screen(EnrollScreen(plan=plan, tools=self._tools, authenticated=authenticated),
                                 self._next_remote)

        self._flow.read_zone(with_facts, elevate=True)
