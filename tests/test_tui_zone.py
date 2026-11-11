# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Interface sous le pilote Textual (refonte du parcours, lot R1) : menu, Registre (etats, selection, « Inscrire »
en un seul plan, Corriger, Detail), Scanner, Liaisons, Dashboard, Reparer. Les commandes root passent par le faux
systeme (`zone_fakes.FakeSystem`), les commandes des outils par un executeur qui les note : jamais de vrai sudo,
jamais le vrai /var/lib."""
from __future__ import annotations

from pathlib import Path

import pytest
from omega_lib.synchro.models import InstanceSheet, ReadStatus
from omega_lib.terminal.models import RenderProfile
from textual.widgets import Button, DataTable, Static
from zone_fakes import AT, FIRE, SERV, SERV_SERVICE, SUBJECT, FakeSystem, _detection

from omega_connect.application.repair_actions import RepairTools
from omega_connect.application.zone_actions import ZoneTools
from omega_connect.domain.detection import DetectedInstallation, DetectionReport, SheetResult, Source
from omega_connect.domain.links import (
    Check,
    CheckCode,
    CheckStatus,
    Link,
    LinkKind,
    Repair,
    RepairKind,
    VerificationReport,
)
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.repair import RepairStep, StepOutcome
from omega_connect.domain.zone import read_registry
from omega_connect.domain.zone_checks import zone_link
from omega_connect.interfaces.tui.app import OmegaConnectApp
from omega_connect.interfaces.tui.menu import MENU
from omega_connect.interfaces.tui.screens.dashboard import LinksScreen
from omega_connect.interfaces.tui.screens.enroll import EnrollScreen
from omega_connect.interfaces.tui.screens.home import HomeScreen
from omega_connect.interfaces.tui.screens.keep_or_erase import KeepOrEraseScreen
from omega_connect.interfaces.tui.screens.local_repair import LocalRepairScreen
from omega_connect.interfaces.tui.screens.registry import RegistryScreen
from omega_connect.interfaces.tui.screens.repair import RepairScreen
from omega_connect.interfaces.tui.screens.scanner import ScannerScreen
from omega_connect.interfaces.tui.screens.synchronisation import SynchronisationScreen
from omega_connect.interfaces.tui.screens.zone_detail import ZoneDetailScreen
from omega_connect.interfaces.tui.screens.zone_plan import ZonePlanScreen
from omega_connect.interfaces.tui.widgets.splash_hero import splash_content

ROOT = "/home/k/omega-serv"
NEW_ROOT = "/home/k/omega-waf"
NEW = DetectedInstallation(NEW_ROOT, "omega-serv", (Source.HOME,), "k", ReadStatus.ABSENT,
                           sheet=SheetResult(ReadStatus.OK, InstanceSheet("omega-serv", "2.6.1", "", "omega-serv", AT)))
"""Application trouvee sans carte d'identite (jeton) : « Inscrire » la lui fait creer."""
DETECTION = _detection(SERV, FIRE, NEW)


class _Subject:
    def subject(self):
        return SUBJECT


class _NotedRunner:
    def __init__(self) -> None:
        self.ran: list[tuple[str, ...]] = []

    def run(self, step: RepairStep) -> StepOutcome:
        self.ran.append(step.argv())
        return StepOutcome(step, 0)


class _Parc:
    def __init__(self) -> None:
        self.saved: list[MachineEntry] = []

    def load(self) -> tuple[MachineEntry, ...]:
        return tuple(self.saved)

    def save(self, machine: MachineEntry) -> None:
        self.saved = [entry for entry in self.saved if entry.key != machine.key] + [machine]

    def remove(self, key: str) -> bool:
        before = len(self.saved)
        self.saved = [entry for entry in self.saved if entry.key != key]
        return len(self.saved) != before


@pytest.fixture
def system(tmp_path: Path) -> FakeSystem:
    return FakeSystem(tmp_path)


def _app(system: FakeSystem, *, detection: DetectionReport = DETECTION, extra=(), noted: _NotedRunner | None = None,
         parc: _Parc | None = None, remote=None, remote_sync=None) -> OmegaConnectApp:
    def verify() -> VerificationReport:
        return VerificationReport(detection, (*extra, zone_link(system.inspect(), detection, SUBJECT, "oc")))

    tools = ZoneTools(inspector=system, runner=system, subject=_Subject(), now=lambda: AT, interactive=lambda: False)
    return OmegaConnectApp(verify=verify, version="0.1.0", render_profile=RenderProfile.COMPLETE, refresh_seconds=0,
                           zone=tools, detect=lambda: detection, splash=False, machine="pc-test", parc=parc,
                           repair=RepairTools(runner=noted or _NotedRunner(), user=lambda: "k"), remote=remote,
                           remote_sync=remote_sync)


async def _open(app: OmegaConnectApp, pilot, entry: str):
    await pilot.pause()
    assert isinstance(app.screen, HomeScreen)
    await pilot.click(f"#menu-{entry}")
    await _settle(app, pilot)
    return app.screen


