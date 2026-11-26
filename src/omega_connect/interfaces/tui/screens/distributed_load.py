# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Charge distribuee d'omega-stress (lot L2, 2026-11-21) : ouvert depuis Synchronisation (l'ecran qui agit) et
depuis Reparer. Cette machine pilote ; chaque machine du reseau ou omega-stress est installe peut aider.

On coche les machines, on choisit l'accord, un bouton : le plan s'affiche (commandes exactes), puis un seul mot de
passe sudo si le pare-feu de cette machine doit s'ouvrir. Aucune commande a taper, aucune empreinte a recopier."""
from __future__ import annotations

import contextlib

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, RadioButton, RadioSet, Static

from omega_connect.application.distributed_actions import (
    DistributedTools,
    StepResult,
    needs_root,
    plan,
    run_plan,
    unlink,
)
from omega_connect.application.remote_actions import RemoteTools
from omega_connect.domain.distributed_load import Accord, Helper, LinkStep, PilotState, StepWhere, shown
from omega_connect.domain.links import CheckCode, Link, LinkKind, LinkState
from omega_connect.domain.parc import MachineEntry
from omega_connect.interfaces.tui.presentation import state_text
from omega_connect.interfaces.tui.screens._base import SUDO_MESSAGE, OmegaScreen, suspended
from omega_connect.interfaces.tui.screens.confirm import ConfirmScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.scan_banner import ScanBanner
from omega_connect.interfaces.tui.widgets.states import theme_styles
from omega_connect.interfaces.tui.widgets.tables import SELECTED_MARK, UNSELECTED_MARK, WideTable
from omega_connect.shared.i18n import N_, _

"""Cases lisibles de loin (retour de l'auteur, 2026-11-21 : cases trop petites)."""
LINK_WORDS = {
    CheckCode.STRESS_LINKED: N_("reliée"),
    CheckCode.STRESS_NOT_LINKED: N_("non reliée"),
    CheckCode.STRESS_HALF_LINKED: N_("liaison incomplète"),
    CheckCode.STRESS_FIREWALL_CLOSED: N_("reliée, pare-feu de cette machine fermé"),
    CheckCode.STRESS_NEEDS_OMEGA_FIRE: N_("reliée, omega-fire nécessaire pour le pare-feu"),
    CheckCode.STRESS_HELPER_UNREADABLE: N_("état illisible (version trop ancienne ?)"),
    CheckCode.STRESS_NO_PILOT: N_("omega-stress absent de cette machine"),
}
ACCORD_WORDS = {Accord.ASK: N_("demander"), Accord.ALL: N_("tout accepter")}


OLD_VERSION = N_("Ancienne version")
SELECTABLE = (CheckCode.STRESS_LINKED, CheckCode.STRESS_NOT_LINKED, CheckCode.STRESS_HALF_LINKED,
              CheckCode.STRESS_FIREWALL_CLOSED, CheckCode.STRESS_NEEDS_OMEGA_FIRE)
Key = tuple[str, str]
"""(machine, dossier d'omega-stress) : une machine peut en avoir plusieurs."""


def selectable(link: Link) -> bool:
    return any(check.code in SELECTABLE for check in link.checks)


def link_words(link: Link) -> str:
    if link.instance:  # omega-stress trop ancien sur cette machine (jamais lance par le scan)
        return f"{_(OLD_VERSION)} ({link.instance})"
    for code in (CheckCode.STRESS_FIREWALL_CLOSED, CheckCode.STRESS_NEEDS_OMEGA_FIRE, CheckCode.STRESS_HALF_LINKED,
                 CheckCode.STRESS_HELPER_UNREADABLE, CheckCode.STRESS_NO_PILOT, CheckCode.STRESS_NOT_LINKED,
                 CheckCode.STRESS_LINKED):
        if any(check.code is code for check in link.checks):
            return _(LINK_WORDS[code])
    return ""


def accord_of(link: Link) -> str:
    check = next((c for c in link.checks if c.code is CheckCode.STRESS_LINKED), None)
    try:
        return _(ACCORD_WORDS[Accord(check.detail)]) if check and check.detail else ""
    except ValueError:
        return ""


