# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lot F : Reglages (theme, dossiers des exports et des captures, purge) et capture d'ecran. Jamais le vrai var/ :
tout se passe dans un dossier de test."""
from __future__ import annotations

from pathlib import Path

import pytest
from omega_lib.terminal.models import RenderProfile
from omega_lib.theme.policies import TUI_THEMES
from textual.widgets import Button, Input, Select
from zone_fakes import AT, FakeSystem, _detection

from omega_connect.application.settings import (
    KEY_EXPORTS_DIR,
    KEY_THEME,
    SettingsTools,
    UnsafeDirectoryError,
)
from omega_connect.application.zone_actions import ZoneTools
from omega_connect.domain.links import VerificationReport
from omega_connect.infrastructure.settings.directories import check_clearable, clear_directory
from omega_connect.infrastructure.settings.json_store import JsonSettingsStore
from omega_connect.interfaces.tui.app import OmegaConnectApp
from omega_connect.interfaces.tui.screens.confirm import ConfirmScreen
from omega_connect.interfaces.tui.screens.home import HomeScreen
from omega_connect.interfaces.tui.screens.settings import SettingsScreen


def _tools(tmp_path: Path) -> SettingsTools:
    var = tmp_path / "projet" / "var"
    return SettingsTools(JsonSettingsStore(var / "settings.json"), var / "exports", var / "screenshots",
                         lambda directory: clear_directory(directory, tmp_path / "projet"), tmp_path / "projet")


def test_defaults_are_the_project_var_folders(tmp_path):
    tools = _tools(tmp_path)
    assert tools.exports_dir() == tmp_path / "projet" / "var" / "exports"
    assert tools.screenshots_dir() == tmp_path / "projet" / "var" / "screenshots"
    # Retour utilisateur 2026-11-11 : affiche « var/exports/ », jamais le chemin complet de la machine
    assert tools.shown(tools.exports_dir()) == "var/exports/"
    assert tools.shown(tools.screenshots_dir()) == "var/screenshots/"
    assert str(tmp_path) not in tools.shown(tools.exports_dir())
    assert tools.set_directory(KEY_EXPORTS_DIR, "var/autres/") == tmp_path / "projet" / "var" / "autres"
    assert tools.store.get(KEY_EXPORTS_DIR) == "var/autres"  # enregistre relatif : suit le dossier du logiciel
    assert tools.set_directory(KEY_EXPORTS_DIR, "var/exports") == tools.default_exports
    assert tools.store.get(KEY_EXPORTS_DIR) == ""
    without_root = SettingsTools(tools.store, tools.default_exports, tools.default_screenshots, tools.clear)
    assert without_root.set_directory(KEY_EXPORTS_DIR, "relatif/non") is None  # sans dossier connu : chemin complet
    assert tools.set_directory(KEY_EXPORTS_DIR, str(tmp_path / "ailleurs")) == tmp_path / "ailleurs"
    assert tools.exports_dir() == tmp_path / "ailleurs"
    assert tools.set_directory(KEY_EXPORTS_DIR, "") == tools.default_exports  # vide : retour au defaut
    assert tools.theme() and tools.export_theme()


def test_purge_empties_only_the_configured_folder_and_never_follows_links(tmp_path):
    folder = tmp_path / "exports"
    (folder / "sous").mkdir(parents=True)
    (folder / "rapport.html").write_text("x", encoding="utf-8")
    (folder / "sous" / "f").write_text("x", encoding="utf-8")
    outside = tmp_path / "precieux"
    outside.mkdir()
    (outside / "garde.txt").write_text("x", encoding="utf-8")
    (folder / "lien").symlink_to(outside)
    result = clear_directory(folder, tmp_path / "projet")
    assert result.removed == 3 and not result.failed
    assert folder.is_dir() and not list(folder.iterdir())
    assert (outside / "garde.txt").exists()  # la cible du lien n'est jamais touchee


@pytest.mark.parametrize("path", ["/", "/etc", "/home", "/usr/local", "/var/log"])
def test_purge_refuses_system_folders(tmp_path, path):
    with pytest.raises(UnsafeDirectoryError):
        check_clearable(Path(path), tmp_path / "projet")


def test_purge_refuses_home_and_the_project_itself(tmp_path):
    project = tmp_path / "projet"
    project.mkdir()
    with pytest.raises(UnsafeDirectoryError):
        check_clearable(Path.home(), project)
    with pytest.raises(UnsafeDirectoryError):
        check_clearable(project, project)
    with pytest.raises(UnsafeDirectoryError):
        check_clearable(tmp_path, project)  # parent du projet


def _app(tmp_path: Path, tools: SettingsTools) -> OmegaConnectApp:
    system = FakeSystem(tmp_path / "machine")
    detection = _detection()

    def verify() -> VerificationReport:
        return VerificationReport(detection, ())

    zone = ZoneTools(inspector=system, runner=system, subject=None, now=lambda: AT,  # type: ignore[arg-type]
                     interactive=lambda: False)
    return OmegaConnectApp(verify=verify, version="0.1.0", render_profile=RenderProfile.COMPLETE, refresh_seconds=0,
                           zone=zone, detect=lambda: detection, splash=False, settings=tools)


async def test_settings_screen_saves_theme_folders_and_purges_after_confirmation(tmp_path):
    tools = _tools(tmp_path)
    app = _app(tmp_path, tools)
    exports = tools.exports_dir()
    exports.mkdir(parents=True)
    (exports / "ancien.json").write_text("{}", encoding="utf-8")
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        await pilot.press("s")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)
        other = next(name for name in TUI_THEMES if name != app.theme)
        screen.query_one("#theme-select", Select).value = other
        await pilot.pause()
        assert app.theme == other and tools.store.get(KEY_THEME) == other  # enregistre
        screen.query_one("#screenshots-dir", Input).value = str(tmp_path / "captures")
        screen.query_one("#save-dirs", Button).press()
        await pilot.pause()
        assert tools.screenshots_dir() == tmp_path / "captures"
        screen.query_one("#clear-exports", Button).press()  # bas de l'ecran, sous la notification
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        assert (exports / "ancien.json").exists()  # rien avant l'accord
        await pilot.click("#confirm")
        for _round in range(5):
            await app.workers.wait_for_complete()
            await pilot.pause()
        assert not (exports / "ancien.json").exists() and exports.is_dir()
        app.save_screen_capture()
        await pilot.pause()
        assert list((tmp_path / "captures").glob("*.svg"))  # capture Textual dans le dossier configure
        assert not screen.query_one("#back", Button).disabled


def test_settings_store_survives_a_damaged_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{abime", encoding="utf-8")
    store = JsonSettingsStore(path)
    assert store.all() == {}
    store.set("theme", "x")
    assert JsonSettingsStore(path).get("theme") == "x"