async def _settle(app: OmegaConnectApp, pilot) -> None:
    for _round in range(5):
        await app.workers.wait_for_complete()
        await pilot.pause()


def _states(screen: RegistryScreen | SynchronisationScreen) -> dict[str, str]:
    return {row.root: row.state.value for row in screen._rows}


def test_splash_keeps_the_author_characters_and_the_real_version():
    content = splash_content("0.1.0")
    text = content.plain
    assert "OMEGA TOOLS CONNECTOR" in text and "█▓▒░V0.1.0░▒▓█" in text
    assert "OMEGA-STRESS─│██│\\ \\_\\██│────OMEGA-LOG" in text
    lines = text.split("\n")
    def center(line: str) -> float:
        start = len(line) - len(line.lstrip())
        return start + (len(line.strip()) - 1) / 2

    blocks = [lines[0], lines[1], lines[3], lines[4], lines[9], lines[13], lines[-1]]
    # titre, barre de version, cadres OMEGA et CONNECT, interrupteur, ligne du bas : centres sur la colonne 29
    # (milieu du cadre CONNECT), une demi-colonne a gauche pour les blocs de largeur paire
    assert [center(line) - 29 for line in blocks] == [0, 0, -0.5, 0, 0, -0.5, 0]
    assert "OFF" in text and "══" in lines[8] and lines[8].index("══") == 28
    assert "SYNCHRONISATION | RULES | PERMISSION | TOOLS | NETWORKS" in text
    styles = {str(span.style) for span in content.spans}
    lit = {text[span.start:span.end] for span in content.spans if str(span.style) == "$accent"}
    assert "OFF" in lit and "ON" not in lit  # interrupteur sur OFF : le voyant OFF est allume
    assert {"$accent", "$foreground", "$foreground 75%", "$foreground 55%", "$foreground 35%"} <= styles
    for span in content.spans:  # jamais d'espace en bord de plage (piege constate chez omega-log)
        piece = text[span.start:span.end]
        assert piece == piece.strip(" ") and "\n" not in piece




async def test_menu_is_the_one_chosen_by_the_author(system):
    app = _app(system)
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        home = app.screen
        labels = [str(button.label) for button in home.query(Button)]
        assert labels == ["REGISTRE", "SCANNER", "LIAISONS", "SYNCHRONISATION", "DASHBOARD",
                          "RÉPARER", "RAPPORT", "RÉGLAGES", "AIDE", "QUITTER"]
        assert labels == [entry.label.upper() for entry in MENU]
        await pilot.click("#menu-settings")  # Reglages : lot F, notification seulement
        await pilot.pause()
        assert app.screen is home


async def test_registry_only_displays_what_was_scanned(system):
    """Retours de l'auteur : le Registre est un affichage (etats en couleur) ; deux boutons explicites, chacun une
    seule chose : « Mettre à jour le registre » (scan sur place, sans changer d'ecran) et « Mettre à jour
    l'application » (grise si la ligne n'est pas une ancienne version d'une machine distante)."""
    app = _app(system)
    async with app.run_test(size=(140, 50)) as pilot:
        registry = await _open(app, pilot, "registry")
        assert isinstance(registry, RegistryScreen)
        assert registry.query_one("#registry-table", DataTable).row_count == 3
        assert _states(registry) == {SERV.root: "enrolled", FIRE.root: "enrolled", NEW_ROOT: "detected"}
        summary = str(registry.query_one("#registry-summary", Static).render())
        assert "◐ 2 Inscrite" in summary and "○ 1 Détectée" in summary
        assert {button.id for button in registry.query(Button)} == {"update", "update-app", "back"}
        assert str(registry.query_one("#update", Button).label) == "Mettre à jour le registre"
        assert str(registry.query_one("#update-app", Button).label) == "Mettre à jour l'application"
        assert registry.query_one("#update-app", Button).disabled
        await pilot.click("#update")
        await _settle(app, pilot)
        assert app.screen is registry  # sur place : jamais le Scanner


