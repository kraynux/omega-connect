# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""UPDATER (menu Maintenance, sous Reparer ; demande de l'auteur, 2026-11-22) : le seul endroit qui met a jour les
applications. Reparer et le Registre y renvoient, l'application deja cochee.

Lignes = ce qui est deja scanne (rien n'est rescanne a l'ouverture). « Verifier les versions » (la selection, ou
tout) ; « Mettre a jour la selection » / « Tout mettre a jour » (obsoletes et installations inachevees) : cette
machine d'abord, dans le terminal ; puis chaque machine du reseau, son plan affiche avant d'agir (archives
verifiees, envoyees, `install.sh` dans le terminal, un mot de passe par machine)."""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_connect.application.remote_sync import RemoteSyncTools
from omega_connect.application.updater import (
    AppRow,
    LocalPrepared,
    Releases,
    UpdateState,
    app_rows,
    check_versions,
    finish_local,
    prepare_local,
    run_local,
)
from omega_connect.domain.fleet import registry_rows
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.remote import parse_target
from omega_connect.domain.updates import Purpose
from omega_connect.interfaces.tui.screens._base import OmegaScreen, suspended
from omega_connect.interfaces.tui.screens.remote_machine import BACK_PROMPT, RemoteMachineScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.tables import WideTable
from omega_connect.shared.i18n import N_, _

SELECTED_MARK = Text(" ✔ ", style="bold reverse green")
UNSELECTED_MARK = Text("   ", style="reverse dim")
"""Cases lisibles de loin (retour de l'auteur, 2026-11-21 : cases trop petites)."""
STATE_WORDS = {
    UpdateState.NOT_CHECKED: N_("non vérifiée"),
    UpdateState.UP_TO_DATE: N_("à jour"),
    UpdateState.OUTDATED: N_("à mettre à jour"),
    UpdateState.INCOMPLETE: N_("installation inachevée — à réinstaller"),
    UpdateState.UNKNOWN: N_("aucune version publiée trouvée"),
    UpdateState.UNREACHABLE: N_("machine injoignable"),
}
STATE_STYLES = {
    UpdateState.UP_TO_DATE: "green", UpdateState.OUTDATED: "bold yellow", UpdateState.INCOMPLETE: "bold yellow",
    UpdateState.UNKNOWN: "dim", UpdateState.UNREACHABLE: "red", UpdateState.NOT_CHECKED: "dim",
}
LOCAL_MESSAGE = N_("omega-connect — mise à jour sur cette machine. Les install.sh peuvent demander le mot de passe "
                   "sudo (il ne s'affiche pas pendant la saisie).")


class UpdaterScreen(OmegaScreen):
    BINDINGS = [*OmegaScreen.BINDINGS, Binding("space", "choose_row", _("Choisir"), show=False)]

    def __init__(self, *, parc: object, releases: Releases, remote_sync: RemoteSyncTools | None,
                 rescan_local: Callable[[], None], runner: Callable[[list[str]], int], machine: str,
                 preselect: str = "") -> None:
        super().__init__()
        self._parc = parc
        self._releases = releases
        self._remote_sync = remote_sync
        self._rescan_local = rescan_local
        self._runner = runner
        self._machine = machine
        self._preselect = preselect
        """Nom de machine (ou cle machine:dossier) a cocher et verifier a l'ouverture (venu de Reparer ou du
        Registre)."""
        self._rows: list[AppRow] = []
        self._chosen: set[str] = set()
        self._queue: list[tuple[str, tuple[AppRow, ...]]] = []
        self._working = False
        self._report: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel omega-fill"):
            yield Static(_("UPDATER"), classes="omega-title")
            yield Static(_("Les applications déjà scannées, sur cette machine et sur le réseau. « Vérifier les "
                           "versions » cherche la dernière version publiée (GitHub, puis le site). Cochez (Entrée ou "
                           "Espace) puis « Mettre à jour la sélection », ou « Tout mettre à jour » : chaque machine "
                           "montre son plan avant d'agir, et un seul mot de passe est demandé, dans le terminal."),
                         classes="omega-hint")
            yield Static("", id="updater-status", classes="omega-hint")
            yield Busy(id="busy")
            yield WideTable(id="updater-table")
            yield Static("", id="updater-report")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Vérifier les versions"), id="check", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Mettre à jour la sélection"), id="update-chosen", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Tout mettre à jour"), id="update-all", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#updater-table", WideTable)
        table.cursor_type = "row"
        table.add_columns(" ", _("Machine"), _("Application"), _("Installée"), _("Disponible"), _("Source"),
                          _("État"))
        self._reload_rows()
        if self._preselect:
            self._chosen = {row.key for row in self._rows
                            if self._preselect in (row.machine, row.key)}
            self._check(only=set(self._chosen) or None)

    # ---- lignes ----
    def _reload_rows(self) -> None:
        known = {row.key: row for row in self._rows}
        try:
            machines = self._parc.load()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            machines = ()
        fresh = app_rows(machines)
        # garde les versions deja verifiees (meme outil) : pas de nouvelle requete au retour d'une mise a jour
        latest = {row.tool: row for row in known.values() if row.latest or row.failure}
        self._rows = [replace(row, latest=latest[row.tool].latest, origin=latest[row.tool].origin,
                              failure=latest[row.tool].failure) if row.tool in latest else row
                      for row in fresh]
        self._chosen &= {row.key for row in self._rows}
        self._fill()

    def _fill(self) -> None:
        with contextlib.suppress(NoMatches):
            table = self.query_one("#updater-table", WideTable)
            cursor = table.cursor_row
            table.clear()
            for row in self._rows:
                mark = SELECTED_MARK if row.key in self._chosen else UNSELECTED_MARK
                state = Text(_(STATE_WORDS[row.state]), style=STATE_STYLES[row.state])
                tool = _("{tool} (contient {tools})").format(tool=row.tool, tools=row.contains) if row.contains \
                    else row.tool
                table.add_row(mark, row.machine, tool, row.version or "?", row.latest or "—",
                              row.origin or "—", state, key=row.key)
            if cursor is not None and cursor < table.row_count:
                table.move_cursor(row=cursor)
            actionable = [row for row in self._rows if row.actionable]
            chosen_actionable = [row for row in actionable if row.key in self._chosen]
            self.query_one("#update-chosen", Button).disabled = self._working or not chosen_actionable
            self.query_one("#update-all", Button).disabled = self._working or not actionable
            self.query_one("#check", Button).disabled = self._working
            counts = {state: sum(1 for row in self._rows if row.state is state) for state in UpdateState}
            self.query_one("#updater-status", Static).update(
                _("{count} application(s) — à jour : {ok} ; à mettre à jour : {old} ; inachevées : {incomplete} ; "
                  "non vérifiées : {unchecked}.").format(
                    count=len(self._rows), ok=counts[UpdateState.UP_TO_DATE], old=counts[UpdateState.OUTDATED],
                    incomplete=counts[UpdateState.INCOMPLETE], unchecked=counts[UpdateState.NOT_CHECKED]))

    def action_choose_row(self) -> None:
        table = self.query_one("#updater-table", WideTable)
        if self._working or not self._rows or table.cursor_row is None or table.cursor_row >= len(self._rows):
            return
        self._chosen ^= {self._rows[table.cursor_row].key}
        self._fill()

    def on_data_table_row_selected(self, _event: DataTable.RowSelected) -> None:
        self.action_choose_row()

    def _busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()

    # ---- actions ----
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "back":
            self.action_back()
        elif button == "check":
            self._check(only=set(self._chosen) or None)
        elif button == "update-chosen":
            self._start([row for row in self._rows if row.key in self._chosen and row.actionable])
        elif button == "update-all":
            self._start([row for row in self._rows if row.actionable])

    def action_back(self) -> None:
        if not self._working:
            super().action_back()

    def _check(self, only: set[str] | None) -> None:
        self._working = True
        self._fill()
        self._busy(_("Recherche des dernières versions publiées (GitHub, puis le site)…"))
        rows = list(self._rows)

        def work() -> None:
            checked = check_versions(rows, self._releases, only)
            self.app.call_from_thread(self._checked, checked)

        self.run_worker(work, thread=True, group="updater", exclusive=True)

    def _checked(self, rows: list[AppRow]) -> None:
        self._working = False
        self._busy(None)
        self._rows = rows
        self._fill()

    def _start(self, rows: list[AppRow]) -> None:
        if not rows:
            return
        self._report = []
        local = tuple(row for row in rows if row.local)
        by_machine: dict[str, list[AppRow]] = {}
        for row in rows:
            if not row.local:
                by_machine.setdefault(row.target, []).append(row)
        self._queue = [(target, tuple(items)) for target, items in by_machine.items()]
        if local:
            self._update_local(local)
        else:
            self._next_remote()

    def _update_local(self, rows: tuple[AppRow, ...]) -> None:
        self._working = True
        self._fill()
        self._busy(_("Téléchargement et vérification des archives…"))

        def prepare() -> None:
            prepared = prepare_local(rows, self._releases)
            self.app.call_from_thread(self._run_local, prepared)

        self.run_worker(prepare, thread=True, group="updater", exclusive=True)

    def _run_local(self, prepared: LocalPrepared) -> None:
        self._busy(None)
        if prepared.refused:
            self._working = False
            for choice, failure in prepared.refused:
                self._report.append(f"✗ {self._machine} · {choice.outdated.tool} : {failure.value}")
            self._show_report()
            self._next_remote()
            return
        with suspended(self.app, _(LOCAL_MESSAGE)):
            run_local(prepared, self._runner)
            with contextlib.suppress(EOFError, KeyboardInterrupt):
                input(_(BACK_PROMPT))
        ok, text = finish_local(prepared)
        self._report.append(f"{'✓' if ok else '✗'} {self._machine}" + (f"\n{text}" if text else ""))
        self._busy(_("Rescan de cette machine…"))

        def rescan() -> None:
            with contextlib.suppress(Exception):
                self._rescan_local()
            self.app.call_from_thread(self._after_local)

        self.run_worker(rescan, thread=True, group="updater", exclusive=True)

    def _after_local(self) -> None:
        self._busy(None)
        self._working = False
        self._reload_rows()
        self._show_report()
        self._next_remote()

    def _next_remote(self, _ran: object = None) -> None:
        if _ran is not None:
            self._reload_rows()
        if not self._queue or self._remote_sync is None:
            self._queue = []
            self._chosen.clear()
            self._reload_rows()
            self._show_report()
            return
        target_text, rows = self._queue.pop(0)
        target = parse_target(target_text)
        if target is None:
            self._next_remote()
            return
        self.app.push_screen(
            RemoteMachineScreen(target=target, tools=self._remote_sync, purpose=Purpose.UPDATE,
                                items=tuple(row.outdated() for row in rows)),
            self._next_remote)

    def _show_report(self) -> None:
        with contextlib.suppress(NoMatches):
            if self._report:
                self.query_one("#updater-report", Static).update("\n".join(self._report))


def rescan_local_machine(verify: Callable[[], object], inspector: object, parc: object, machine: str) -> None:
    """Cette machine relue apres une mise a jour (comme le Scanner) : ses lignes du registre du parc a jour."""
    from omega_lib.synchro.policies import format_utc

    report = verify()
    facts = inspector.inspect(elevated=False)  # type: ignore[attr-defined]
    parc.save(MachineEntry(machine, True, format_utc(datetime.now(timezone.utc)),  # type: ignore[attr-defined]
                           registry_rows(report, facts, machine)))  # type: ignore[arg-type]
