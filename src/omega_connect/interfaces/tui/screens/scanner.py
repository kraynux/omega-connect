# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scanner (refonte du parcours, lots R1 et R2) : analyse de la machine locale, et des machines distantes par SSH
avec vos clés (scanner envoyé en mémoire, rien installé là-bas), en lecture seule et sans mot de passe. Une machine
jamais jointe : empreinte de sa clé montrée, confiance demandée. Le résultat met à jour le registre du parc."""
from __future__ import annotations

import contextlib
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone

from omega_lib.synchro.policies import format_utc
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_connect.application.remote_actions import RemoteOutcome, RemoteTools, failed, forget_machine, scan_remote
from omega_connect.domain.detection import SOURCE_ORDER
from omega_connect.domain.fleet import registry_rows
from omega_connect.domain.links import VerificationReport
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.remote import HostCheck, HostKey, RemoteFailure, RemoteTarget, Suggestion, parse_target
from omega_connect.domain.zone import ZoneFacts
from omega_connect.interfaces.cli.detection_view import SOURCE_LABELS
from omega_connect.interfaces.cli.remote_view import last_scan_text, outcome_text, sources_text
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.screens.confirm import ConfirmScreen
from omega_connect.interfaces.tui.screens.dashboard import VerifyNow
from omega_connect.interfaces.tui.screens.trust_host import TrustHostScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.tables import WideTable
from omega_connect.ports.fleet import ParcStore
from omega_connect.ports.zone import ZoneInspector
from omega_connect.shared.i18n import _


def scan_summary(report: VerificationReport) -> str:
    installations = [item for item in report.detection.installations if item.tool]
    lines = [_("{count} application(s) omega trouvée(s) sur cette machine.").format(count=len(installations))]
    for tool, count in sorted(Counter(item.tool for item in installations).items()):
        lines.append(f"  · {tool} × {count}")
    sources = Counter(source for item in installations for source in item.sources)
    if sources:
        found = ", ".join(f"{_(SOURCE_LABELS[source])} ({sources[source]})" for source in SOURCE_ORDER
                          if source in sources)
        lines.append(_("Trouvées via : {sources}.").format(sources=found))
    if report.detection.scan_notes:
        lines.append(_("{count} remarque(s) sur la recherche (montages réseau ignorés, etc.) : voir le "
                       "Rapport.").format(count=len(report.detection.scan_notes)))
    return "\n".join(lines)


class ScannerScreen(OmegaScreen):
    def __init__(self, *, verify: VerifyNow, inspector: ZoneInspector, machine: str,
                 parc: ParcStore | None = None, registry: Callable[[], Screen[None]] | None = None,
                 remote: RemoteTools | None = None) -> None:
        """`registry` : ouvre le Registre (Scanner lance depuis le menu) ; None : on vient du Registre, « Voir le
        registre » y revient simplement."""
        super().__init__()
        self._registry = registry
        self._verify = verify
        self._inspector = inspector
        self._machine = machine
        self._parc = parc
        self._remote = remote
        self._scanning = False
        self._remote_working = False
        self._suggestions: tuple[Suggestion, ...] = ()
        self._known: tuple[MachineEntry, ...] = ()

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("SCANNER"), classes="omega-title")
            yield Static(_("Recherche des applications omega, en lecture seule : rien n'est modifié, aucun mot de "
                           "passe. Le résultat met à jour le registre."), classes="omega-hint")
            yield Static(_("MACHINE LOCALE — {machine}").format(machine=self._machine), classes="omega-subtitle")
            yield Busy(id="busy")
            yield Static("", id="scan-result")
            yield Static(_("MACHINES QUE CET ORDINATEUR SAIT DÉJÀ JOINDRE"), classes="omega-subtitle")
            yield Static(_("Trouvées dans vos profils Unison, votre ~/.ssh/config et les machines déjà connues de "
                           "SSH. Choisissez-en une (Entrée ou clic) : omega-connect s'y connecte avec vos clés et y "
                           "lance le même scanner, en mémoire — rien n'y est installé, aucun mot de passe."),
                         classes="omega-hint")
            yield WideTable(id="suggestions")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Scanner la machine choisie"), id="scan-suggested", variant="primary",
                             disabled=True)
            yield Static(_("AUTRE MACHINE (SAISIE MANUELLE)"), classes="omega-subtitle")
            yield Static(_("utilisateur@machine (nom ou adresse), ou un nom de votre ~/.ssh/config."),
                         classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                yield Input(placeholder=_("utilisateur@machine"), id="remote", disabled=self._remote is None)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Scanner cette machine"), id="scan-remote", disabled=self._remote is None)
            yield Busy(id="remote-busy")
            yield Static("", id="remote-result")
            yield Static(_("MACHINES DISTANTES CONNUES"), classes="omega-subtitle")
            yield Static(_("Celles du registre. Sur un grand parc, retirez celles qui ne vous concernent plus : elles "
                           "ne sont plus rescannées (rien n'est modifié sur elles)."), classes="omega-hint")
            yield WideTable(id="known-machines")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retirer cette machine"), id="forget", disabled=True)
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Scanner de nouveau"), id="scan")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Rescanner les machines connues"), id="scan-known", disabled=self._remote is None)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Voir le registre"), id="registry", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#suggestions", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Machine"), _("Trouvée dans"), _("Dernier scan"))
        known = self.query_one("#known-machines", DataTable)
        known.cursor_type = "row"
        known.add_columns(_("Machine"), _("Applications"), _("Dernier scan"), _("État"))
        self._show_machines()
        self._scan()

    def _busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()

    def _scan(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        self.query_one("#scan", Button).disabled = True
        self._busy(_("Analyse de la machine locale : recherche des applications omega…"))

        def collect() -> None:
            try:
                report = self._verify()
                facts = self._inspector.inspect(elevated=False)
            except Exception as exc:  # noqa: BLE001 - jamais planter l'interface
                self.app.call_from_thread(self._done, None, None, str(exc) or type(exc).__name__)
                return
            self.app.call_from_thread(self._done, report, facts, "")

        self.run_worker(collect, thread=True, group="scan", exclusive=True)

    def _done(self, report: VerificationReport | None, facts: ZoneFacts | None, error: str) -> None:
        self._scanning = False
        self._busy(None)
        with contextlib.suppress(NoMatches):
            self.query_one("#scan", Button).disabled = False
            result = self.query_one("#scan-result", Static)
            if report is None:
                result.update(_("Erreur : {message}").format(message=error))
                return
            moment = datetime.now().astimezone()
            self.app.report = report  # type: ignore[attr-defined]
            self.app.verified_at = moment  # type: ignore[attr-defined]
            result.update(scan_summary(report) + "\n" + _("Analysée à {time}.").format(
                time=moment.strftime("%H:%M:%S")))
            if self._parc is not None:
                try:
                    self._parc.save(MachineEntry(self._machine, True, format_utc(datetime.now(timezone.utc)),
                                                 registry_rows(report, facts, self._machine)))
                except OSError as exc:
                    self.app.notify(_("Registre du parc non enregistré : {error}").format(error=exc),
                                    severity="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan":
            self._scan()
        elif event.button.id == "scan-remote":
            self._scan_typed()
        elif event.button.id == "scan-suggested":
            self._scan_suggested()
        elif event.button.id == "forget":
            self._forget()
        elif event.button.id == "scan-known":
            self._scan_known()
        elif event.button.id == "registry":
            if self._registry is None:
                self.action_back()
            else:
                registry = self._registry
                self.dismiss()
                self.app.push_screen(registry())
        elif event.button.id == "back":
            self.action_back()

    # ---- machines distantes (lot R2) ----
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "remote":
            self._scan_typed()

    def _remote_busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one("#remote-busy", Busy)
            busy.show(text) if text is not None else busy.hide()
            for button in ("#scan-remote", "#scan-known", "#scan-suggested"):
                self.query_one(button, Button).disabled = text is not None or self._remote is None

    def _show_machines(self) -> None:
        with contextlib.suppress(NoMatches):
            machines = self._parc.load() if self._parc is not None else ()
            self._known = tuple(machine for machine in machines if not machine.local)
            known = self.query_one("#known-machines", DataTable)
            known.clear()
            for machine in self._known:
                known.add_row(machine.label, str(len(machine.rows)), machine.scanned_at or "?",
                              _("répond") if machine.reachable else _("injoignable"))
            if not self._known:
                known.add_row(_("aucune machine distante pour l'instant"), "", "", "")
            known.refresh(layout=True)
            self.query_one("#forget", Button).disabled = not self._known
            table = self.query_one("#suggestions", DataTable)
            cursor = table.cursor_row
            self._suggestions = self._remote.suggest() if self._remote is not None else ()
            table.clear()
            for item in self._suggestions:
                table.add_row(item.target.text, sources_text(item), last_scan_text(item, machines))
            if not self._suggestions:
                table.add_row(_("aucune machine trouvée"), "", "")
            elif cursor > 0:
                table.move_cursor(row=min(cursor, len(self._suggestions) - 1))
            table.refresh(layout=True)
            self.query_one("#scan-suggested", Button).disabled = not self._suggestions or self._remote_working

    def _forget(self) -> None:
        index = self.query_one("#known-machines", DataTable).cursor_row
        if self._remote is None or not 0 <= index < len(self._known):
            return
        machine = self._known[index]
        remote = self._remote

        def done(confirmed: bool | None) -> None:
            if confirmed and forget_machine(machine, remote):
                self.app.notify(_("{machine} retirée du registre.").format(machine=machine.label))
                self._show_machines()

        self.app.push_screen(ConfirmScreen(
            title=_("RETIRER CETTE MACHINE ?"),
            text=_("{machine} et ses {count} application(s) sortent du registre : elles ne seront plus rescannées. "
                   "Rien n'est modifié sur la machine ; vous pourrez la scanner de nouveau à tout moment.").format(
                machine=machine.label, count=len(machine.rows)),
            yes=_("Retirer"), no=_("Annuler")), done)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "suggestions":
            self._scan_suggested()

    def _scan_suggested(self) -> None:
        index = self.query_one("#suggestions", DataTable).cursor_row
        if 0 <= index < len(self._suggestions):
            self._scan_target(self._suggestions[index].target)

    def _scan_typed(self) -> None:
        target = parse_target(self.query_one("#remote", Input).value)
        if target is None:
            self.app.notify(_("Saisissez utilisateur@machine (nom ou adresse), sans espace ni option."),
                            severity="warning")
            return
        self._scan_target(target)

    def _scan_target(self, target: RemoteTarget) -> None:
        if self._remote is None or self._remote_working:
            return
        self._remote_working = True
        self._remote_busy(_("Connexion à {target}…").format(target=target.text))
        remote = self._remote

        def check() -> None:
            result = remote.scanner.check_host(target)
            self.app.call_from_thread(self._after_check, result)

        # Groupes distincts et non exclusifs : la verification de la clef lance elle-meme le scan ; dans un meme groupe
        # exclusif, le scan annulait la verification encore en cours (« Worker was cancelled », 2026-11-10).
        self.run_worker(check, thread=True, group="remote-check")

    def _after_check(self, check: HostCheck) -> None:
        if check.key is HostKey.KNOWN:
            self._run_remote(check.target)
        elif check.key is HostKey.UNKNOWN:
            self._remote_busy(None)
            self.app.push_screen(TrustHostScreen(check), lambda trusted: self._after_trust(check, bool(trusted)))
        else:
            self._run_remote(check.target, failure=check.failure or RemoteFailure.UNREACHABLE, detail=check.detail)

    def _after_trust(self, check: HostCheck, trusted: bool) -> None:
        if not trusted:
            self._remote_working = False
            self.app.notify(_("{target} : rien n'a été fait (machine non acceptée).").format(target=check.target.text))
            return
        assert self._remote is not None
        if not self._remote.scanner.trust(check):
            self._remote_working = False
            self.app.notify(_("Impossible d'ajouter la clé à ~/.ssh/known_hosts."), severity="error")
            return
        self._run_remote(check.target)

    def _run_remote(self, target: RemoteTarget, *, failure: RemoteFailure | None = None, detail: str = "") -> None:
        remote = self._remote
        assert remote is not None
        self._remote_busy(_("Scan de {target} : le scanner tourne là-bas, en lecture seule…").format(
            target=target.text))

        def work() -> None:
            outcome = (failed(target, failure, detail, remote) if failure is not None
                       else scan_remote(target, remote))
            self.app.call_from_thread(self._remote_done, [outcome])

        self.run_worker(work, thread=True, group="remote-scan")

    def _scan_known(self) -> None:
        remote = self._remote
        if remote is None or self._remote_working:
            return
        targets = [parse_target(machine.target) for machine in remote.parc.load() if not machine.local]
        known = [target for target in targets if target is not None]
        if not known:
            self.app.notify(_("Aucune machine distante connue pour l'instant."))
            return
        self._remote_working = True
        self._remote_busy(_("Scan des {count} machine(s) connue(s)…").format(count=len(known)))

        def work() -> None:
            outcomes = []
            for target in known:
                check = remote.scanner.check_host(target)
                if check.key is HostKey.KNOWN:
                    outcomes.append(scan_remote(target, remote))
                else:
                    reason = check.failure or (RemoteFailure.UNKNOWN_HOST if check.key is HostKey.UNKNOWN
                                               else RemoteFailure.CHANGED_HOST)
                    outcomes.append(failed(target, reason, check.detail, remote))
            self.app.call_from_thread(self._remote_done, outcomes)

        self.run_worker(work, thread=True, group="remote-scan")

    def _remote_done(self, outcomes: list[RemoteOutcome]) -> None:
        self._remote_working = False
        self._remote_busy(None)
        with contextlib.suppress(NoMatches):
            self.query_one("#remote-result", Static).update("\n\n".join(outcome_text(item) for item in outcomes))
        self._show_machines()
        good = sum(1 for item in outcomes if item.ok)
        self.app.notify(_("{good} machine(s) scannée(s) sur {total}.").format(good=good, total=len(outcomes)),
                        severity="information" if good == len(outcomes) else "warning")