async def test_synchroniser_tout_in_one_plan_then_everything_is_linked_and_removable(system):
    """Synchronisation -> « Synchroniser tout » -> un plan, un mot de passe -> « Reliée » ; puis tout retirer."""
    before = system.snapshot()
    noted = _NotedRunner()
    app = _app(system, noted=noted)
    async with app.run_test(size=(140, 50)) as pilot:
        registry = await _open(app, pilot, "synchronisation")
        assert isinstance(registry, SynchronisationScreen)
        assert registry.query_one("#sync-table", DataTable).row_count == 3
        assert _states(registry) == {SERV.root: "enrolled", FIRE.root: "enrolled", NEW_ROOT: "detected"}
        assert "pas encore préparé" in str(registry.query_one("#space-badge", Static).render())
        await pilot.click("#enroll-all")
        await _settle(app, pilot)
        plan_screen = app.screen
        assert isinstance(plan_screen, EnrollScreen) and not system.ran and not noted.ran
        text = str(plan_screen.query_one("#enroll-plan", Static).render())
        assert "1. Cartes d'identité à créer" in text and f"{NEW_ROOT}/omega-serv.sh synchro jeton" in text
        assert "sudo groupadd --system omega-synchro" in text
        assert f"Recopier la carte d'identité de {NEW_ROOT}" in text
        await pilot.click("#run")
        await _settle(app, pilot)
        assert noted.ran == [(f"{NEW_ROOT}/omega-serv.sh", "synchro", "jeton")]
        assert "Synchronisation terminée" in str(plan_screen.query_one("#enroll-progress", Static).render())
        await pilot.click("#back")
        await _settle(app, pilot)
        assert app.screen is registry
        # Le faux executeur ne cree pas vraiment la carte de NEW : elle reste « Détectée ».
        assert _states(registry) == {SERV.root: "linked", FIRE.root: "linked", NEW_ROOT: "detected"}
        assert "prêt" in str(registry.query_one("#space-badge", Static).render())

        await pilot.click("#detail")
        await _settle(app, pilot)
        detail = app.screen
        assert isinstance(detail, ZoneDetailScreen)
        assert detail.query_one("#linked-table", DataTable).row_count == 2
        await pilot.click("#remove-all")
        await pilot.pause()
        assert isinstance(app.screen, KeepOrEraseScreen)
        await pilot.click("#erase")
        await _settle(app, pilot)
        assert isinstance(app.screen, ZonePlanScreen)
        await pilot.click("#run")
        await _settle(app, pilot)
        await pilot.click("#back")
        await _settle(app, pilot)
    assert system.snapshot() == before


async def test_synchroniser_la_selection_only_touches_the_chosen_rows(system):
    app = _app(system)
    async with app.run_test(size=(140, 50)) as pilot:
        registry = await _open(app, pilot, "synchronisation")
        assert registry.query_one("#enroll-chosen", Button).disabled
        table = registry.query_one("#sync-table", DataTable)
        index = [row.root for row in registry._rows].index(FIRE.root)
        table.move_cursor(row=index)
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert registry._chosen == {("pc-test", FIRE.root)} and not registry.query_one("#enroll-chosen", Button).disabled
        await pilot.click("#enroll-chosen")
        await _settle(app, pilot)
        assert isinstance(app.screen, EnrollScreen) and app.screen._plan.roots == (FIRE.root,)
        await pilot.click("#run")
        await _settle(app, pilot)
        await pilot.click("#back")
        await _settle(app, pilot)
        assert _states(registry)[FIRE.root] == "linked" and _states(registry)[SERV.root] == "enrolled"
    registry_file = read_registry(system.inspect()).value
    assert registry_file is not None and [item.root for item in registry_file.installations] == [FIRE.root]


async def test_a_row_to_fix_says_why_in_the_registry(system):
    rights = Link(LinkKind.BLOCKLIST, "omega-serv", ROOT, (
        Check(CheckCode.BLOCKLIST_MODE, CheckStatus.FAILURE, f"{ROOT}/var/lib/waf/blocklist.json", "k:k 0600",
              fix="p", repair=Repair(RepairKind.SERV_PERMISSIONS, ROOT, "omega-serv", "omega-serv")),))
    app = _app(system, extra=(rights,))
    async with app.run_test(size=(140, 50)) as pilot:
        registry = await _open(app, pilot, "registry")
        assert _states(registry)[ROOT] == "to-fix"
        index = [row.root for row in registry._rows].index(ROOT)
        registry.query_one("#registry-table", DataTable).move_cursor(row=index)
        await pilot.pause()
        detail = str(registry.query_one("#row-detail", Static).render()).lower()
        assert "liste noire" in detail and "réparer" in detail


async def test_scanner_updates_the_registry_and_the_parc(system):
    parc = _Parc()
    app = _app(system, parc=parc)
    async with app.run_test(size=(140, 50)) as pilot:
        scanner = await _open(app, pilot, "scanner")
        assert isinstance(scanner, ScannerScreen)
        text = str(scanner.query_one("#scan-result", Static).render())
        assert "3 application(s) omega trouvée(s)" in text and "dossier personnel (3)" in text
        assert scanner.query_one("#remote").disabled  # machines distantes : lot R2
        assert [entry.name for entry in parc.saved] == ["pc-test"] and len(parc.saved[0].rows) == 3
        await pilot.click("#back")  # Retour : au menu
        await _settle(app, pilot)
        assert isinstance(app.screen, HomeScreen)
        await _open(app, pilot, "scanner")
        await pilot.click("#registry")  # « Voir le registre » depuis le menu : ouvre le Registre
        await _settle(app, pilot)
        assert isinstance(app.screen, RegistryScreen)
        await pilot.press("escape")
        await _settle(app, pilot)
        assert isinstance(app.screen, HomeScreen)


