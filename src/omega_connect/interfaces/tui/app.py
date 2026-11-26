# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Application Textual d'omega-connect : ecran de demarrage, menu (refonte : GESTION — Registre, Scanner,
Liaisons, Synchronisation, Dashboard | MAINTENANCE — Reparer, Rapport, Reglages, Aide, Quitter). Meme cadre que
le reste de la suite (themes d'omega-lib, feuilles de style par profil de rendu, confirmation de sortie, touche `t`).

Le composition root (app/main.py) passe les fonctions deja cablees : l'interface n'importe jamais
l'infrastructure. Reparer : lot E ; Reglages, Aide et Contact et support : lot F."""
from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, cast

from omega_lib.ports.declaration import ContactSupportServices
from omega_lib.terminal.models import RenderProfile
from omega_lib.theme.policies import DEFAULT_TUI_THEME, TUI_THEMES
from textual.app import App, SystemCommand
from textual.binding import Binding, BindingType

from omega_connect.application.distributed_actions import DistributedTools
from omega_connect.application.enroll_actions import EnrollTools
from omega_connect.application.remote_actions import RemoteTools, scan_remote
from omega_connect.application.remote_sync import RemoteSyncTools
from omega_connect.application.repair_actions import RepairTools
from omega_connect.application.report import ReportTools
from omega_connect.application.scan_cache import rescan_now
from omega_connect.application.scan_service import DEFAULT_WORKERS, LOCAL, ScanJob, ScanService
from omega_connect.application.settings import KEY_THEME, SettingsTools
from omega_connect.application.updater import UpdaterTools
from omega_connect.application.zone_actions import ZoneTools
from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.links import VerificationReport
from omega_connect.domain.remote import parse_target
from omega_connect.interfaces.tui.language_setting import notify_language_at_startup
from omega_connect.interfaces.tui.rendering.stylesheet_loader import load_paths_for
from omega_connect.interfaces.tui.rendering.textual_theme_builder import build_all_textual_themes
from omega_connect.interfaces.tui.screens.contact_support import contact_support_screen
from omega_connect.interfaces.tui.screens.dashboard import LinksScreen, VerifyNow
from omega_connect.interfaces.tui.screens.distributed_load import DistributedLoadScreen
from omega_connect.interfaces.tui.screens.help import HelpScreen
from omega_connect.interfaces.tui.screens.home import HomeScreen
from omega_connect.interfaces.tui.screens.local_repair import LocalRepairScreen
from omega_connect.interfaces.tui.screens.overview import OverviewScreen
from omega_connect.interfaces.tui.screens.quit_confirm import QuitConfirmScreen
from omega_connect.interfaces.tui.screens.registry import RegistryScreen
from omega_connect.interfaces.tui.screens.repair import RepairScreen
from omega_connect.interfaces.tui.screens.report import ReportScreen
from omega_connect.interfaces.tui.screens.scanner import ScannerScreen
from omega_connect.interfaces.tui.screens.settings import SettingsScreen
from omega_connect.interfaces.tui.screens.splash import SplashScreen
from omega_connect.interfaces.tui.screens.synchronisation import SynchronisationScreen
from omega_connect.interfaces.tui.screens.updater import InstallerScreen, UpdaterScreen, rescan_local_machine
from omega_connect.interfaces.tui.views import VIEWS
from omega_connect.interfaces.tui.widgets.scan_banner import parse_moment
from omega_connect.ports.fleet import ParcStore
from omega_connect.shared.i18n import _

if TYPE_CHECKING:
    from pathlib import PurePath

    from textual.screen import Screen

TITLE = "\U0001f517 OMEGA-CONNECT"


class OmegaConnectApp(App[None]):
    TITLE = TITLE
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", _("Quitter"), show=True),
        Binding("ctrl+q", "quit", _("Quitter"), show=False),
        Binding("t", "cycle_theme", _("Thème suivant"), show=True),
        Binding("r", "refresh_terminal", _("Rafraîchir"), show=True),
        Binding("a", "help", _("Aide"), show=True),
        Binding("s", "open_settings", _("Réglages"), show=True),
    ]
    """Barre d'etat identique sur tous les ecrans (comme omega-log) : Echap Retour (ecrans), q Quitter, t Theme
    suivant, r Rafraichir, a Aide, s Reglages. Les touches propres a un ecran (v : verifier) restent actives mais
    n'y figurent pas (demande de l'auteur, 2026-11-10)."""

    def __init__(self, *, verify: VerifyNow, version: str, render_profile: RenderProfile,
                 refresh_seconds: float, theme_name: str = DEFAULT_TUI_THEME, zone: ZoneTools | None = None,
                 detect: Callable[[], DetectionReport] | None = None, splash: bool = True,
                 report: ReportTools | None = None, repair: RepairTools | None = None,
                 parc: ParcStore | None = None, machine: str = "local", remote: RemoteTools | None = None,
                 remote_sync: RemoteSyncTools | None = None,
                 system_clipboard: Callable[[str], str] | None = None,
                 settings: SettingsTools | None = None,
                 contact: ContactSupportServices | None = None,
                 distributed: DistributedTools | None = None,
                 updater: UpdaterTools | None = None,
                 stop_processes: Callable[[], object] = lambda: None,
                 allow_processes: Callable[[], object] = lambda: None) -> None:
        super().__init__(css_path=cast("list[str | PurePath]", load_paths_for(render_profile)))
        for theme in build_all_textual_themes():
            self.register_theme(theme)
        self.theme = theme_name if theme_name in TUI_THEMES else DEFAULT_TUI_THEME
        self.title = f"{TITLE} {version}"
        self._verify = verify
        self._refresh_seconds = refresh_seconds
        self._version = version
        self._zone = zone
        self._detect = detect or (lambda: verify().detection)
        self._splash = splash
        self._report_tools = report
        self._repair_tools = repair
        self._parc = parc
        self._machine = machine
        self._remote = remote
        self._remote_sync = remote_sync
        self._distributed = distributed
        self._updater = updater
        self.system_clipboard = system_clipboard
        self._contact = contact
        self.pending_language: str | None = None
        """Langue choisie dans les Reglages : app/main.py relance l'interface apres sa fermeture."""
        self.settings = settings
        """Reglages (lot F) : theme enregistre, dossiers des exports et des captures."""
        if settings is not None:
            self.theme = settings.theme()
        """Copie dans le presse-papiers du systeme ; renvoie l'outil utilise (vide : aucun)."""
        self.report: VerificationReport | None = None
        """Dernier rapport de `verifier` : chaque vue l'affiche tout de suite, puis le rafraichit."""
        self.verified_at: datetime | None = None
        self.scans = ScanService(scan_local=self._scan_local, scan_remote=self._scan_remote,
                                 workers=self._scan_workers, stop_processes=stop_processes,
                                 allow_processes=allow_processes)
        """Scan en arriere-plan (2026-11-26) : jamais lance tout seul ; voir application/scan_service.py."""

    def on_mount(self) -> None:
        notify_language_at_startup(self)
        self.push_screen(HomeScreen(open_screen=self.screen_for))
        if self._splash:
            self.push_screen(SplashScreen(version=self._version))
        # Aucun scan au lancement (decision 2026-11-26) : etat vide, le scan est propose (bandeau de scan).

    def on_unmount(self) -> None:
        self.scans.stop()  # quitter n'attend jamais la fin d'un scan

    # ---- scan (decision 2026-11-26 : jamais automatique, sauf la machine qu'une action vient de toucher) ----
    def _scan_workers(self) -> int:
        settings = self.settings
        return settings.scan_workers() if settings is not None else DEFAULT_WORKERS

    def _scan_local(self) -> None:
        if self._parc is not None and self._zone is not None:
            rescan_local_machine(self._verify, self._zone.inspector, self._parc, self._machine)
        else:
            rescan_now(self._verify)

    def _scan_remote(self, target_text: str) -> None:
        target = parse_target(target_text)
        if target is not None and self._remote is not None:
            scan_remote(target, self._remote)

    def network_jobs(self) -> list[ScanJob]:
        remote = self._remote
        if remote is None:
            return []
        return [ScanJob(entry.target, entry.label) for entry in remote.parc.load()
                if not entry.local and parse_target(entry.target)]

    def scan_this_machine(self) -> int:
        return self.scans.start([ScanJob(LOCAL, self._machine)])

    def scan_everything(self) -> int:
        """« Scanner tout le parc » : cette machine et chaque machine connue, plusieurs a la fois, en arriere-plan."""
        return self.scans.start([ScanJob(LOCAL, self._machine), *self.network_jobs()])

    def scan_machine(self, target: str, label: str) -> int:
        """« Scanner la machine choisie » (vide : cette machine)."""
        return self.scans.start([ScanJob(target or LOCAL, label or self._machine)])

    def stop_scan(self) -> None:
        self.scans.stop()

    def local_scanned_at(self) -> datetime | None:
        """Heure du scan de cette machine depuis le lancement (None : pas encore scannee)."""
        moment = getattr(self._verify, "scanned_at", None)
        return moment if isinstance(moment, datetime) else None

    def network_scanned_at(self) -> tuple[datetime, ...]:
        """Heure du dernier scan de chaque machine connue du reseau (enregistre : garde d'un lancement a l'autre)."""
        if self._remote is None:
            return ()
        moments = (parse_moment(entry.scanned_at) for entry in self._remote.parc.load() if not entry.local)
        return tuple(moment for moment in moments if moment is not None)

    def local_changed(self) -> None:
        """Une action a change CETTE machine (reparation, synchronisation, liaison, mise a jour) : elle seule est
        rescannee, en arriere-plan ; les ecrans se remettent a jour a la fin."""
        self.scan_this_machine()

    def screen_for(self, key: str) -> Screen[None] | None:
        parc = self._parc
        if key == "dashboard":
            zone_tools = self._zone
            return OverviewScreen(verify=self._verify, refresh_seconds=self._refresh_seconds, machine=self._machine,
                                  inspect=(lambda: zone_tools.inspector.inspect(elevated=False))
                                  if zone_tools is not None else None,
                                  network=parc.load if parc is not None else None)
        if key in VIEWS:
            return LinksScreen(verify=self._verify, refresh_seconds=0, view=VIEWS[key],
                               network_links=(lambda: tuple(link for machine in parc.load() if not machine.local
                                                            for link in machine.links)) if parc else None)
        if key == "help":
            contact = self._contact
            writer = self._report_tools.writer if self._report_tools is not None else None
            return HelpScreen(version=self._version, writer=writer,
                              contact=(lambda: contact_support_screen(contact)) if contact is not None else None)
        if key == "settings" and self.settings is not None:
            return SettingsScreen(tools=self.settings)
        if key == "report":
            return ReportScreen(tools=self._report_tools) if self._report_tools is not None else None
        if self._zone is None:
            return None
        zone = self._zone

        updater_tools, store, machine, verify = self._updater, self._parc, self._machine, self._verify

        def updater(preselect: str = "") -> UpdaterScreen | None:
            if updater_tools is None or store is None:
                return None
            return UpdaterScreen(parc=store, releases=updater_tools.releases, remote_sync=self._remote_sync,
                                 rescan_local=lambda: rescan_local_machine(verify, zone.inspector, store, machine),
                                 runner=updater_tools.runner, machine=machine, preselect=preselect)

        def scanner(*, from_menu: bool = False) -> ScannerScreen:
            return ScannerScreen(verify=self._verify, inspector=zone.inspector, machine=self._machine,
                                 parc=self._parc, registry=registry if from_menu else None, remote=self._remote)

        def registry() -> RegistryScreen:
            return RegistryScreen(verify=self._verify, inspector=zone.inspector, machine=self._machine,
                                  scanner=scanner, parc=self._parc, remote=self._remote,
                                  remote_sync=self._remote_sync, updater=updater)

        if key == "scanner":
            return scanner(from_menu=True)
        if key == "registry":
            return registry()
        distributed_tools, remote = self._distributed, self._remote

        def distributed(preselect: str = "") -> DistributedLoadScreen | None:
            if distributed_tools is None or remote is None:
                return None
            return DistributedLoadScreen(tools=distributed_tools, remote=remote, sudo=zone.runner,
                                         preselect=preselect)

        if key == "updater":
            return updater()
        if key == "installer" and updater_tools is not None and store is not None:
            return InstallerScreen(parc=store, releases=updater_tools.releases, remote_sync=self._remote_sync,
                                   rescan_local=lambda: rescan_local_machine(verify, zone.inspector, store, machine),
                                   runner=updater_tools.runner, machine=machine)
        if key == "synchronisation" and self._repair_tools is not None:
            tools = EnrollTools(zone=zone, repair=self._repair_tools, detect=self._detect)
            return SynchronisationScreen(verify=self._verify, tools=tools, machine=self._machine,
                                         remote_sync=self._remote_sync, distributed=distributed)
        if key == "repair" and self._repair_tools is not None:
            repair_tools = self._repair_tools

            def local_repair() -> LocalRepairScreen:
                return LocalRepairScreen(verify=self._verify, repair=repair_tools, zone=zone, detect=self._detect)

            return RepairScreen(verify=self._verify, inspector=zone.inspector, machine=self._machine,
                                local_repair=local_repair, parc=self._parc, remote_sync=self._remote_sync,
                                distributed=distributed, updater=updater,
                                runner=updater_tools.runner if updater_tools is not None else None)
        return None

    def watch_theme(self, _theme_name: str) -> None:
        self.sub_title = self.theme
        settings = getattr(self, "settings", None)
        if settings is not None and settings.store.get(KEY_THEME) != self.theme:
            with contextlib.suppress(OSError):
                settings.store.set(KEY_THEME, self.theme)

    async def action_quit(self) -> None:
        self.push_screen(QuitConfirmScreen(), self._quit_if_confirmed)

    def _quit_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.exit()

    def action_refresh_terminal(self) -> None:
        """Touche `r` : redessine tout et donne la taille du terminal (comme omega-log)."""
        self.refresh(layout=True)
        self.sub_title = f"{self.theme} | {self.size.width}x{self.size.height}"
        self.notify(f"{self.size.width}x{self.size.height}", title=_("Terminal rafraîchi"))

    def action_help(self) -> None:
        screen = self.screen_for("help")
        if screen is not None:
            self.push_screen(screen)

    def action_open_settings(self) -> None:
        screen = self.screen_for("settings")
        if screen is not None:
            self.push_screen(screen)

    def action_cycle_theme(self) -> None:
        """Theme suivant du catalogue d'omega-lib (non enregistre avant les Reglages du lot F)."""
        names = list(TUI_THEMES)
        index = names.index(self.theme) if self.theme in names else 0
        self.theme = names[(index + 1) % len(names)]

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield SystemCommand(_("Thème"), _("Changer le thème actif"), self.action_change_theme)
        yield SystemCommand(_("Quitter"), _("Quitter l'application (avec confirmation)"), self.action_quit)
        yield SystemCommand(_("Capture d'écran"), _("Enregistrer une capture SVG de l'écran courant"),
                            self.save_screen_capture)

    def save_screen_capture(self) -> None:
        """Capture SVG de l'ecran courant, dans le dossier des captures (Reglages ; var/screenshots/ par defaut)."""
        directory = self.settings.screenshots_dir() if self.settings is not None else None
        if directory is None:
            self.notify(_("Dossier des captures non configuré."), severity="warning")
            return
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.notify(str(error), severity="error")
            return
        self.deliver_screenshot(path=str(directory))
