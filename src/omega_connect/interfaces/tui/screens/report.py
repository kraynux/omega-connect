# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Rapport (menu Maintenance) : export complet — outils, jetons, fiches, liens et tous leurs controles, zone et
registre — en texte, JSON ou HTML (theme d'export d'omega-lib), dans var/exports/. Lecture seule, sans root : le
rapport est refait a l'ouverture, dans un fil."""
from __future__ import annotations

import contextlib

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Select, Static

from omega_connect.application.report import FullReport, ReportTools
from omega_connect.interfaces.cli.main import render_report
from omega_connect.interfaces.cli.report_view import export_name, render_report_text
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.shared.i18n import _

EXPORT_BUTTONS = {"export-txt": "texte", "export-json": "json", "export-html": "html"}


class ReportScreen(OmegaScreen):
    def __init__(self, *, tools: ReportTools) -> None:
        super().__init__()
        self._tools = tools
        self.report: FullReport | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RAPPORT"), classes="omega-title")
            yield Static(_("Un document complet, établi à l'instant (les machines du réseau sont rescannées "
                           "avant) : bilan, ce qu'il reste à faire, registre, machines du réseau, liaisons de chaque "
                           "machine, espace partagé. Enregistré dans le dossier des exports."), classes="omega-hint")
            yield Static("", id="status", classes="omega-hint")
            yield Busy(id="busy")
            yield Static(_("THÈME DE LA PAGE HTML"), classes="omega-subtitle")
            settings = getattr(self.app, "settings", None)
            theme = settings.export_theme() if settings is not None else DEFAULT_EXPORT_THEME
            yield Select([(name, name) for name in EXPORT_PALETTES], value=theme,
                         allow_blank=False, id="export-theme")
            yield Static(_("APERÇU"), classes="omega-subtitle", id="preview-title")
            yield Static("", id="report-preview")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            for button_id, label in (("export-txt", _("Exporter TXT")), ("export-json", _("Exporter JSON")),
                                     ("export-html", _("Exporter HTML"))):
                with Container(classes="omega-btn-frame"):
                    yield Button(label, id=button_id, disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Actualiser"), id="refresh", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._set_ready(False)
        self.query_one("#status", Static).update("")
        self.query_one(Busy).show(_("Génération du rapport en cours (détection, vérification, zone)…"))
        self.run_worker(self._collect, thread=True, group="report", exclusive=True)

    def _collect(self) -> None:
        try:
            report = self._tools.collect()
        except Exception as exc:  # noqa: BLE001 - jamais planter l'interface pour un rapport
            self.app.call_from_thread(self._error, str(exc) or type(exc).__name__)
            return
        self.app.call_from_thread(self._show, report)

    def _set_ready(self, ready: bool) -> None:
        with contextlib.suppress(NoMatches):
            for button_id in (*EXPORT_BUTTONS, "refresh"):
                self.query_one(f"#{button_id}", Button).disabled = not ready

    def _error(self, message: str) -> None:
        with contextlib.suppress(NoMatches):
            self.query_one(Busy).hide()
            self.query_one("#status", Static).update(_("Erreur : {message}").format(message=message))
            self.query_one("#refresh", Button).disabled = False

    def _show(self, report: FullReport) -> None:
        self.report = report
        with contextlib.suppress(NoMatches):
            self.query_one(Busy).hide()
            self.query_one("#report-preview", Static).update(render_report_text(report))
            self.query_one("#status", Static).update(_("Rapport prêt."))
            self._set_ready(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id or ""
        if button in EXPORT_BUTTONS and self.report is not None:
            theme = str(self.query_one("#export-theme", Select).value)
            content, extension = render_report(self.report, EXPORT_BUTTONS[button], theme)
            try:
                path = self._tools.writer.save(export_name(self.report, extension), content)
            except OSError as exc:
                self.app.notify(_("Export impossible : {error}").format(error=exc.strerror or exc), severity="error")
                return
            self.query_one("#status", Static).update(_("Rapport enregistré : {path}").format(path=path))
            self.app.notify(_("Rapport enregistré : {path}").format(path=path))
        elif button == "refresh":
            self._refresh()
        elif button == "back":
            self.action_back()