@pytest.mark.parametrize(("entry", "kinds"), [
    ("links", {LinkKind.BLOCKLIST, LinkKind.ZONE}),  # espace partagé : relié ou pas (retour de l auteur)
])
async def test_links_and_dashboard(system, entry, kinds):
    rights = Link(LinkKind.BLOCKLIST, "omega-serv", ROOT, (Check(CheckCode.BLOCKLIST_OK, CheckStatus.OK, "/b"),))
    app = _app(system, extra=(rights,))
    async with app.run_test(size=(140, 50)) as pilot:
        screen = await _open(app, pilot, entry)
        assert isinstance(screen, LinksScreen)
        assert {link.kind for link in screen._links} == kinds
        table = screen.query_one("#links-table", DataTable)
        assert str(table.get_row_at(0)[1]) == "Local"  # provenance : liaison vue sur cette machine


CLASSIC_FOOTER = ["escape", "q", "t", "r", "a", "s"]
"""Barre d'etat identique partout (demande de l'auteur, 2026-11-10) : Echap Retour, q Quitter, t Theme suivant,
r Rafraichir, a Aide, s Reglages ; jamais de touche propre a un ecran."""


def _footer_keys(app: OmegaConnectApp) -> list[str]:
    shown = [(key, active.binding.description) for key, active in app.active_bindings.items() if active.binding.show]
    order = {key: index for index, key in enumerate(CLASSIC_FOOTER)}
    return sorted((key for key, _label in shown), key=lambda key: order.get(key, 99))


@pytest.mark.parametrize("entry", ["registry", "scanner", "links", "synchronisation", "dashboard", "repair"])
async def test_footer_is_the_same_on_every_screen(system, entry):
    app = _app(system)
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        assert _footer_keys(app) == CLASSIC_FOOTER
        labels = {key: active.binding.description for key, active in app.active_bindings.items()}
        assert labels["escape"] == "Retour" and labels["q"] == "Quitter"
        await _open(app, pilot, entry)
        assert _footer_keys(app) == CLASSIC_FOOTER


async def test_detail_shows_a_service_group_creation(system):
    from omega_connect.application.zone_actions import apply_plan, establish_plan

    facts = system.inspect()
    assert apply_plan(establish_plan(facts, _detection(SERV_SERVICE), SUBJECT, AT), facts, system).ok
    app = _app(system, detection=_detection(SERV_SERVICE))
    async with app.run_test(size=(140, 50)) as pilot:
        await _open(app, pilot, "synchronisation")
        await pilot.click("#detail")
        await _settle(app, pilot)
        created = app.screen.query_one("#created-table", DataTable)
        kinds = {str(created.get_row_at(index)[0]) for index in range(created.row_count)}
        assert "groupe donné au service (par omega-serv)" in kinds


async def test_repair_shows_the_owner_commands_runs_them_then_offers_the_zone(system):
    """Lot E : commandes des outils affichees, lancees sur accord ; la zone (etablie a la main avant, copie
    perimee simulee) est proposee ensuite par l'ecran du plan d'« Établir »."""
    noted = _NotedRunner()
    permissions = Repair(RepairKind.SERV_PERMISSIONS, ROOT, "omega-serv", "omega-serv")

    def verify() -> VerificationReport:
        return VerificationReport(DETECTION, (
            Link(LinkKind.BLOCKLIST, "omega-serv", ROOT, (
                Check(CheckCode.BLOCKLIST_MODE, CheckStatus.FAILURE, f"{ROOT}/var/lib/waf/blocklist.json", "k:k 0600",
                      fix="p", repair=permissions),)),
            Link(LinkKind.ZONE, "", "", (
                Check(CheckCode.ZONE_NOT_LINKED, CheckStatus.WARNING, ROOT, "omega-serv", fix="e",
                      repair=Repair(RepairKind.ZONE)),)),
        ))

    tools = ZoneTools(inspector=system, runner=system, subject=_Subject(), now=lambda: AT, interactive=lambda: False)
    app = OmegaConnectApp(verify=verify, version="0.1.0", render_profile=RenderProfile.COMPLETE, refresh_seconds=0,
                          zone=tools, detect=lambda: DETECTION, splash=False,
                          repair=RepairTools(runner=noted, user=lambda: "k"))
    async with app.run_test(size=(120, 45)) as pilot:
        listing = await _open(app, pilot, "repair")
        await _settle(app, pilot)
        assert isinstance(listing, RepairScreen)  # d'abord la liste de tout ce qui ne va pas
        table = listing.query_one("#problems", DataTable)
        assert table.row_count == 2
        assert "À réparer (bloquant)" in str(table.get_row_at(0)[2]) and "l'outil" in str(table.get_row_at(0)[3])
        await pilot.click("#repair-one")
        await _settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, LocalRepairScreen)  # puis le plan de cette machine
        text = str(screen.query_one("#repair-plan", Static).render())
        assert "omega-serv répare les droits" in text and "service permissions --service-name omega-serv" in text
        run = screen.query_one("#run", Button)
        assert str(run.label) == "Lancer avec sudo" and not run.disabled
        assert not screen.query_one("#zone-frame").display  # zone : apres les commandes
        assert not noted.ran
        await pilot.click("#run")
        await _settle(app, pilot)
        assert noted.ran == [(f"{ROOT}/omega-serv.sh", "service", "permissions", "--service-name", "omega-serv")]
        # Parcours enchaine : le plan d'« Etablir » s'ouvre aussitot apres les commandes des outils.
        assert isinstance(app.screen, ZonePlanScreen)
        assert screen.query_one("#zone-frame").display  # le bouton reste si on ferme le plan
        assert not system.ran  # rien de la zone n'est lance avant « Lancer avec sudo »