class DistributedLoadScreen(OmegaScreen):
    BINDINGS = [*OmegaScreen.BINDINGS, Binding("space", "choose_row", _("Choisir"), show=False)]

    def __init__(self, *, tools: DistributedTools, remote: RemoteTools, sudo: object,
                 preselect: str = "") -> None:
        super().__init__()
        self._tools = tools
        self._remote = remote
        self._sudo = sudo
        self._pilot: PilotState | None = None
        self._rows: list[tuple[MachineEntry, Link]] = []
        self._preselect = preselect
        self._chosen: set[Key] = set()
        self._working = False
        self._changed = False
        """Une liaison faite ou retiree : l'ecran qui a ouvert celui-ci se met a jour au retour (sinon rien
        n'est rescanne en revenant ; retour de l'auteur, 2026-11-21)."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel omega-fill"):
            yield Static(_("CHARGE DISTRIBUÉE (OMEGA-STRESS)"), classes="omega-title")
            yield Static(_("Cette machine pilote les tests ; les machines cochées l'aident à charger la cible. "
                           "Cochez-les (Entrée ou Espace), choisissez leur accord, puis « Relier la sélection » : "
                           "le plan s'affiche avant d'agir, et un seul mot de passe est demandé si le pare-feu de "
                           "cette machine doit s'ouvrir."), classes="omega-hint")
            yield ScanBanner()
            yield Static("", id="distributed-status", classes="omega-hint")
            yield Busy(id="busy")
            yield WideTable(id="distributed-table")
            with RadioSet(id="accord"):
                yield RadioButton(_("Demander pour chaque nouvelle cible"), value=True, id="accord-ask")
                yield RadioButton(_("Tout accepter de ce pilote (machines qui sont toutes à vous)"), id="accord-all")
            yield Static("", id="distributed-result")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Relier la sélection"), id="link", variant="primary", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Délier la sélection"), id="unlink", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#distributed-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(" ", _("Machine"), _("État"), _("Liaison"), _("Accord"))
        self._load()

    def _busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()

    def action_back(self) -> None:
        if not self._working:
            self.dismiss(self._changed)  # type: ignore[arg-type]

    def scan_changed(self) -> bool:
        """Une machine vient d'etre scannee (bandeau de scan) : la liste est relue, rien n'est rescanne."""
        if self._working:
            return False
        self._load()
        return True

    def _load(self) -> None:
        """Pilote lu, machines relues dans le dernier scan : jamais rescannees a l'ouverture (decision 2026-11-26 ;
        apres une liaison, les machines concernees viennent d'etre rescannees par la liaison elle-meme)."""
        self._busy(_("Lecture d'omega-stress sur cette machine et sur le réseau…"))

        def collect() -> None:
            try:
                pilot = self._tools.pilot()
                rows = [(entry, link) for entry in self._remote.parc.load() if not entry.local
                        for link in entry.links
                        if link.kind is LinkKind.DISTRIBUTED_LOAD]
            except Exception as exc:  # noqa: BLE001 - jamais planter l'interface
                self.app.call_from_thread(self._show, None, [], str(exc) or type(exc).__name__)
                return
            self.app.call_from_thread(self._show, pilot, rows, "")

        self.run_worker(collect, thread=True, group="distributed", exclusive=True)

    def _show(self, pilot: PilotState | None, rows: list[tuple[MachineEntry, Link]], error: str) -> None:
        self._busy(None)
        self._pilot = pilot
        self._rows = rows
        if self._preselect:
            self._chosen |= {(entry.label, link.root) for entry, link in rows
                             if entry.label == self._preselect and selectable(link)}
            self._preselect = ""
        self._chosen &= {(entry.label, link.root) for entry, link in rows if selectable(link)}
        status = self.query_one("#distributed-status", Static)
        if error:
            status.update(_("Erreur : {message}").format(message=error))
        elif pilot is None:
            status.update(_("omega-stress n'est pas installé sur cette machine (ou trop ancien) : elle ne peut pas "
                            "piloter. Installez omega-stress 2.0.0 ou plus, puis revenez ici."))
        elif not rows:
            status.update(_("Aucune machine du réseau n'a omega-stress 2.0.0 ou plus. Scannez vos machines "
                            "(Scanner), installez-le sur celles qui doivent aider, puis revenez ici."))
        else:
            status.update(_("{count} machine(s) du réseau peuvent aider.").format(count=len(rows)))
        self._fill()

    def _fill(self) -> None:
        styles = theme_styles(self.app)
        table = self.query_one("#distributed-table", DataTable)
        table.clear()
        several = {label for label in (entry.label for entry, _link in self._rows)
                   if sum(1 for other, _l in self._rows if other.label == label) > 1}
        for entry, link in self._rows:
            key = (entry.label, link.root)
            mark = SELECTED_MARK if key in self._chosen else UNSELECTED_MARK if selectable(link) else Text("   ")
            name = f"{entry.label} — {link.root}" if entry.label in several else entry.label
            table.add_row(mark, name, state_text(link.state, styles), link_words(link), accord_of(link),
                          key=f"{entry.label}\n{link.root}")
        usable = self._pilot is not None and not self._working
        self.query_one("#link", Button).disabled = not (usable and self._chosen)
        self.query_one("#unlink", Button).disabled = not (usable and self._chosen)

    def action_choose_row(self) -> None:
        table = self.query_one("#distributed-table", DataTable)
        if not self._rows or table.cursor_row is None or table.cursor_row >= len(self._rows):
            return
        entry, link = self._rows[table.cursor_row]
        if not selectable(link):
            self.app.notify(_("{machine} : omega-stress trop ancien ou illisible — mettez-le à jour depuis le "
                              "Registre.").format(machine=entry.label))
            return
        self._chosen ^= {(entry.label, link.root)}
        self._fill()

    def on_data_table_row_selected(self, _event: DataTable.RowSelected) -> None:
        self.action_choose_row()

    # ---- actions ----
    def _helpers(self) -> list[Helper]:
        pilot = self._pilot
        helpers = []
        for entry, link in self._rows:
            if (entry.label, link.root) in self._chosen:
                known = pilot.machine_for(entry.target, link.root) if pilot else ""
                helpers.append(Helper(entry.label, entry.target, link.root, known))
        return helpers

    def _accord(self) -> Accord:
        return Accord.ALL if self.query_one("#accord-all", RadioButton).value else Accord.ASK

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "link" and self._pilot is not None:
            steps = plan(self._pilot, self._helpers(), self._accord(), self._tools.runner)
            self._confirm(steps, _("Relier la charge distribuée"))
        elif event.button.id == "unlink" and self._pilot is not None:
            self._start_unlink()

    def _confirm(self, steps: tuple[LinkStep, ...], title: str) -> None:
        lines = [_("Commandes lancées, dans cet ordre :")] + [f"  {shown(step)}" for step in steps]
        if needs_root(steps):
            lines.append("")
            lines.append(_("Le pare-feu de cette machine s'ouvre au port d'omega-stress pour votre réseau "
                           "local : un mot de passe sudo sera demandé, une seule fois."))
        self.app.push_screen(ConfirmScreen(title=title, text="\n".join(lines), yes=_("Lancer"), no=_("Annuler")),
                             lambda yes: self._run(steps) if yes else None)

    def _run(self, steps: tuple[LinkStep, ...]) -> None:
        privileged = None
        if needs_root(steps):
            with suspended(self.app, SUDO_MESSAGE):
                authenticated = self._sudo.authenticate()  # type: ignore[attr-defined]
            if not authenticated:
                self.app.notify(_("Authentification sudo refusée ou annulée : rien n'a été lancé."),
                                severity="error")
                return
            privileged = self._sudo
        self._working = True
        self._fill()
        self._busy(_("Liaison en cours…"))

        def work() -> None:
            try:
                results = run_plan(steps, self._tools, privileged)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001
                results = [StepResult("", "", False, str(exc) or type(exc).__name__)]
            self.app.call_from_thread(self._done, results)

        self.run_worker(work, thread=True, group="distributed", exclusive=True)

    def _start_unlink(self) -> None:
        pilot = self._pilot
        helpers = self._helpers()
        if pilot is None or not helpers:
            return
        self._working = True
        self._fill()
        self._busy(_("Retrait de la liaison…"))

        def work() -> None:
            results: list[StepResult] = []
            for helper in helpers:
                results += unlink(pilot, helper, self._tools)
            self.app.call_from_thread(self._done, results)

        self.run_worker(work, thread=True, group="distributed", exclusive=True)

    def _done(self, results: list[StepResult]) -> None:
        getattr(self.app, "local_changed", lambda: None)()  # scan relu : cette machine a change
        self._working = False
        failed = [r for r in results if not r.ok]
        text = Text()
        if failed:
            text.append(_("{count} étape(s) en échec :").format(count=len(failed)) + "\n", style="bold")
            for result in failed:
                text.append(f"  {result.helper or _('cette machine')} : {result.detail or '?'}\n")
        else:
            text.append(_("Fait."), style="bold")
            text.append("\n")
        rules = [line for result in results for line in result.firewall]
        if rules:
            text.append(_("Pare-feu de cette machine (règles posées) :") + "\n", style="bold")
            for line in rules:
                text.append(f"  {line}\n")
        self.query_one("#distributed-result", Static).update(text)
        self._chosen.clear()
        self._changed = True
        self._load()


def where_label(step: LinkStep) -> str:
    return {StepWhere.LOCAL: _("cette machine"), StepWhere.REMOTE: step.target,
            StepWhere.ROOT: _("cette machine (root)")}[step.where]


__all__ = ["DistributedLoadScreen", "LinkState"]
