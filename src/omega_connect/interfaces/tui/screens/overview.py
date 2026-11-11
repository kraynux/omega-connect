# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Dashboard (refonte, demande de l'auteur 2026-11-11) : une vue d'ensemble faite de cadres separes, comme un tableau
de bord web. « Un dashboard c'est que du visuel » : aucune action sur les machines ; Actualiser et Retour seulement.

En haut : Machines, Applications, Liaisons, Espace partage. Au milieu : Liaisons par type, Cette machine / Reseau.
En bas : un top 5 par categorie (top 3 sur un ecran etroit). Les cadres se rangent en 4, 2 ou 1 colonne(s) selon la
largeur ; rien n'est tasse, l'ecran defile.

Cette machine est verifiee dans un fil, a l'ouverture puis a intervalle regulier tant que l'ecran est ouvert ; les
machines du reseau sont celles du registre du parc (leur dernier scan) : aucune connexion depuis cet ecran."""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.events import Resize
from textual.widgets import Button, Footer, Header, Static

from omega_connect.domain.fleet import registry_rows, space_status
from omega_connect.domain.links import VerificationReport
from omega_connect.domain.overview import Overview, build_overview
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.zone import ZoneFacts
from omega_connect.interfaces.tui import overview_view as view
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.widgets.states import theme_styles
from omega_connect.shared.i18n import N_, _

VerifyNow = Callable[[], VerificationReport]
HINT = N_("Vue d'ensemble de vos machines et de vos applications. Rien n'est modifié depuis cet écran. "
          "Pour corriger : menu Réparer.")
COUNTERS = ("machines", "applications", "links", "space")
MIDDLE = ("kinds", "sides")
TOPS = ("top-machines", "top-links", "top-versions", "top-oldest")


def columns(width: int, wide: int, *, four: int = 120, two: int = 64) -> int:
    """Colonnes d'une rangee de cadres selon la largeur du terminal."""
    if width >= four:
        return wide
    return min(2, wide) if width >= two else 1