class _FakeRemote:
    """Scanner distant factice : machine d'abord inconnue, acceptee, puis scannee."""

    def __init__(self) -> None:
        self.trusted = False

    def check_host(self, target):
        from omega_connect.domain.remote import HostCheck, HostKey

        key = HostKey.KNOWN if self.trusted else HostKey.UNKNOWN
        return HostCheck(target, key, ("256 SHA256:abcDEF hpc-109 (ED25519)",), b"hpc-109 ssh-ed25519 AAAA\n")

    def trust(self, _check) -> bool:
        self.trusted = True
        return True

    def scan(self, _target):
        from omega_connect.domain.fleet import AppState, RegistryRow
        from omega_connect.domain.remote import RemoteScan

        row = RegistryRow("hpc-109", "omega-stress", "/srv/omega-stress", "worker", "active", "1.4.0", AppState.ENROLLED)
        link = Link(LinkKind.BLOCKLIST, "omega-serv", "/srv/omega-serv",
                    (Check(CheckCode.BLOCKLIST_OK, CheckStatus.OK, "/srv/b"),), machine="hpc-109")
        return RemoteScan("hpc-109", "f" * 16, "2026-11-10T20:00:00Z", (row,), (link,))


async def test_scanner_remote_machine_trust_then_registry_and_network_links(system):
    from omega_connect.application.remote_actions import RemoteTools
    from omega_connect.interfaces.tui.screens.trust_host import TrustHostScreen

    parc = _Parc()
    fake = _FakeRemote()
    app = _app(system, parc=parc, remote=RemoteTools(fake, parc))
    async with app.run_test(size=(150, 55)) as pilot:
        scanner = await _open(app, pilot, "scanner")
        scanner.query_one("#remote").value = "k@192.168.1.109"
        await pilot.click("#scan-remote")
        await _settle(app, pilot)
        assert isinstance(app.screen, TrustHostScreen)
        assert "SHA256:abcDEF" in str(app.screen.query_one("#trust-text", Static).render())
        assert not fake.trusted  # rien d'accepte avant l'accord
        await pilot.click("#trust")
        await _settle(app, pilot)
        assert app.screen is scanner and fake.trusted
        result = str(scanner.query_one("#remote-result", Static).render())
        assert "hpc-109 (192.168.1.109) : 1 application(s)" in result
        known = scanner.query_one("#known-machines", DataTable)
        assert str(known.get_row_at(0)[0]) == "hpc-109 (192.168.1.109)"
        await pilot.click("#registry")
        await _settle(app, pilot)
        registry = app.screen
        assert isinstance(registry, RegistryScreen)
        assert ("hpc-109 (192.168.1.109)", "omega-stress") in {(row.machine, row.tool) for row in registry._rows}
        await pilot.press("escape")
        await _settle(app, pilot)
        links = await _open(app, pilot, "links")
        table = links.query_one("#links-table", DataTable)
        provenances = {str(table.get_row_at(index)[1]) for index in range(table.row_count)}
        assert "Réseau — hpc-109" in provenances


async def test_scanner_lists_reachable_machines_and_scans_one_without_typing(system):
    from omega_connect.application.remote_actions import RemoteTools
    from omega_connect.domain.remote import RemoteTarget, Suggestion, SuggestionSource
    from omega_connect.interfaces.tui.screens.trust_host import TrustHostScreen

    parc = _Parc()
    fake = _FakeRemote()
    suggestions = (Suggestion(RemoteTarget("kraynux", "192.168.1.109"), (SuggestionSource.UNISON,)),
                   Suggestion(RemoteTarget("kraynux", "192.168.1.103"), (SuggestionSource.KNOWN_HOSTS,)))
    app = _app(system, parc=parc, remote=RemoteTools(fake, parc, lambda: suggestions))
    async with app.run_test(size=(150, 60)) as pilot:
        scanner = await _open(app, pilot, "scanner")
        table = scanner.query_one("#suggestions", DataTable)
        assert table.row_count == 2 and str(table.get_row_at(0)[1]) == "Unison"
        assert str(table.get_row_at(0)[2]) == "jamais scannée"
        assert not scanner.query_one("#remote").disabled  # la saisie manuelle reste
        table.focus()
        await pilot.press("enter")
        await _settle(app, pilot)
        assert isinstance(app.screen, TrustHostScreen)
        await pilot.click("#trust")
        await _settle(app, pilot)
        assert "hpc-109 (192.168.1.109)" in str(scanner.query_one("#remote-result", Static).render())
        assert "hpc-109 — 1 application(s), répond" in str(table.get_row_at(0)[2])


