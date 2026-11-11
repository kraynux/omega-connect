# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Dashboard (vue d'ensemble en cadres, refonte 2026-11-11) et Liaisons sous le pilote Textual, avec un rapport
fabrique : jamais la vraie machine."""
from __future__ import annotations

import threading

from omega_lib.synchro.models import InstallToken, ReadStatus
from omega_lib.terminal.models import RenderProfile
from omega_lib.theme.policies import TUI_THEMES
from textual.widgets import DataTable, Static

from omega_connect.domain.detection import (
    DetectedInstallation,
    DetectionReport,
    NoteKind,
    ScanNote,
    Source,
)
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind, VerificationReport
from omega_connect.interfaces.cli.main import DetectRequest, run
from omega_connect.interfaces.tui.app import OmegaConnectApp
from omega_connect.interfaces.tui.screens.dashboard import LinksScreen
from omega_connect.interfaces.tui.screens.home import HomeScreen
from omega_connect.interfaces.tui.screens.link_detail import LinkDetailScreen
from omega_connect.interfaces.tui.screens.overview import OverviewScreen
from omega_connect.interfaces.tui.screens.quit_confirm import QuitConfirmScreen
from omega_connect.interfaces.tui.screens.splash import SplashScreen

ROOT = "/home/k/omega-serv"
TOKEN = InstallToken("omega-serv", "2.6.1", "a" * 32, "m", ROOT, "k", "2026-11-10T00:00:00Z", "2026-11-10T00:00:00Z")


def _report(links: int = 0) -> VerificationReport:
    detection = DetectionReport(
        home="/home/k",
        installations=(DetectedInstallation(ROOT, "omega-serv", (Source.HOME,), "k", ReadStatus.OK, TOKEN),),
        scan_notes=(ScanNote(NoteKind.NETWORK_MOUNT_SKIPPED, "/home/k/Reseau/nas"),),
    )
    base = [
        Link(LinkKind.SERV_LOGS, "omega-serv", ROOT, (
            Check(CheckCode.JAIL_LOG_MISSING, CheckStatus.FAILURE, f"{ROOT}/var/log/waf-alerts.log",
                  "omega-serv-waf-block", fix="/home/k/omega-jail/omega-jail.sh --apply --update"),
            Check(CheckCode.JAIL_LOG_OK, CheckStatus.OK, f"{ROOT}/var/log/access.log", "k:omega-serv 0664"),
        )),
        Link(LinkKind.BLOCKLIST, "omega-serv", ROOT, (
            Check(CheckCode.BLOCKLIST_OK, CheckStatus.OK, f"{ROOT}/var/lib/waf/blocklist.json", "k:omega-serv 0660"),)),
        Link(LinkKind.TOKENS, "", "", (Check(CheckCode.TOKEN_OK, CheckStatus.OK, ROOT, "aaaaaaaa"),)),
    ]
    base += [Link(LinkKind.FAIL2BAN_FILES, "", "", (Check(CheckCode.FILES_OK, CheckStatus.OK, str(i)),))
             for i in range(links)]
    return VerificationReport(detection, tuple(base))


def _app(verify=None) -> OmegaConnectApp:
    return OmegaConnectApp(verify=verify or _report, version="0.1.0", render_profile=RenderProfile.COMPLETE,
                           refresh_seconds=0)


async def _ready(app: OmegaConnectApp, pilot, entry: str = "dashboard"):
    await pilot.pause()
    assert isinstance(app.screen, SplashScreen)
    await pilot.press("space")
    await pilot.pause()
    assert isinstance(app.screen, HomeScreen)
    await pilot.click(f"#menu-{entry}")
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()
    await pilot.pause()
    screen = app.screen
    assert isinstance(screen, OverviewScreen if entry == "dashboard" else LinksScreen)
    return screen


def _card(screen, name: str) -> str:
    return str(screen.query_one(f"#card-{name}", Static).render())


async def test_dashboard_is_an_overview_in_separate_frames_without_actions():
    """« Un dashboard c'est que du visuel » : cadres de compteurs, liaisons par type, cette machine / reseau, tops ;
    Actualiser et Retour seulement, aucun tableau ni detail technique."""
    app = _app()
    async with app.run_test(size=(140, 50)) as pilot:
        screen = await _ready(app, pilot)
        assert "1 au total" in _card(screen, "machines")
        assert "▲ 1 À réparer" in _card(screen, "applications")
        links = _card(screen, "links")
        assert "✔ 2 OK" in links and "✘ 1 à réparer (bloquant)" in links
        assert "Journaux d'omega-serv → jails fail2ban" in _card(screen, "kinds")
        assert "Cette machine" in _card(screen, "sides") and "Réseau" in _card(screen, "sides")
        assert "1. ✘ Journaux d'omega-serv → jails fail2ban" in _card(screen, "top-links")
        assert "Aucune machine du réseau" in _card(screen, "top-oldest")
        assert screen.query_one("#card-top-links", Static).border_title == "TOP 5 · LIAISONS À RÉPARER"
        assert {button.id for button in screen.query("Button")} == {"refresh", "back"}
        assert not list(screen.query(DataTable))
        page = " ".join(str(widget.render()) for widget in screen.query(Static))
        for word in ("à venir", "refonte", "contrôle", "constat", "Provenance", "OUTILS ET INSTANCES"):
            assert word not in page, word


async def test_dashboard_tops_shrink_to_three_on_a_small_screen():
    app = _app()
    async with app.run_test(size=(90, 28)) as pilot:  # menu plus haut que l'ecran : ouverture directe
        await pilot.pause()
        app.push_screen(app.screen_for("dashboard"))
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OverviewScreen)
        assert screen.query_one("#card-top-machines", Static).border_title.startswith("TOP 3 ·")
        assert screen.query_one("#overview-counters").styles.grid_size_columns == 2


async def test_links_screen_shows_the_links_and_the_highlighted_one():
    app = _app()
    async with app.run_test(size=(140, 50)) as pilot:
        screen = await _ready(app, pilot, "links")
        links = screen.query_one("#links-table", DataTable)
        assert links.row_count == 3
        assert "1 à réparer (bloquant)" in str(screen.query_one("#summary", Static).render())
        detail = str(screen.query_one("#link-detail", Static).render())
        assert "omega-jail.sh --apply --update" in detail and "1 contrôle(s) conforme(s)" in detail


async def test_link_detail_lists_every_check_then_back():
    app = _app()
    async with app.run_test(size=(140, 50)) as pilot:
        screen = await _ready(app, pilot, "links")
        screen.query_one("#links-table", DataTable).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, LinkDetailScreen)
        checks = str(app.screen.query_one("#link-checks", Static).render())
        assert "access.log présent" in checks and "waf-alerts.log absent" in checks
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, LinksScreen)


async def test_verification_runs_off_the_interface_thread_and_errors_are_shown():
    seen: list[bool] = []

    def failing() -> VerificationReport:
        seen.append(threading.current_thread() is threading.main_thread())
        raise OSError("disque absent")

    app = _app(failing)
    async with app.run_test(size=(140, 50)) as pilot:
        screen = await _ready(app, pilot)
        assert seen == [False]
        assert "disque absent" in str(screen.query_one("#status", Static).render())
        assert not screen.query_one("#refresh").disabled


async def test_escape_goes_back_to_the_menu_then_asks_before_quitting():
    app = _app()
    async with app.run_test(size=(140, 50)) as pilot:
        await _ready(app, pilot)
        first = app.theme
        await pilot.press("t")
        assert app.theme != first and app.theme in TUI_THEMES
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, QuitConfirmScreen)
        await pilot.click("#cancel")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)


async def test_tables_never_collapse_to_their_header_in_any_theme():
    """Piege connu de la suite : une DataTable en `1fr` dans un panneau qui defile tombe a une ligne."""
    app = _app(lambda: _report(links=20))
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await _ready(app, pilot, "links")
        for name in TUI_THEMES:
            app.theme = name
            await pilot.pause()
            assert screen.query_one("#links-table", DataTable).size.height >= 10


def test_no_command_opens_the_dashboard():
    calls: list[DetectRequest] = []

    def dashboard(request: DetectRequest) -> int:
        calls.append(request)
        return 0

    assert run([], lambda request: _report().detection, None, dashboard) == 0
    assert run(["tableau", "--chemin", "/srv/x"], lambda request: _report().detection, None, dashboard) == 0
    assert [call.manual_paths for call in calls] == [[], ["/srv/x"]] and all(call.with_sheets for call in calls)
