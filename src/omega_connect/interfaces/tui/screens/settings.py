# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Reglages (menu Maintenance, touche s ; lot F) : theme de l'interface et des exports, dossiers des exports et des
captures d'ecran (par defaut `var/exports/` et `var/screenshots/` du projet, comme les autres outils), et purge de
ces deux dossiers, apres confirmation, hors du fil de l'interface, jamais avec sudo."""
from __future__ import annotations

import contextlib
from pathlib import Path

from omega_lib.theme.policies import EXPORT_PALETTES, TUI_THEMES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Input, Select, Static

from omega_connect.application.settings import (
    KEY_EXPORT_THEME,
    KEY_EXPORTS_DIR,
    KEY_SCREENSHOTS_DIR,
    ClearResult,
    SettingsTools,
    UnsafeDirectoryError,
)
from omega_connect.interfaces.tui.language_setting import LanguageSetting
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.screens.confirm import ConfirmScreen
from omega_connect.shared.i18n import _


class SettingsScreen(OmegaScreen):
    def __init__(self, *, tools: SettingsTools) -> None:
        super().__init__()
        self._tools = tools

    def compose(self) -> ComposeResult:
        tools = self._tools
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RÉGLAGES"), classes="omega-title")
            yield Static(_("Enregistrés dans var/settings.json, appliqués tout de suite."), classes="omega-hint")

            yield LanguageSetting(self._tools.store)

            yield Static(_("Thème de l'interface"), classes="omega-subtitle")
            yield Select([(name, name) for name in TUI_THEMES], value=self.app.theme, allow_blank=False,
                         id="theme-select")
            yield Static(_("Thème des exports (rapport HTML, aide exportée)"), classes="omega-subtitle")
            yield Select([(name, name) for name in EXPORT_PALETTES], value=tools.export_theme(), allow_blank=False,
                         id="export-theme-select")

            yield Static(_("Dossier des exports"), classes="omega-subtitle")
            yield Static(_("Par défaut : {path}. Laissez vide pour revenir au dossier par défaut.").format(
                path=tools.shown(tools.default_exports)), classes="omega-hint")
            yield Input(value=tools.shown(tools.exports_dir()), id="exports-dir")
            yield Static(_("Dossier des captures d'écran"), classes="omega-subtitle")
            yield Static(_("Par défaut : {path}. Capture : Ctrl+P → « Capture d'écran ».").format(
                path=tools.shown(tools.default_screenshots)), classes="omega-hint")
            yield Input(value=tools.shown(tools.screenshots_dir()), id="screenshots-dir")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Enregistrer les dossiers"), id="save-dirs", variant="primary")

            yield Static(_("Maintenance des dossiers"), classes="omega-subtitle")
            yield Static(_("Supprime définitivement le contenu du dossier configuré ; le dossier reste."),
                         classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Vider le dossier des exports"), id="clear-exports", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Vider le dossier des captures"), id="clear-screenshots", variant="error")
        with Horizontal(classes="omega-actions omega-fixed-actions"), Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    def on_select_changed(self, event: Select.Changed) -> None:
        value = str(event.value)
        if event.select.id == "theme-select" and value in TUI_THEMES and value != self.app.theme:
            self.app.theme = value  # enregistre par l'application (watch_theme)
        elif event.select.id == "export-theme-select" and value in EXPORT_PALETTES:
            self._tools.store.set(KEY_EXPORT_THEME, value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "save-dirs":
            self._save_directories()
        elif button == "clear-exports":
            self._confirm_clear(_("des exports"), self._tools.exports_dir())
        elif button == "clear-screenshots":
            self._confirm_clear(_("des captures"), self._tools.screenshots_dir())
        elif button == "back":
            self.action_back()

    def _save_directories(self) -> None:
        saved = []
        for key, widget in ((KEY_EXPORTS_DIR, "#exports-dir"), (KEY_SCREENSHOTS_DIR, "#screenshots-dir")):
            field = self.query_one(widget, Input)
            path = self._tools.set_directory(key, field.value)
            if path is None:
                self.app.notify(_("Chemin à donner en entier (commençant par / ou ~) : {path}").format(
                    path=field.value), severity="error")
                return
            field.value = self._tools.shown(path)
            saved.append(field.value)
        self.app.notify(_("Dossiers enregistrés : {paths}").format(paths=" ; ".join(saved)))

    def _confirm_clear(self, label: str, directory: Path) -> None:
        self.app.push_screen(ConfirmScreen(
            title=_("VIDER LE DOSSIER {label} ?").format(label=label.upper()),
            text=_("Supprime définitivement tout le contenu de {directory}. Le dossier reste.").format(
                directory=self._tools.shown(directory)),
            yes=_("Vider"), no=_("Annuler")), lambda confirmed: self._clear(confirmed, directory))

    def _clear(self, confirmed: bool | None, directory: Path) -> None:
        if not confirmed:
            return
        tools = self._tools

        def work() -> None:
            try:
                result = tools.clear(directory)
            except UnsafeDirectoryError as error:
                self.app.call_from_thread(self.app.notify, _("Refusé — {path} : {reason}").format(
                    path=error.path, reason=error.reason), severity="error")
                return
            except OSError as error:
                self.app.call_from_thread(self.app.notify, str(error), severity="error")
                return
            self.app.call_from_thread(self._cleared, result)

        self.run_worker(work, thread=True, group="clear", exclusive=True)

    def _cleared(self, result: ClearResult) -> None:
        with contextlib.suppress(NoMatches):
            message = _("{count} élément(s) supprimé(s) dans {path}.").format(count=result.removed,
                                                                             path=result.directory)
            if result.failed:
                message += " " + _("Non supprimés : {items}").format(items=", ".join(result.failed))
            self.app.notify(message, severity="warning" if result.failed else "information")