async def test_forget_a_machine_from_the_scanner(system):
    """Demande de l'auteur : « Retirer cette machine » (grand parc : ne pas tout rescanner) ; rien n'est touche sur
    la machine, elle sort seulement du registre."""
    from omega_connect.application.remote_actions import RemoteTools, scan_remote
    from omega_connect.domain.remote import RemoteTarget
    from omega_connect.interfaces.tui.screens.confirm import ConfirmScreen

    parc = _Parc()
    fake = _FakeRemote()
    tools = RemoteTools(fake, parc)
    assert scan_remote(RemoteTarget("k", "192.168.1.109"), tools).ok
    app = _app(system, parc=parc, remote=tools)
    async with app.run_test(size=(150, 60)) as pilot:
        scanner = await _open(app, pilot, "scanner")
        assert not scanner.query_one("#forget", Button).disabled
        await pilot.click("#forget")
        await _settle(app, pilot)
        assert isinstance(app.screen, ConfirmScreen)
        assert "Rien n'est modifié sur la machine" in str(app.screen.query_one("#confirm-text", Static).render())
        await pilot.click("#confirm")
        await _settle(app, pilot)
        assert [machine.name for machine in parc.saved if not machine.local] == []
        assert scanner.query_one("#forget", Button).disabled


@pytest.mark.parametrize("size", [(120, 40), (200, 60)])
async def test_links_table_fills_the_screen(system, size):
    """Retour de l'auteur : le tableau occupait 16 lignes et 77 colonnes, avec un ascenseur, quel que soit l'ecran ;
    il prend maintenant toute la place restante (largeur et hauteur), et seul lui defile."""
    many = tuple(Link(LinkKind.BLOCKLIST, f"i{n}", f"/r{n}", (Check(CheckCode.BLOCKLIST_OK, CheckStatus.OK, "/b"),),
                      machine=f"m{n % 4}") for n in range(40))
    app = _app(system, extra=many)
    async with app.run_test(size=size) as pilot:
        screen = await _open(app, pilot, "links")
        await _settle(app, pilot)
        panel = screen.query_one(".omega-panel")
        table = screen.query_one("#links-table", DataTable)
        assert panel.virtual_size.height <= panel.region.height  # le panneau ne defile pas
        assert table.region.width >= panel.region.width - 6
        assert table.virtual_size.width >= table.region.width - 4  # la derniere colonne va jusqu'au bord
        detail = screen.query_one("#link-detail")
        assert detail.region.y + detail.region.height <= panel.region.y + panel.region.height


async def test_synchronisation_of_a_remote_machine_without_typing_anything_there(system):
    """Lot R3 : machine du registre -> plan calcule la-bas -> « Lancer » -> terminal (suspendu en test) ->
    resultat, machine rescannee."""
    from omega_connect.application.remote_actions import RemoteTools, scan_remote
    from omega_connect.application.remote_sync import RemoteSyncTools
    from omega_connect.domain.remote import RemoteTarget
    from omega_connect.domain.updates import (
        ReleaseArchive,
        RemotePlan,
        RemoteResult,
        RemoteStepResult,
        StepName,
    )
    from omega_connect.domain.versions import Outdated
    from omega_connect.interfaces.tui.screens.remote_machine import RemoteMachineScreen

    class Session:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def plan(self, target):
            self.calls.append("plan")
            return RemotePlan("hpc-109", "f" * 16, (Outdated("omega-jail", "/h/omega-jail", "1.1.0", "1.2.1"),),
                              "Réparer : plan\n", "Synchroniser : plan\n", False, True, True)

        def prepare(self, target, files):
            self.calls.append("prepare:" + ",".join(sorted(files)))
            return "/tmp/omega-connect.ABCDEFGH"

        def run(self, target, directory):
            self.calls.append("run")
            return 0

        def finish(self, target, directory):
            self.calls.append("finish")
            return RemoteResult((RemoteStepResult(StepName.UPDATE, 0, "omega-jail"),
                                 RemoteStepResult(StepName.REPAIR, 0), RemoteStepResult(StepName.ENROLL, 0)))

    class Releases:
        def latest(self, tool):
            return "1.2.1"

        def fetch(self, tool, version):
            import tempfile

            directory = Path(tempfile.mkdtemp(dir=system.base))
            (directory / "a.tar.gz").write_bytes(b"x")
            return ReleaseArchive(tool, version, str(directory / "a.tar.gz"), "a" * 64)

    parc = _Parc()
    remote = RemoteTools(_FakeRemote(), parc)
    assert scan_remote(RemoteTarget("k", "192.168.1.109"), remote).ok
    session = Session()
    sync = RemoteSyncTools(session, Releases(), remote, payload=lambda: b"zip")
    app = _app(system, parc=parc, remote=remote, remote_sync=sync)
    async with app.run_test(size=(150, 60)) as pilot:
        screen = await _open(app, pilot, "synchronisation")
        table = screen.query_one("#sync-table", DataTable)
        machines = [str(table.get_row_at(index)[1]) for index in range(table.row_count)]
        assert "pc-test" in machines and "hpc-109 (192.168.1.109)" in machines  # une seule liste, toutes machines
        table.focus()
        table.move_cursor(row=machines.index("hpc-109 (192.168.1.109)"))
        await pilot.press("space")
        await pilot.pause()
        assert screen._chosen == {("hpc-109 (192.168.1.109)", "/srv/omega-stress")}
        await pilot.click("#enroll-chosen")
        await _settle(app, pilot)
        machine = app.screen
        assert isinstance(machine, RemoteMachineScreen)
        text = str(machine.query_one("#machine-plan", Static).render())
        assert "Réparer : plan" in text and "1.1.0 → 1.2.1" not in text  # synchroniser : jamais de mise a jour
        assert "Mettre à jour l'application" in text  # mais elle est signalee, avec le chemin
        assert session.calls == ["plan"]  # rien de lance avant « Lancer »
        await pilot.click("#launch")
        await _settle(app, pilot)
        assert session.calls == ["plan", "prepare:agent.pyz,updates.json", "run", "finish"]
        result = str(machine.query_one("#machine-plan", Static).render())
        assert "✓ Synchroniser" in result
        assert machine.query_one("#launch", Button).disabled  # deja lance
        await pilot.click("#back")
        await _settle(app, pilot)
        assert app.screen is screen


