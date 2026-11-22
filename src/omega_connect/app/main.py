# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Racine de composition : cable les sources de detection reelles derriere la ligne de commande."""
from __future__ import annotations

import os
import socket
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omega_lib.declaration.models import MIRROR_SITE_URL
from omega_lib.infrastructure.declaration import build_contact_support
from omega_lib.infrastructure.synchro.files import zone_dir
from omega_lib.synchro.policies import format_utc

from omega_connect import __version__
from omega_connect.application.detect_installations import detect_installations
from omega_connect.application.distributed_actions import DistributedTools
from omega_connect.application.remote_actions import RemoteTools, rescan_network, scan_remote
from omega_connect.application.remote_sync import RemoteSyncTools
from omega_connect.application.repair_actions import RepairTools
from omega_connect.application.report import FullReport, ReportTools, collect_report
from omega_connect.application.scan_cache import ScanCache, request_rescan
from omega_connect.application.settings import SettingsTools
from omega_connect.application.updater import UpdaterTools
from omega_connect.application.verify_links import verify_links
from omega_connect.application.zone_actions import ZoneTools
from omega_connect.core.constants import (
    DASHBOARD_REFRESH_SECONDS,
    FAIL2BAN_DIR,
    HOME_SCAN_DEPTH,
    OPENRC_INIT_DIR,
    RUNIT_SERVICE_DIR,
    SRV_DIR,
    SRV_SCAN_DEPTH,
    SYSTEMD_UNIT_DIR,
)
from omega_connect.domain.detection import DetectionReport, Source
from omega_connect.domain.distributed_load import STRESS_TOOL
from omega_connect.domain.links import VerificationReport
from omega_connect.domain.remote import parse_target
from omega_connect.infrastructure.clipboard.system import copy_text
from omega_connect.infrastructure.detection.filesystem_scan import (
    MOUNTS_FILE,
    FilesystemScanLocator,
    ManualLocator,
)
from omega_connect.infrastructure.detection.home import target_home
from omega_connect.infrastructure.detection.layout import FilesystemInspector
from omega_connect.infrastructure.detection.serv_registry import ServRegistryLocator
from omega_connect.infrastructure.detection.service_units import ServiceUnitsLocator
from omega_connect.infrastructure.detection.sheet_fetcher import SubprocessSheetFetcher
from omega_connect.infrastructure.exports.writer import FileExportWriter
from omega_connect.infrastructure.fleet.sqlite_store import SqliteParcStore
from omega_connect.infrastructure.remote.payload import build_payload
from omega_connect.infrastructure.remote.ssh import SshRemoteSession
from omega_connect.infrastructure.remote.suggestions import LocalSuggestions
from omega_connect.infrastructure.repair.tool_runner import ToolCommandRunner
from omega_connect.infrastructure.session.zone_group import relaunch_with_zone_group
from omega_connect.infrastructure.settings.directories import clear_directory
from omega_connect.infrastructure.settings.json_store import JsonSettingsStore
from omega_connect.infrastructure.stress.pilot import LocalPilot
from omega_connect.infrastructure.stress.runner import StressRunner, local_address_towards
from omega_connect.infrastructure.updates.github_releases import GithubReleases
from omega_connect.infrastructure.updates.local_agent import run_in_terminal
from omega_connect.infrastructure.updates.site_releases import ChainedReleases, SiteReleases
from omega_connect.infrastructure.verification.files import Fail2banFilesReader, StatFileProbe
from omega_connect.infrastructure.zone.inspector import SystemZoneInspector
from omega_connect.infrastructure.zone.system import SessionSubject, SudoRunner, running_as_root
from omega_connect.interfaces.cli.main import (
    DashboardFunction,
    DetectFunction,
    DetectRequest,
    ReportFunction,
    VerifyFunction,
    main_with,
)
from omega_connect.ports.detection import CandidateLocator
from omega_connect.ports.fleet import ParcStore


def build_detect(environ: Mapping[str, str] | None = None, *, home: Path | None = None,
                 systemd_dir: str | None = None, openrc_dir: str | None = None, runit_dir: str | None = None,
                 srv_dir: str = SRV_DIR, mounts_file: str | None = None) -> DetectFunction:
    """Fonction de detection ; chaque chemin systeme est remplacable (tests : jamais le vrai /etc)."""
    def detect(request: DetectRequest) -> DetectionReport:
        examined_home = home or target_home(environ)
        mounts = mounts_file or MOUNTS_FILE
        units = ServiceUnitsLocator(systemd_dir or SYSTEMD_UNIT_DIR, openrc_dir or OPENRC_INIT_DIR,
                                    runit_dir or RUNIT_SERVICE_DIR)
        locators: list[CandidateLocator] = [
            ServRegistryLocator(examined_home),
            units,
            FilesystemScanLocator(examined_home, HOME_SCAN_DEPTH, Source.HOME, mounts_file=mounts),
            FilesystemScanLocator(Path(srv_dir), SRV_SCAN_DEPTH, Source.SRV, mounts_file=mounts),
            ManualLocator(request.manual_paths),
        ]
        fetcher = SubprocessSheetFetcher() if request.with_sheets else None
        return detect_installations(str(examined_home), locators, FilesystemInspector(), fetcher)

    return detect


