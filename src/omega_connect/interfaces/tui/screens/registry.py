# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Registre (refonte du parcours ; retours de l'auteur des 2026-11-10 et 11) : AFFICHAGE de ce qui a ete scanne —
chaque application omega, son service, sa version et son etat en couleur, comme les registres des autres outils.

Deux boutons, chacun une seule chose, et son nom le dit (« mettre a jour le registre, mettre a jour l'application,
synchroniser l'application, c'est pas la meme chose ») :
- « Mettre a jour le registre » : nouveau scan, sur place (cette machine et les machines connues) ;
- « Mettre a jour l'application » : la ligne choisie est « Ancienne version » sur une machine distante -> plan
  (version installee -> derniere version GitHub), puis lancement ; rien d'autre (les liens : Synchronisation)."""
from __future__ import annotations

import contextlib
from collections.abc import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_connect.application.remote_actions import RemoteTools, scan_remote
from omega_connect.application.remote_sync import RemoteSyncTools
from omega_connect.domain.fleet import AppState, RegistryRow, registry_rows, space_status
from omega_connect.domain.links import VerificationReport
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.remote import parse_target
from omega_connect.domain.updates import Purpose
from omega_connect.domain.zone import ZoneFacts
from omega_connect.interfaces.cli.enroll_view import SPACE_LABELS, state_hint
from omega_connect.interfaces.cli.verification_view import LINK_LABELS, check_text
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.screens.dashboard import VerifyNow
from omega_connect.interfaces.tui.screens.remote_machine import RemoteMachineScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.states import state_cell, state_summary, theme_styles
from omega_connect.interfaces.tui.widgets.tables import WideTable
from omega_connect.ports.fleet import ParcStore
from omega_connect.ports.zone import ZoneInspector
from omega_connect.shared.i18n import _