async def test_registry_updates_an_old_application_of_a_remote_machine(system):
    """Retour de l'auteur (2026-11-11) : « Mettre à jour l'application » met a jour, rien d'autre."""
    from omega_connect.application.remote_actions import RemoteTools
    from omega_connect.application.remote_sync import RemoteSyncTools
    from omega_connect.domain.fleet import AppState, RegistryRow
    from omega_connect.domain.updates import ReleaseArchive, RemotePlan, RemoteResult, RemoteStepResult, StepName
    from omega_connect.domain.versions import Outdated
    from omega_connect.interfaces.tui.screens.remote_machine import RemoteMachineScreen

    calls: list[str] = []

    class Session:
        def plan(self, target):
            return RemotePlan("hpc-109", "f" * 16, (Outdated("omega-serv", "/h/omega-serv", "0.1.0", "2.6.1"),),
                              "", "", False, True, False)

        def prepare(self, target, files):
            calls.append("prepare:" + ",".join(sorted(files)) + ":" + files["updates.json"].decode())
            return "/tmp/omega-connect.ABCDEFGH"

        def run(self, target, directory):
            return 0

        def finish(self, target, directory):
            return RemoteResult((RemoteStepResult(StepName.UPDATE, 0, "omega-serv"),))

    class Releases:
        def latest(self, tool):
            return "2.6.1"

        def fetch(self, tool, version):
            import tempfile

            directory = Path(tempfile.mkdtemp(dir=system.base))
            (directory / "a.tar.gz").write_bytes(b"x")
            return ReleaseArchive(tool, version, str(directory / "a.tar.gz"), "a" * 64)

    parc = _Parc()
    old = RegistryRow("omega-server", "omega-serv", "/h/omega-serv", "", "", "0.1.0", AppState.OLD_VERSION)
    parc.save(MachineEntry("omega-server", False, "2026-11-11T00:00:00Z", (old,), "f" * 16, ("192.168.1.109",),
                           "kraynux@192.168.1.109"))
    remote = RemoteTools(_FakeRemote(), parc)
    sync = RemoteSyncTools(Session(), Releases(), remote, payload=lambda: b"zip")
    app = _app(system, parc=parc, remote=remote, remote_sync=sync)
    async with app.run_test(size=(150, 60)) as pilot:
        registry = await _open(app, pilot, "registry")
        table = registry.query_one("#registry-table", DataTable)
        table.move_cursor(row=len(registry._rows) - 1)
        await pilot.pause()
        assert not registry.query_one("#update-app", Button).disabled
        await pilot.click("#update-app")
        await _settle(app, pilot)
        machine = app.screen
        assert isinstance(machine, RemoteMachineScreen)
        text = str(machine.query_one("#machine-plan", Static).render())
        assert "omega-serv 0.1.0 → 2.6.1" in text and "Rien d'autre n'est fait" in text
        assert str(machine.query_one("#launch", Button).label) == "Mettre à jour sur hpc-109"
        await pilot.click("#launch")
        await _settle(app, pilot)
        assert '"purpose": "update"' in calls[0] and "omega-serv-2.6.1.tar.gz" in calls[0]
        assert "✓ Mise à jour omega-serv" in str(machine.query_one("#machine-plan", Static).render())


