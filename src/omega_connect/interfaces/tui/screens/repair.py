# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Réparer (menu Maintenance) : LA LISTE DE TOUT CE QUI NE VA PAS, sur toutes les machines, et on choisit (retour de
l'auteur, 2026-11-11 : « dans Réparer il devrait y avoir la liste de tout ce qui ne va pas et là on choisit de
réparer » ; « on tourne en boucle »).

Une ligne par problème : machine, problème, état (mêmes mots que Liaisons et le Registre), qui le corrige.
« Réparer la ligne choisie » ouvre le plan de cette machine (cette machine : plan local ; machine du réseau : plan
calculé sur elle, lancé depuis ici). « Tout réparer » (retour d'utilisation 2026-11-26 : « on reste en boucle infinie
sur les réparations ») : UN récapitulatif machine par machine, UNE confirmation, puis les machines une à une dans le
terminal (un mot de passe par machine), sans écran entre deux, et un bilan. Une réparation qui échoue ne repart pas
en boucle : la ligne dit « Échec » et sort de « Tout réparer » jusqu'à ce qu'elle soit relancée seule. Après une
réparation, seule la machine touchée est rescannée, en arrière-plan."""
from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_connect.application.remote_sync import RemoteSyncTools
from omega_connect.domain.fleet import AppState, registry_rows
from omega_connect.domain.links import LinkKind
from omega_connect.domain.problems import Problem, ProblemKind, problems
from omega_connect.domain.remote import parse_target
from omega_connect.domain.updates import Purpose
from omega_connect.interfaces.cli.enroll_view import STATE_LABELS as APP_STATE_LABELS
from omega_connect.interfaces.cli.verification_view import LINK_LABELS, STATE_LABELS
from omega_connect.interfaces.tui.presentation import check_lines
from omega_connect.interfaces.tui.screens._base import OmegaScreen, suspended
from omega_connect.interfaces.tui.screens.confirm import ConfirmScreen
from omega_connect.interfaces.tui.screens.dashboard import VerifyNow
from omega_connect.interfaces.tui.screens.link_detail import LinkDetailScreen
from omega_connect.interfaces.tui.screens.remote_machine import RemoteMachineScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.list_filter import ListFilter
from omega_connect.interfaces.tui.widgets.scan_banner import ScanBanner
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
    "scan": N_("la rescanner, depuis ici"),
    "none": N_("aucune correction connue (voir le détail)"),
    "distributed": N_("Charge distribuée : relier de nouveau, ou ouvrir le pare-feu"),
    "updater": N_("Updater : mise à jour depuis ici"),
}


def who(problem: Problem) -> str:
    if problem.kind is ProblemKind.UNREACHABLE:
        return "scan"
    if problem.link is not None and problem.link.kind is LinkKind.DISTRIBUTED_LOAD:
        return "distributed"
    if problem.kind is ProblemKind.UPDATE:
        return "updater"  # seul l'Updater met a jour (decision de l'auteur, 2026-11-22)
    if not problem.fixable:
        return "none"
    if problem.by_tool:
        return "tool"
    return "manual-local" if problem.local else "manual-remote"


def problem_key(problem: Problem) -> tuple[str, str, str, str]:
    """Identite d'une ligne d'un scan a l'autre (suivi des echecs)."""
    if problem.link is not None:
        return (problem.machine, problem.kind.value, problem.link.kind.value, problem.link.instance)
    return (problem.machine, problem.kind.value, "", problem.row.root if problem.row is not None else "")


ALL_AT_ONCE = ("tool", "manual-remote", "manual-local")
"""Ce que « Tout réparer » enchaîne dans le terminal ; les mises a jour (Updater), la charge distribuee (son ecran)
et les machines injoignables (a rescanner) restent a part, nommees dans le recapitulatif."""


def actionable(problem: Problem) -> bool:
    return who(problem) in ("tool", "manual-remote", "update", "reinstall", "manual-local", "distributed",
                            "updater", "scan")