def connect_command() -> str:
    """Commande d'omega-connect a proposer dans les corrections : son lanceur s'il existe, sinon son nom."""
    launcher = Path(__file__).resolve().parents[3] / "omega-connect.sh"
    return str(launcher) if launcher.is_file() else "omega-connect"


VAR_DIR_ENV = "OMEGA_CONNECT_VAR_DIR"
"""Remplace `<omega-connect>/var` (tests : jamais le vrai var/)."""


def var_dir(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    return Path(env.get(VAR_DIR_ENV) or Path(__file__).resolve().parents[3] / "var")


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_settings(environ: Mapping[str, str] | None = None) -> SettingsTools:
    """Reglages dans var/settings.json ; exports et captures par defaut dans var/exports/ et var/screenshots/."""
    var = var_dir(environ)
    root = project_root()
    return SettingsTools(JsonSettingsStore(var / "settings.json"), var / "exports", var / "screenshots",
                         lambda directory: clear_directory(directory, root), root)


def build_report(verify: VerifyFunction, zone: ZoneTools, parc: ParcStore | None = None,
                 remote: RemoteTools | None = None, *, rescan: bool = True) -> ReportFunction:
    """Ligne de commande : les machines du reseau sont rescannees avant (lecture seule), un rapport dit l'etat
    reel (retour de l'auteur, 2026-11-11). Interface (`rescan=False`, 2026-11-22) : le dernier scan est relu,
    « Relancer le scan » rescanne d'abord."""
    def report(request: DetectRequest) -> FullReport:
        if remote is not None and rescan:
            rescan_network(remote)
        return collect_report(verify(request), zone.inspector, version=__version__, now=zone.now(),
                              machine=machine_name(), parc=parc)

    return report


def build_zone(environ: Mapping[str, str] | None = None) -> ZoneTools:
    """Zone neutre (lot D) : `OMEGA_SYNCHRO_DIR` la remplace (tests : jamais le vrai /var/lib)."""
    runner = SudoRunner()
    return ZoneTools(
        inspector=SystemZoneInspector(str(zone_dir(environ)), runner.capture),
        runner=runner,
        subject=SessionSubject(environ),
        now=lambda: format_utc(datetime.now(timezone.utc)),
        as_root=running_as_root(),
        command=connect_command(),
    )


def machine_name() -> str:
    """Nom court de cette machine (comme celui que renvoie le scanner distant)."""
    return (socket.gethostname() or "local").split(".")[0][:64]


def build_repair(environ: Mapping[str, str] | None = None) -> RepairTools:
    """`reparer` (lot E) : commandes des outils proprietaires (lanceur verifie, sudo -n ou compte proprietaire)."""
    subject = SessionSubject(environ)
    return RepairTools(runner=ToolCommandRunner(), user=lambda: subject.subject().user, as_root=running_as_root())


def build_verify(detect: DetectFunction, *, fail2ban_dir: str = FAIL2BAN_DIR,
                 zone: ZoneTools | None = None) -> VerifyFunction:
    """Fonction de verification ; `fail2ban_dir` remplacable (tests : jamais le vrai /etc/fail2ban)."""
    command = connect_command()

    def verify(request: DetectRequest) -> VerificationReport:
        return verify_links(detect(request), Fail2banFilesReader(fail2ban_dir), StatFileProbe(),
                            zone.inspector if zone else None, zone.subject if zone else None, command)

    return verify


def install_language(settings: SettingsTools | None, terminal_family: object) -> None:
    """Langue de l'interface, AVANT d'importer la TUI (comme le reste de la suite) ; jamais pour la ligne de
    commande, qui reste en francais."""
    from omega_lib.i18n.terminal_cell_widths import align_spacing_marks_with_terminal

    from omega_connect.shared.i18n import LANGUAGE

    if settings is not None:
        LANGUAGE.install(settings_store=settings.store, environ=os.environ,
                         terminal_family=terminal_family)  # type: ignore[arg-type]
    align_spacing_marks_with_terminal()


def run_with_text_direction(app: Any) -> None:
    """Arabe : omega-connect ordonne lui-meme le texte droite-a-gauche ; le terminal passe en mode bidi explicite
    le temps de l'interface (repris d'omega-log)."""
    from omega_lib.i18n.policies import text_direction
    from omega_lib.i18n.terminal_bidi import ENTER_EXPLICIT_MODE, LEAVE_EXPLICIT_MODE, install_visual_reordering

    from omega_connect.shared.i18n import STATE

    if text_direction(STATE.language.code) != "rtl" or not install_visual_reordering():
        app.run()
        return
    sys.stdout.write(ENTER_EXPLICIT_MODE)
    sys.stdout.flush()
    try:
        app.run()
    finally:
        sys.stdout.write(LEAVE_EXPLICIT_MODE)
        sys.stdout.flush()


def restart_for_language(code: str) -> None:  # pragma: no cover - remplace le processus
    from omega_connect.shared.i18n import LANGUAGE

    LANGUAGE.prepare_restart_environment(os.environ, code)
    os.execv(sys.executable, [sys.executable, "-m", "omega_connect", *sys.argv[1:]])


def build_dashboard(verify: VerifyFunction, *, refresh_seconds: float = DASHBOARD_REFRESH_SECONDS,
                    detect: DetectFunction | None = None, zone: ZoneTools | None = None,
                    report: ReportFunction | None = None, writer: FileExportWriter | None = None,
                    repair: RepairTools | None = None, remote: RemoteTools | None = None,
                    remote_sync: RemoteSyncTools | None = None,
                    settings: SettingsTools | None = None,
                    distributed: DistributedTools | None = None,
                    updater: UpdaterTools | None = None) -> DashboardFunction:
    """Ouvre l'interface (Textual charge seulement ici : la ligne de commande n'en a pas besoin)."""
    def dashboard(request: DetectRequest) -> int:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("omega-connect : pas de terminal interactif ; utilisez « detecter » ou « verifier ».",
                  file=sys.stderr)
            return 2
        from omega_lib.infrastructure.terminal.detector import SystemTerminalDetector
        from omega_lib.terminal.service import resolve_render_profile

        detected = SystemTerminalDetector().detect()
        install_language(settings, detected.family)
        from omega_connect.interfaces.tui.app import OmegaConnectApp

        profile = resolve_render_profile(detected).render_profile
        # Scan relu (2026-11-22) : un seul scan de cette machine, partage par tous les ecrans
        scan = ScanCache(lambda: verify(request))
        shown = build_report(lambda _request: scan(), zone, remote.parc if remote is not None else None, remote,
                             rescan=False) if zone is not None else None

        def open_folder(path: Path) -> bool:
            from omega_lib.infrastructure.desktop.browser_opener import open_path_in_browser

            path.mkdir(parents=True, exist_ok=True)
            return open_path_in_browser(path).ok

        def rescan_all() -> None:
            request_rescan(scan)
            if remote is not None:
                rescan_network(remote)

        app = OmegaConnectApp(verify=scan, version=__version__, render_profile=profile,
                        refresh_seconds=refresh_seconds, zone=zone, repair=repair,
                        parc=remote.parc if remote is not None else SqliteParcStore(var_dir()),
                        machine=machine_name(), remote=remote,
                        remote_sync=remote_sync, system_clipboard=copy_text, settings=settings,
                        distributed=distributed, updater=updater,
                        contact=build_contact_support("omega-connect", __version__, var_dir()),
                        detect=(lambda: detect(request)) if detect is not None else None,
                        report=ReportTools(lambda: shown(request), writer, rescan_all,
                                           settings.exports_dir if settings is not None else None, open_folder)
                        if report is not None and writer is not None and shown is not None else None)
        run_with_text_direction(app)
        if app.pending_language is not None:  # pragma: no cover - remplace le processus
            restart_for_language(app.pending_language)
        return 0

    return dashboard


def _rescan(text: str, remote: RemoteTools) -> None:
    target = parse_target(text)
    if target is not None:
        scan_remote(target, remote)


def stress_roots(detect: DetectFunction) -> list[str]:
    """Dossiers d'omega-stress de cette machine (charge distribuee : cette machine pilote)."""
    report = detect(DetectRequest(manual_paths=[], with_sheets=False))
    return [item.root for item in report.installations if item.tool == STRESS_TOOL]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        relaunched = relaunch_with_zone_group(sys.argv[1:])
        if relaunched is not None:
            return relaunched
    detect = build_detect()
    zone = build_zone()
    verify = build_verify(detect, zone=zone)
    parc = SqliteParcStore(var_dir())
    session = SshRemoteSession()
    pilot = LocalPilot(lambda: stress_roots(detect))
    remote = RemoteTools(scanner=session, parc=parc, suggest=LocalSuggestions(), pilot=pilot,
                         local_name=(socket.gethostname() or "?").split(".")[0][:64])
    report = build_report(verify, zone, parc, remote)
    settings = build_settings()
    writer = FileExportWriter(settings.exports_dir)
    repair = build_repair()
    releases = ChainedReleases(GithubReleases(), SiteReleases(), SiteReleases(MIRROR_SITE_URL, "craftdark"))
    updater = UpdaterTools(releases=releases, runner=run_in_terminal)
    remote_sync = RemoteSyncTools(session=session, releases=releases, remote=remote,
                                  payload=lambda: build_payload(runnable=True))
    distributed = DistributedTools(
        runner=StressRunner(), pilot=pilot, address_towards=local_address_towards,
        rescan=lambda text: _rescan(text, remote))
    dashboard = build_dashboard(verify, detect=detect, zone=zone, report=report, writer=writer, repair=repair,
                                remote=remote, remote_sync=remote_sync, settings=settings,
                                distributed=distributed, updater=updater)
    return main_with(detect, verify, argv, dashboard, zone, report=report, writer=writer, repair=repair,
                     parc=parc, machine=machine_name(), remote=remote, remote_sync=remote_sync)