async def test_repair_a_remote_machine_from_here_and_copy_manual_commands(system):
    """Retour de l'auteur (2026-11-11) : « on ne peut rien réparer depuis omega-connect, et les commandes il faut
    les retaper à la main sur la machine distante ». Réparer -> machine choisie -> lancé SUR elle ; copier."""
    from omega_connect.application.remote_actions import RemoteTools, scan_remote
    from omega_connect.application.remote_sync import RemoteSyncTools
    from omega_connect.domain.remote import RemoteTarget
    from omega_connect.domain.updates import RemotePlan, RemoteResult, RemoteStepResult, StepName
    from omega_connect.interfaces.tui.screens.remote_machine import RemoteMachineScreen

    sent: list[str] = []

    class Session:
        def plan(self, target):
            return RemotePlan("hpc-109", "f" * 16, (), "Réparer : 1 commande\n", "", False, True, True, True,
                              ("sudo chmod 0640 /srv/x.log",))

        def prepare(self, target, files):
            sent.append(files["updates.json"].decode())
            return "/tmp/omega-connect.ABCDEFGH"

        def run(self, target, directory):
            return 0

        def finish(self, target, directory):
            return RemoteResult((RemoteStepResult(StepName.REPAIR, 0),))

    class Releases:
        def latest(self, tool):
            raise AssertionError("réparer ne met jamais à jour")

        def fetch(self, tool, version):
            raise AssertionError("réparer ne met jamais à jour")

    import dataclasses

    degraded = Link(LinkKind.TOKENS, "", "", (Check(CheckCode.TOKEN_RIGHTS, CheckStatus.WARNING, "/srv/jeton.json",
                                                    "k:k 0600", fix="chmod 0644 /srv/jeton.json"),),
                    machine="hpc-109")

    class StillDegraded(_FakeRemote):
        """La machine, rescannee a l'ouverture de Reparer, a toujours un ecart."""

        def scan(self, target):
            return dataclasses.replace(super().scan(target), links=(degraded,))

    parc = _Parc()
    remote = RemoteTools(StillDegraded(), parc)
    assert scan_remote(RemoteTarget("k", "192.168.1.109"), remote).ok
    app = _app(system, parc=parc, remote=remote, remote_sync=RemoteSyncTools(Session(), Releases(), remote,
                                                                             payload=lambda: b"zip"))
    async with app.run_test(size=(150, 60)) as pilot:
        repair = await _open(app, pilot, "repair")
        table = repair.query_one("#problems", DataTable)
        rows = [str(table.get_row_at(index)[0]) for index in range(table.row_count)]
        assert "hpc-109 (192.168.1.109)" in rows  # la machine du reseau est dans la liste, avec son probleme
        table.move_cursor(row=rows.index("hpc-109 (192.168.1.109)"))
        await pilot.pause()
        assert "commande lancée sur la machine" in str(table.get_row_at(rows.index("hpc-109 (192.168.1.109)"))[3])
        await pilot.click("#repair-one")
        await _settle(app, pilot)
        machine = app.screen
        assert isinstance(machine, RemoteMachineScreen)
        assert str(machine.query_one("#launch", Button).label) == "Réparer hpc-109"
        copied: list[str] = []
        app.system_clipboard = lambda text: (copied.append(text), "xclip")[1]
        await pilot.click("#copy")
        await pilot.pause()
        assert copied == ["sudo chmod 0640 /srv/x.log\n"]  # presse-papiers du systeme
        assert app.clipboard == "sudo chmod 0640 /srv/x.log\n"  # et celui du terminal, en plus
        from omega_connect.interfaces.tui.screens import _base

        shown: list[list[str]] = []
        original = _base.show_commands_in_terminal
        _base.show_commands_in_terminal = lambda _app, lines: shown.append(lines)
        try:
            app.system_clipboard = lambda _text: ""  # aucun outil : repli universel, affichage en clair
            machine.query_one("#copy", Button).press()
            await pilot.pause()
        finally:
            _base.show_commands_in_terminal = original
        assert shown == [["sudo chmod 0640 /srv/x.log"]]
        await pilot.click("#launch")
        await _settle(app, pilot)
        assert '"purpose": "repair"' in sent[0] and '"manual": ["sudo chmod 0640 /srv/x.log"]' in sent[0]
        assert "✓ Réparer" in str(machine.query_one("#machine-plan", Static).render())


async def test_dashboard_reads_the_shared_space_and_the_parc(system):
    """Le Dashboard relit l'espace partage (applications Reliees) et montre les machines du registre du parc."""
    from omega_connect.interfaces.tui.screens.overview import OverviewScreen

    app = _app(system)
    async with app.run_test(size=(140, 50)) as pilot:
        screen = await _open(app, pilot, "dashboard")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(screen, OverviewScreen) and screen.overview is not None
        assert screen.overview.machines[0].local and screen.overview.machines[0].rows