class RegistryScreen(OmegaScreen):
    def __init__(self, *, verify: VerifyNow, inspector: ZoneInspector, machine: str,
                 scanner: Callable[[], Screen[None]] | None = None, parc: ParcStore | None = None,
                 remote: RemoteTools | None = None, remote_sync: RemoteSyncTools | None = None) -> None:
        super().__init__()
        self._remote = remote
        self._remote_sync = remote_sync
        self._entries: tuple[MachineEntry | None, ...] = ()
        """Machine distante de chaque ligne (None : cette machine)."""
        self._parc = parc
        self._verify = verify
        self._inspector = inspector
        self._machine = machine
        self._scanner = scanner
        self._rows: tuple[RegistryRow, ...] = ()
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        # Le tableau remplit l'ecran et defile seul (grand parc : plusieurs machines ; retour de l'auteur).
        with Vertical(classes="omega-panel omega-fill"):
            yield Static(_("REGISTRE"), classes="omega-title")
            yield Static(_("Ce que le scanner a trouvé : chaque application omega, son service, sa version et son "
                           "état. « Mettre à jour le registre » refait le scan ; « Mettre à jour l'application » "
                           "installe la dernière version d'une application trop ancienne (ligne choisie). Remettre "
                           "les liens en place : Synchronisation ; corriger un écart : Réparer."), classes="omega-hint")
            yield Static("", id="registry-status", classes="omega-hint")
            yield Busy(id="busy")
            yield Static("", id="registry-summary")
            yield WideTable(id="registry-table")
            yield Static("", id="space-badge")
            yield Static("", id="row-detail")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Mettre à jour le registre"), id="update", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Mettre à jour l'application"), id="update-app", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#registry-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Machine"), _("Application"), _("Instance / service"), _("Version"), _("État"),
                          _("Dossier"))
        report = getattr(self.app, "report", None)
        self._load(report if isinstance(report, VerificationReport) else None)

    def _busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()

    def _load(self, report: VerificationReport | None) -> None:
        """Dernier scan s'il existe (affichage immediat) ; sinon un premier scan."""
        if self._loading:
            return
        self._loading = True
        self._busy(_("Lecture du registre…") if report is not None else
                   _("Premier scan : recherche des applications omega…"))

        def collect() -> None:
            try:
                current = report if report is not None else self._verify()
                facts = self._inspector.inspect(elevated=False)
            except Exception as exc:  # noqa: BLE001 - jamais planter l'interface
                self.app.call_from_thread(self._error, str(exc) or type(exc).__name__)
                return
            self.app.call_from_thread(self._show, current, facts, report is None)

        self.run_worker(collect, thread=True, group="registry", exclusive=True)

    def _error(self, message: str) -> None:
        self._loading = False
        self._busy(None)
        with contextlib.suppress(NoMatches):
            self.query_one("#registry-status", Static).update(_("Erreur : {message}").format(message=message))

    def _show(self, report: VerificationReport, facts: ZoneFacts, fresh: bool) -> None:
        self._loading = False
        self._busy(None)
        if fresh:
            from datetime import datetime

            self.app.report = report  # type: ignore[attr-defined]
            self.app.verified_at = datetime.now().astimezone()  # type: ignore[attr-defined]
        remote = [machine for machine in (self._parc.load() if self._parc is not None else ()) if not machine.local]
        local_rows = registry_rows(report, facts, self._machine)
        remote_rows = [(row, machine) for machine in remote for row in machine.shown_rows()]
        self._rows = local_rows + tuple(row for row, _machine in remote_rows)
        self._entries = (None,) * len(local_rows) + tuple(machine for _row, machine in remote_rows)
        moment = getattr(self.app, "verified_at", None)
        styles = theme_styles(self.app)
        with contextlib.suppress(NoMatches):
            status = _("{count} application(s) sur {machines} machine(s)").format(
                count=len(self._rows), machines=1 + len(remote))
            if moment is not None:
                status += " — " + _("dernier scan à {time}").format(time=moment.strftime("%H:%M:%S"))
            self.query_one("#registry-status", Static).update(status)
            self.query_one("#registry-summary", Static).update(state_summary(self._rows, styles))
            badge = Text(_("Espace partagé : "), style="bold")
            badge.append(_(SPACE_LABELS[space_status(report)]))
            self.query_one("#space-badge", Static).update(badge)
            table = self.query_one("#registry-table", DataTable)
            table.clear()
            for row in self._rows:
                service = (row.instance + (f" ({row.service_state})" if row.service_state else "")
                           if row.instance else "—")
                table.add_row(row.machine, row.tool, service, row.version or "?", state_cell(row.state, styles),
                              row.root)
            table.refresh(layout=True)
            self._describe_current()

    def _describe_current(self) -> None:
        try:
            index = self.query_one("#registry-table", DataTable).cursor_row
        except NoMatches:
            return
        detail = Text()
        can_update = False
        if 0 <= index < len(self._rows):
            row = self._rows[index]
            detail.append(f"{row.tool} — {row.root}\n", style="bold")
            detail.append(state_hint(row) + "\n")
            for link, check in row.findings:
                detail.append(f"  · {_(LINK_LABELS[link.kind])} : {check_text(check)}\n")
            if row.state in (AppState.OLD_VERSION, AppState.INCOMPLETE):
                entry = self._entries[index] if index < len(self._entries) else None
                can_update = entry is not None and self._remote_sync is not None and \
                    parse_target(entry.target) is not None
                action = _("Réinstaller l'application") if row.state is AppState.INCOMPLETE else \
                    _("Mettre à jour l'application")
                detail.append(_("→ « {action} » installe la dernière version depuis GitHub.").format(action=action)
                              if can_update else
                              _("→ Sur ce poste-ci, la mise à jour depuis omega-connect n'est pas encore possible : "
                                "suivez la section « Mise à jour » du README de l'outil."), style="bold")
        self.query_one("#row-detail", Static).update(detail)
        button = self.query_one("#update-app", Button)
        button.disabled = not can_update
        incomplete = 0 <= index < len(self._rows) and self._rows[index].state is AppState.INCOMPLETE
        button.label = _("Réinstaller l'application") if incomplete else _("Mettre à jour l'application")

    def on_data_table_row_highlighted(self, _event: DataTable.RowHighlighted) -> None:
        self._describe_current()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "update":
            self._refresh_registry()
        elif event.button.id == "update-app":
            self._update_application()
        elif event.button.id == "back":
            self.action_back()

    def _refresh_registry(self) -> None:
        """Sur place : machines distantes connues rescannees, puis cette machine."""
        if self._loading:
            return
        remote = self._remote
        machines = [machine for machine in (remote.parc.load() if remote is not None else ()) if not machine.local]
        if not machines or remote is None:
            self._load(None)
            return
        self._busy(_("Mise à jour du registre : scan de {count} machine(s) distante(s)…").format(count=len(machines)))

        def rescan() -> None:
            for machine in machines:
                target = parse_target(machine.target)
                if target is not None:
                    with contextlib.suppress(Exception):
                        scan_remote(target, remote)
            self.app.call_from_thread(self._load, None)

        self.run_worker(rescan, thread=True, group="registry-rescan", exclusive=True)

    def _update_application(self) -> None:
        index = self.query_one("#registry-table", DataTable).cursor_row
        entry = self._entries[index] if 0 <= index < len(self._entries) else None
        target = parse_target(entry.target) if entry is not None else None
        if target is None or self._remote_sync is None:
            return
        self.app.push_screen(RemoteMachineScreen(target=target, tools=self._remote_sync, purpose=Purpose.UPDATE),
                             lambda _ran: self._load(None))
