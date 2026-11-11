# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Réparer (menu Maintenance) : LA LISTE DE TOUT CE QUI NE VA PAS, sur toutes les machines, et on choisit (retour de
l'auteur, 2026-11-11 : « dans Réparer il devrait y avoir la liste de tout ce qui ne va pas et là on choisit de
réparer » ; « on tourne en boucle »).

Une ligne par problème : machine, problème, état (mêmes mots que Liaisons et le Registre), qui le corrige.
« Réparer la ligne choisie » ouvre le plan de cette machine (cette machine : plan local ; machine du réseau : plan
calculé sur elle, lancé depuis ici), « Tout réparer » enchaîne les machines une à une. Au retour, la liste est
recalculée : ce qui est réparé disparaît."""
from __future__ import annotations

import contextlib
from collections.abc import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_connect.application.remote_actions import scan_remote
from omega_connect.application.remote_sync import RemoteSyncTools
from omega_connect.domain.fleet import AppState, registry_rows
from omega_connect.domain.problems import Problem, ProblemKind, problems
from omega_connect.domain.remote import parse_target
from omega_connect.domain.updates import Purpose
from omega_connect.interfaces.cli.enroll_view import STATE_LABELS as APP_STATE_LABELS
from omega_connect.interfaces.cli.verification_view import LINK_LABELS, STATE_LABELS
from omega_connect.interfaces.tui.presentation import check_lines
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.screens.dashboard import VerifyNow
from omega_connect.interfaces.tui.screens.link_detail import LinkDetailScreen
from omega_connect.interfaces.tui.screens.remote_machine import RemoteMachineScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.states import theme_styles
from omega_connect.interfaces.tui.widgets.tables import WideTable
from omega_connect.ports.fleet import ParcStore
from omega_connect.ports.zone import ZoneInspector
from omega_connect.shared.i18n import N_, _

WHO_LABELS = {
    "tool": N_("l'outil, depuis ici"),
    "manual-remote": N_("commande lancée sur la machine, depuis ici"),
    "manual-local": N_("à la main (commande à copier)"),
    "update": N_("Mettre à jour l'application, depuis ici"),
    "reinstall": N_("Réinstaller l'application, depuis ici"),
    "update-local": N_("à la main (README de l'outil)"),
    "scan": N_("Scanner : rescanner la machine"),
    "none": N_("aucune correction connue (voir le détail)"),
}


def who(problem: Problem) -> str:
    if problem.kind is ProblemKind.UNREACHABLE:
        return "scan"
    if problem.kind is ProblemKind.UPDATE:
        if problem.local:
            return "update-local"
        return "reinstall" if problem.row is not None and problem.row.state is AppState.INCOMPLETE else "update"
    if not problem.fixable:
        return "none"
    if problem.by_tool:
        return "tool"
    return "manual-local" if problem.local else "manual-remote"


def actionable(problem: Problem) -> bool:
    return who(problem) in ("tool", "manual-remote", "update", "reinstall", "manual-local")


class RepairScreen(OmegaScreen):
    def __init__(self, *, verify: VerifyNow, inspector: ZoneInspector, machine: str,
                 local_repair: Callable[[], Screen[None] | None], parc: ParcStore | None = None,
                 remote_sync: RemoteSyncTools | None = None) -> None:
        super().__init__()
        self._verify = verify
        self._inspector = inspector
        self._machine = machine
        self._local_repair = local_repair
        self._parc = parc
        self._remote_sync = remote_sync
        self._problems: tuple[Problem, ...] = ()
        self._queue: list[Problem] = []
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel omega-fill"):
            yield Static(_("RÉPARER"), classes="omega-title")
            yield Static(_("Tout ce qui ne va pas, sur toutes les machines. Choisissez une ligne puis « Réparer la "
                           "ligne choisie », ou « Tout réparer » : le plan de la machine s'affiche, rien n'est lancé "
                           "avant. Machine du réseau : réparée depuis ici, son mot de passe sudo demandé une fois."),
                         classes="omega-hint")
            yield Busy(id="busy")
            yield Static("", id="problems-status")
            yield WideTable(id="problems")
            yield Static("", id="problem-detail")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Réparer la ligne choisie"), id="repair-one", variant="primary", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Détail"), id="detail", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Tout réparer"), id="repair-all", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Analyser de nouveau"), id="again")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#problems", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Machine"), _("Problème"), _("État"), _("Qui corrige"))
        self._load()

    # ---- liste ----
    def _busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()

    def _load(self) -> None:
        """Cette machine verifiee, PUIS les machines du reseau rescannees : la liste dit l'etat reel (retour de
        l'auteur, 2026-11-11 : une liste faite d'apres un ancien scan proposait de reparer ce qui ne l'etait plus —
        « rien a reparer », et on tournait en boucle)."""
        if self._loading:
            return
        self._loading = True
        self._busy(_("Recherche de tout ce qui ne va pas : vérification de cette machine…"))
        remote = self._remote_sync.remote if self._remote_sync is not None else None

        def collect() -> None:
            try:
                report = self._verify()
                rows = registry_rows(report, self._inspector.inspect(elevated=False), self._machine)
                network = self._parc.load() if self._parc is not None else ()
                machines = [entry for entry in network if not entry.local]
                for index, entry in enumerate(machines, start=1):
                    target = parse_target(entry.target)
                    if remote is None or target is None:
                        continue
                    self.app.call_from_thread(self._busy, _("Rescan des machines du réseau ({index}/{count}) : "
                                                            "{machine}…").format(index=index, count=len(machines),
                                                                                 machine=entry.label))
                    with contextlib.suppress(Exception):
                        scan_remote(target, remote)
                network = self._parc.load() if self._parc is not None else ()
                found = problems(self._machine, report.links, rows, network)
            except Exception as exc:  # noqa: BLE001 - jamais planter l'interface
                self.app.call_from_thread(self._error, str(exc) or type(exc).__name__)
                return
            self.app.call_from_thread(self._show, report, found)

        self.run_worker(collect, thread=True, group="problems", exclusive=True)

    def _error(self, message: str) -> None:
        self._loading = False
        self._busy(None)
        with contextlib.suppress(NoMatches):
            self.query_one("#problems-status", Static).update(_("Erreur : {message}").format(message=message))

    def _show(self, report: object, found: tuple[Problem, ...]) -> None:
        self._loading = False
        self._busy(None)
        self.app.report = report  # type: ignore[attr-defined]
        self._problems = found
        styles = theme_styles(self.app)
        with contextlib.suppress(NoMatches):
            machines = len({problem.machine for problem in found})
            status = Text()
            if found:
                status.append(_("{count} problème(s) sur {machines} machine(s).").format(count=len(found),
                                                                                        machines=machines),
                              style=f"bold {styles.get('warning', 'yellow')}")
            else:
                status.append(_("Rien à réparer : tout est OK sur toutes les machines."),
                              style=f"bold {styles.get('success', 'green')}")
            self.query_one("#problems-status", Static).update(status)
            table = self.query_one("#problems", DataTable)
            cursor = table.cursor_row
            table.clear()
            for problem in found:
                table.add_row(problem.machine, self._subject(problem), self._state(problem, styles),
                              _(WHO_LABELS[who(problem)]))
            if found:
                table.move_cursor(row=min(max(cursor, 0), len(found) - 1))
            table.refresh(layout=True)
            self.query_one("#repair-all", Button).disabled = not any(actionable(problem) for problem in found)
            self._describe()

    @staticmethod
    def _subject(problem: Problem) -> str:
        if problem.kind is ProblemKind.UNREACHABLE:
            return _("la machine ne répond plus")
        if problem.row is not None:
            return f"{problem.row.tool} {problem.row.version or '?'}"
        link = problem.link
        assert link is not None
        return _(LINK_LABELS[link.kind])  # l'instance et le chemin sont dans le detail, sous le tableau

    @staticmethod
    def _state(problem: Problem, styles: dict[str, str]) -> Text:
        if problem.kind is ProblemKind.UNREACHABLE:
            return Text("✕ " + _("Injoignable"), style=f"bold {styles.get('error', 'red')}")
        if problem.row is not None:
            label = _(APP_STATE_LABELS[problem.row.state])
            mark = "◇" if problem.row.state is AppState.INCOMPLETE else "◌"
            return Text(f"{mark} {label}", style="bold dim")
        assert problem.link is not None
        key = "error" if problem.blocking else "warning"
        return Text("▲ " + _(STATE_LABELS[problem.link.state]).capitalize(), style=f"bold {styles.get(key, key)}")

    def _current(self) -> Problem | None:
        try:
            index = self.query_one("#problems", DataTable).cursor_row
        except NoMatches:
            return None
        return self._problems[index] if 0 <= index < len(self._problems) else None

    def _describe(self) -> None:
        problem = self._current()
        detail: Text | str = ""
        if problem is not None and problem.link is not None:
            detail = check_lines(problem.link, theme_styles(self.app), with_ok=False)
        elif problem is not None and problem.row is not None:
            detail = Text(problem.row.root)
        with contextlib.suppress(NoMatches):
            self.query_one("#problem-detail", Static).update(detail)
            self.query_one("#repair-one", Button).disabled = problem is None or not actionable(problem)
            self.query_one("#detail", Button).disabled = problem is None or problem.link is None

    def on_data_table_row_highlighted(self, _event: DataTable.RowHighlighted) -> None:
        self._describe()

    def on_data_table_row_selected(self, _event: DataTable.RowSelected) -> None:
        problem = self._current()
        if problem is not None and actionable(problem):
            self._open(problem, self._after)

    # ---- actions ----
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "repair-one":
            problem = self._current()
            if problem is not None:
                self._open(problem, self._after)
        elif button == "detail":
            problem = self._current()
            if problem is not None and problem.link is not None:
                self.app.push_screen(LinkDetailScreen(link=problem.link, verified_at=None))
        elif button == "repair-all":
            self._repair_all()
        elif button == "again":
            self._load()
        elif button == "back":
            self.action_back()

    def _open(self, problem: Problem, done: Callable[[object], None]) -> None:
        if problem.local:
            screen = self._local_repair()
            if screen is not None:
                self.app.push_screen(screen, done)
            return
        target = parse_target(problem.target)
        if target is None or self._remote_sync is None:
            self.app.notify(_("{machine} : rescannez-la d'abord (Scanner).").format(machine=problem.machine))
            return
        purpose = Purpose.UPDATE if problem.kind is ProblemKind.UPDATE else Purpose.REPAIR
        self.app.push_screen(RemoteMachineScreen(target=target, tools=self._remote_sync, purpose=purpose), done)

    def _repair_all(self) -> None:
        """Une etape par machine et par geste : mettre a jour d'abord, puis reparer."""
        seen: set[tuple[str, ProblemKind]] = set()
        self._queue = []
        for problem in self._problems:
            key = (problem.machine, ProblemKind.REPAIR if problem.kind is ProblemKind.REPAIR else problem.kind)
            if actionable(problem) and key not in seen:
                seen.add(key)
                self._queue.append(problem)
        self._next()

    def _next(self, _result: object = None) -> None:
        if not self._queue:
            self._load()
            return
        self._open(self._queue.pop(0), self._next)

    def _after(self, _result: object) -> None:
        self._load()