class RepairScreen(OmegaScreen):
    def __init__(self, *, verify: VerifyNow, inspector: ZoneInspector, machine: str,
                 local_repair: Callable[[], Screen[None] | None], parc: ParcStore | None = None,
                 remote_sync: RemoteSyncTools | None = None,
                 distributed: Callable[..., Screen[None] | None] | None = None,
                 updater: Callable[..., Screen[None] | None] | None = None,
                 runner: Callable[[list[str]], int] | None = None) -> None:
        super().__init__()
        self._runner = runner
        self._failed: set[tuple[str, str, str, str]] = set()
        """Lignes dont la derniere reparation a echoue (cette session) : jamais relancees par « Tout réparer »."""
        self._distributed = distributed
        self._updater = updater
        self._verify = verify
        self._inspector = inspector
        self._machine = machine
        self._local_repair = local_repair
        self._parc = parc
        self._remote_sync = remote_sync
        self._problems: tuple[Problem, ...] = ()
        self._shown: list[int] = []
        """Ligne affichee -> indice dans `_problems` (recherche et filtre : seul l'affichage change)."""
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel omega-fill"):
            yield Static(_("RÉPARER"), classes="omega-title")
            yield Static(_("Tout ce qui ne va pas, sur toutes les machines. Choisissez une ligne puis « Réparer la "
                           "ligne choisie », ou « Tout réparer » : le plan de la machine s'affiche, rien n'est lancé "
                           "avant. Machine du réseau : réparée depuis ici, son mot de passe sudo demandé une fois."),
                         classes="omega-hint")
            yield ScanBanner()
            yield Busy(id="busy")
            yield Static("", id="problems-status")
            yield ListFilter([(_("À réparer"), "repair"), (_("À mettre à jour"), "update"),
                              (_("Injoignable"), "unreachable"), (_("Échec de la réparation"), "failed")])
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

    def scan_changed(self) -> bool:
        """Une machine vient d'etre scannee (bandeau de scan) : la liste est relue, rien n'est rescanne."""
        if self._loading:
            return False
        self._load()
        return True

    def _load(self) -> None:
        """Le dernier scan relu, jamais un nouveau scan (decision 2026-11-26). Apres une reparation, la machine
        touchee est rescannee seule : la liste ne propose pas ce qui vient d'etre repare."""
        if self._loading:
            return
        self._loading = True
        self._busy(_("Lecture du dernier scan…"))

        def collect() -> None:
            try:
                report = self._verify()
                rows = registry_rows(report, self._inspector.inspect(elevated=False), self._machine)
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
            self._failed &= {problem_key(problem) for problem in found}  # ce qui a disparu est repare
            chooser = self.query_one(ListFilter)
            self._shown = [index for index, problem in enumerate(found) if chooser.matches(
                (problem.machine, self._subject(problem), problem.row.root if problem.row else ""),
                self._filter_state(problem))]
            for problem in (found[index] for index in self._shown):
                state = self._state(problem, styles)
                if problem_key(problem) in self._failed:
                    state = Text("✕ " + _("Échec de la réparation"), style=f"bold {styles.get('error', 'red')}")
                table.add_row(problem.machine, self._subject(problem), state, _(WHO_LABELS[who(problem)]))
            if self._shown:
                table.move_cursor(row=min(max(cursor, 0), len(self._shown) - 1))
            table.refresh(layout=True)
            self.query_one("#repair-all", Button).disabled = not self._all_at_once()
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
        return self._problems[self._shown[index]] if 0 <= index < len(self._shown) else None

    def _filter_state(self, problem: Problem) -> str:
        if problem_key(problem) in self._failed:
            return "failed"
        return {ProblemKind.UNREACHABLE: "unreachable", ProblemKind.UPDATE: "update"}.get(problem.kind, "repair")

    def on_list_filter_changed(self, _event: ListFilter.Changed) -> None:
        if not self._loading:
            self._show(getattr(self.app, "report", None), self._problems)

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
        elif button == "back":
            self.action_back()

    def _open(self, problem: Problem, done: Callable[[object], None]) -> None:
        if who(problem) == "scan":
            # Machine injoignable : « Réparer » = la rescanner, seule, en arriere-plan (2026-11-26)
            scan = getattr(self.app, "scan_machine", None)
            if scan is not None and problem.target:
                scan(problem.target, problem.machine)
                self.app.notify(_("Scan de {machine} lancé.").format(machine=problem.machine))
            return
        if who(problem) == "updater":
            # Une seule facon de mettre a jour (decision de l'auteur, 2026-11-22) : l'Updater, l'application cochee
            screen = self._updater(problem.machine) if self._updater is not None else None
            if screen is not None:
                self.app.push_screen(screen, done)
            return
        if who(problem) == "distributed":
            screen = self._distributed(problem.machine) if self._distributed is not None else None
            if screen is not None:
                # Retour sans rien changer : ni rescan, ni rechargement
                self.app.push_screen(screen, lambda changed: done(changed) if changed else None)
            return
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

    # ---- « Tout réparer » : un recapitulatif, une confirmation, le terminal ----
    def _all_at_once(self) -> list[Problem]:
        return [problem for problem in self._problems
                if who(problem) in ALL_AT_ONCE and problem_key(problem) not in self._failed
                and (problem.local or parse_target(problem.target) is not None)]

    def _repair_all(self) -> None:
        chosen = self._all_at_once()
        if not chosen or self._runner is None:
            return
        machines: dict[str, list[Problem]] = {}
        for problem in chosen:
            machines.setdefault(problem.machine, []).append(problem)
        lines = [_("Machines réparées une à une dans le terminal (mot de passe sudo demandé une fois par machine) :")]
        for name, items in machines.items():
            mark = _(" (cette machine)") if items[0].local else ""
            lines.append("  · " + _("{machine}{mark} : {count} correction(s)").format(
                machine=name, mark=mark, count=len(items)))
        left = [problem for problem in self._problems if problem not in chosen]
        if left:
            lines += ["", _("Hors « Tout réparer » :")]
            counts: dict[str, int] = {}
            for problem in left:
                reason = _("échec précédent : « Réparer la ligne choisie »") \
                    if problem_key(problem) in self._failed else _(WHO_LABELS[who(problem)])
                counts[reason] = counts.get(reason, 0) + 1
            lines += [f"  · {count} × {reason}" for reason, count in counts.items()]
        self.app.push_screen(ConfirmScreen(title=_("Tout réparer"), text="\n".join(lines), yes=_("Lancer"),
                                           no=_("Annuler")),
                             lambda yes: self._run_all(machines) if yes else None)

    def _run_all(self, machines: dict[str, list[Problem]]) -> None:
        runner = self._runner
        assert runner is not None
        program = [sys.executable, "-m", "omega_connect"]
        results: list[tuple[str, int, list[Problem]]] = []
        with suspended(self.app, _("Tout réparer : les machines une à une, dans ce terminal.")):
            for name, items in machines.items():
                print("\n" + "=" * 70 + "\n" + _("== {machine}").format(machine=name) + "\n" + "=" * 70, flush=True)
                argv = [*program, "reparer", "--oui"] if items[0].local else \
                    [*program, "reparer", "--machine", items[0].target, "--oui"]
                results.append((name, runner(argv), items))
            print("\n" + _("Bilan :"), flush=True)
            for name, code, _items in results:
                print(("  ✓ " if code == 0 else "  ✕ ") + (name if code == 0 else _("{machine} : échec (code {code})")
                                                           .format(machine=name, code=code)), flush=True)
            with contextlib.suppress(EOFError, OSError):
                input("\n" + _("Appuyez sur Entrée pour revenir à omega-connect…"))
        failed = [name for name, code, _items in results if code != 0]
        for _name, code, items in results:
            if code != 0:
                self._failed |= {problem_key(problem) for problem in items}
            first = items[0]
            if first.local:
                getattr(self.app, "local_changed", lambda: None)()
            else:
                getattr(self.app, "scan_machine", lambda *_args: None)(first.target, first.machine)
        self.app.notify(_("Tout réparer : {ok} machine(s) réparée(s), {failed} en échec ({names}).").format(
            ok=len(results) - len(failed), failed=len(failed), names=", ".join(failed))
            if failed else _("Tout réparer : {ok} machine(s) réparée(s) ; rescan en cours.").format(ok=len(results)),
            severity="warning" if failed else "information")
        self._load()

    def _after(self, _result: object) -> None:
        self._load()  # le dernier scan relu ; la machine touchee est rescannee seule, en arriere-plan

