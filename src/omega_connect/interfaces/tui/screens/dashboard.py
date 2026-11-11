# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Liaisons (spec etape 3, §4 ; lots C et D ; refonte 2026-11-11) : ce qui est relie ou pas, sur toutes les
machines, avec son etat, en lecture seule. Le Dashboard est un ecran a part (screens/overview.py).

La verification (detection + `verifier`) tourne dans un fil, a l'ouverture puis a intervalle regulier tant que
l'ecran est ouvert : aucun demon. Le dernier rapport est garde par l'application : chaque vue l'affiche tout de
suite, puis le rafraichit. Aucune action ici ne modifie la machine : les corrections sont affichees, jamais
lancees."""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_connect.domain.links import Link, VerificationReport
from omega_connect.interfaces.tui.presentation import check_lines, link_row, summary_text
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.screens.link_detail import LinkDetailScreen
from omega_connect.interfaces.tui.views import LINKS, ViewSpec, view_links
from omega_connect.interfaces.tui.widgets.tables import WideTable
from omega_connect.shared.i18n import _

VerifyNow = Callable[[], VerificationReport]


class LinksScreen(OmegaScreen):
    BINDINGS = [*OmegaScreen.BINDINGS, Binding("v", "verify", _("Vérifier maintenant"), show=False)]

    def __init__(self, *, verify: VerifyNow, refresh_seconds: float, view: ViewSpec = LINKS,
                 network_links: Callable[[], tuple[Link, ...]] | None = None) -> None:
        """`network_links` : liaisons des machines distantes (registre du parc, lot R2), provenance « Réseau »."""
        super().__init__()
        self._network_links = network_links or (lambda: ())
        self._verify = verify
        self._refresh_seconds = refresh_seconds
        self._view = view
        self._verifying = False
        self.report: VerificationReport | None = None
        self.verified_at: datetime | None = None
        self._links: tuple[Link, ...] = ()

    def compose(self) -> ComposeResult:
        yield Header()
        # Le tableau remplit l'ecran et defile seul, titre et detail restent visibles (retour de l'auteur, 2026-11-10).
        with Vertical(classes="omega-panel omega-fill"):
            yield Static(_(self._view.title), classes="omega-title")
            yield Static(_(self._view.hint), classes="omega-hint")
            yield Static("", id="status", classes="omega-hint")
            yield Static("", id="summary")
            yield Static(_("LIENS"), classes="omega-subtitle", id="links-title")
            yield WideTable(id="links-table")
            yield Static("", id="link-detail")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Vérifier maintenant"), id="verify", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Détail du lien"), id="detail", disabled=True)

            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        links = self.query_one("#links-table", DataTable)
        links.cursor_type = "row"
        links.add_columns(_("État"), _("Provenance"), _("Lien"), _("Instance"), _("Constat"))
        holder = self.app
        previous = getattr(holder, "report", None)
        if isinstance(previous, VerificationReport):
            self._apply(previous, getattr(holder, "verified_at", None), keep_running=True)
        self.action_verify()
        if self._refresh_seconds > 0:
            self.set_interval(self._refresh_seconds, self.action_verify)

    # ---- verification dans un fil -------------------------------------------

    def action_verify(self) -> None:
        if self._verifying:
            return
        self._verifying = True
        self._set_busy(True)
        self.run_worker(self._collect, thread=True, group="verify", exclusive=True)

    def _collect(self) -> None:
        try:
            report = self._verify()
        except Exception as exc:  # noqa: BLE001 - jamais planter l'interface pour une verification
            self.app.call_from_thread(self._show_error, str(exc) or type(exc).__name__)
            return
        self.app.call_from_thread(self._apply, report, datetime.now().astimezone())

    def _set_busy(self, busy: bool) -> None:
        try:
            self.query_one("#verify", Button).disabled = busy
            if busy:
                self.query_one("#status", Static).update(_("Vérification en cours…"))
        except NoMatches:
            pass  # ecran deja ferme

    def _show_error(self, message: str) -> None:
        self._verifying = False
        self._set_busy(False)
        with contextlib.suppress(NoMatches):
            self.query_one("#status", Static).update(_("Erreur : {message}").format(message=message))

    def _styles(self) -> dict[str, str]:
        variables = self.app.get_css_variables()
        return {key: variables.get(key, fallback) or fallback for key, fallback in (
            ("success", "green"), ("warning", "yellow"), ("error", "red"), ("secondary", "cyan"))}

    def _apply(self, report: VerificationReport, verified_at: datetime | None, *, keep_running: bool = False) -> None:
        if not keep_running:
            self._verifying = False
            self._set_busy(False)
            app = self.app
            app.report = report  # type: ignore[attr-defined]
            app.verified_at = verified_at  # type: ignore[attr-defined]
        self.report = report
        self.verified_at = verified_at
        self._links = view_links(VerificationReport(report.detection, report.links + self._network_links()),
                                 self._view)
        try:
            links = self.query_one("#links-table", DataTable)
        except NoMatches:
            return
        styles = self._styles()
        if verified_at is not None and not keep_running:
            status = _("Vérifié à {time}.").format(time=verified_at.strftime("%H:%M:%S"))
            if self._refresh_seconds > 0:
                status += " " + _("Nouvelle vérification toutes les {minutes} min tant que cet écran est "
                                  "ouvert.").format(minutes=max(1, round(self._refresh_seconds / 60)))
            self.query_one("#status", Static).update(status)
        summary_source = VerificationReport(report.detection, self._links)
        self.query_one("#summary", Static).update(summary_text(summary_source, styles))

        cursor = links.cursor_row
        links.clear()
        for link in self._links:
            links.add_row(*link_row(link, styles))
        if self._links:
            links.move_cursor(row=min(max(cursor, 0), len(self._links) - 1))
        self._show_detail(links.cursor_row)


    # ---- lien surligne ------------------------------------------------------

    def _selected(self, row: int | None = None) -> Link | None:
        if not self._links:
            return None
        index = self.query_one("#links-table", DataTable).cursor_row if row is None else row
        return self._links[index] if 0 <= index < len(self._links) else None

    def _show_detail(self, row: int) -> None:
        link = self._selected(row)
        self.query_one("#detail", Button).disabled = link is None

        self.query_one("#link-detail", Static).update(
            check_lines(link, self._styles(), with_ok=False) if link is not None else "")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "links-table":
            self._show_detail(event.cursor_row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "links-table":
            self._open_detail(event.cursor_row)

    def _open_detail(self, row: int | None = None) -> None:
        link = self._selected(row)
        if link is not None:
            self.app.push_screen(LinkDetailScreen(link=link, verified_at=self.verified_at),
                                 lambda _result: self.action_verify())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "verify":
            self.action_verify()
        elif event.button.id == "detail":
            self._open_detail()

        elif event.button.id == "back":
            self.action_back()