class OverviewScreen(OmegaScreen):
    BINDINGS = [*OmegaScreen.BINDINGS, Binding("v", "refresh_overview", _("Actualiser"), show=False)]

    def __init__(self, *, verify: VerifyNow, refresh_seconds: float, machine: str = "",
                 inspect: Callable[[], ZoneFacts] | None = None,
                 network: Callable[[], tuple[MachineEntry, ...]] | None = None) -> None:
        super().__init__()
        self._verify = verify
        self._refresh_seconds = refresh_seconds
        self._machine = machine or _("cette machine")
        self._inspect = inspect
        self._network = network or (lambda: ())
        self._busy = False
        self.overview: Overview | None = None
        self.verified_at: datetime | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel", id="overview-panel"):
            yield Static(_("DASHBOARD"), classes="omega-title")
            yield Static(_(HINT), classes="omega-hint")
            yield Static("", id="status", classes="omega-hint")
            for grid_id, cards in (("overview-counters", COUNTERS), ("overview-middle", MIDDLE),
                                   ("overview-tops", TOPS)):
                with Grid(id=grid_id, classes="overview-grid"):
                    for card in cards:
                        yield Static("", id=f"card-{card}", classes="overview-card")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Actualiser"), id="refresh", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        for card, title in view.TITLES.items():
            self.query_one(f"#card-{card}", Static).border_title = _(title)
        self._layout(self.app.size.width)
        # Pas d'affichage du dernier rapport garde par l'application : sans l'espace partage relu, les applications
        # reliees apparaitraient « Inscrites » le temps de la verification.
        self.action_refresh_overview()
        if self._refresh_seconds > 0:
            self.set_interval(self._refresh_seconds, self.action_refresh_overview)

    def on_resize(self, event: Resize) -> None:
        self._layout(event.size.width)
        self.call_after_refresh(self._paint_cards)  # largeur des cadres connue apres la mise en page

    def _layout(self, width: int) -> None:
        with contextlib.suppress(NoMatches):
            self.query_one("#overview-counters", Grid).styles.grid_size_columns = columns(width, 4)
            self.query_one("#overview-middle", Grid).styles.grid_size_columns = columns(width, 2, four=120, two=120)
            self.query_one("#overview-tops", Grid).styles.grid_size_columns = columns(width, 4, four=150)

    # ---- verification dans un fil -------------------------------------------

    def action_refresh_overview(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_busy(True)
        self.run_worker(self._collect, thread=True, group="overview", exclusive=True)

    def _collect(self) -> None:
        try:
            report = self._verify()
            facts = self._inspect() if self._inspect is not None else None
        except Exception as exc:  # noqa: BLE001 - jamais planter l'interface pour une verification
            self.app.call_from_thread(self._show_error, str(exc) or type(exc).__name__)
            return
        self.app.call_from_thread(self._apply, report, facts, datetime.now().astimezone())

    def _set_busy(self, busy: bool) -> None:
        with contextlib.suppress(NoMatches):
            self.query_one("#refresh", Button).disabled = busy
            if busy:
                self.query_one("#status", Static).update(_("Vérification en cours…"))

    def _show_error(self, message: str) -> None:
        self._busy = False
        self._set_busy(False)
        with contextlib.suppress(NoMatches):
            self.query_one("#status", Static).update(_("Erreur : {message}").format(message=message))

    def _apply(self, report: VerificationReport, facts: ZoneFacts | None, verified_at: datetime) -> None:
        self._busy = False
        self._set_busy(False)
        self.app.report = report  # type: ignore[attr-defined]
        self.app.verified_at = verified_at  # type: ignore[attr-defined]
        self.verified_at = verified_at
        self.overview = build_overview(machine=self._machine, rows=registry_rows(report, facts, self._machine),
                                       links=report.links, space=space_status(report), verified_at=verified_at,
                                       network=self._network())
        status = _("Cette machine vérifiée à {time} ; machines du réseau : leur dernier scan.").format(
            time=verified_at.strftime("%H:%M:%S"))
        if self._refresh_seconds > 0:
            status += " " + _("Nouvelle vérification toutes les {minutes} min tant que cet écran est "
                              "ouvert.").format(minutes=max(1, round(self._refresh_seconds / 60)))
        with contextlib.suppress(NoMatches):
            self.query_one("#status", Static).update(status)
        self._paint_cards()
        self.call_after_refresh(self._paint_cards)  # barres a la largeur reelle du cadre

    def _paint_cards(self) -> None:
        overview = self.overview
        if overview is None:
            return
        styles = theme_styles(self.app)
        size = view.top_size(self.app.size.width, self.app.size.height)
        now = datetime.now().astimezone()
        cards = {
            "machines": view.machines_card(overview, styles),
            "applications": view.applications_card(overview, styles),
            "links": view.links_card(overview, styles),
            "space": view.space_card(overview, styles),
            "kinds": view.kinds_card(overview, styles, self._content_width("kinds")),
            "sides": view.sides_card(overview, styles),
            "top-machines": view.top_machines_card(overview, size, styles),
            "top-links": view.top_links_card(overview, size, styles),
            "top-versions": view.top_versions_card(overview, size, styles),
            "top-oldest": view.top_oldest_card(overview, size, styles, now),
        }
        with contextlib.suppress(NoMatches):
            for card, text in cards.items():
                widget = self.query_one(f"#card-{card}", Static)
                widget.update(text)
                if card in view.TOP_TITLES:
                    widget.border_title = _(view.TOP_TITLES[card]).format(count=size)

    def _content_width(self, card: str) -> int:
        try:
            return self.query_one(f"#card-{card}", Static).content_size.width
        except NoMatches:
            return 0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh":
            self.action_refresh_overview()
        elif event.button.id == "back":
            self.action_back()
