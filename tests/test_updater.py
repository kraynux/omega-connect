# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""UPDATER (2026-11-22) : lignes d'apres ce qui est scanne, verification des versions (GitHub puis le site),
Reparer qui y renvoie, et une mise a jour de bout en bout sur CETTE machine avec une fausse installation dans un
dossier temporaire (archive verifiee, extraite par-dessus, install.sh lance, resultat relu). Jamais le reseau."""
from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

from omega_connect.application.updater import (
    AppRow,
    UpdateState,
    app_rows,
    check_versions,
    finish_local,
    prepare_local,
    run_local,
)
from omega_connect.domain.fleet import AppState, RegistryRow
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.updates import ReleaseArchive, ReleaseFailure
from omega_connect.infrastructure.updates.local_agent import run_in_terminal
from omega_connect.infrastructure.updates.site_releases import ChainedReleases


class FakeSource:
    def __init__(self, label: str, versions: dict[str, str | ReleaseFailure], archives: dict | None = None):
        self.label = label
        self.versions = versions
        self.archives = archives or {}
        self.asked: list[str] = []

    def latest(self, tool):
        self.asked.append(tool)
        return self.versions.get(tool, ReleaseFailure.NO_RELEASE)

    def fetch(self, tool, version):
        return self.archives.get((tool, version), ReleaseFailure.NO_RELEASE)


def _row(machine, tool, root, version, state=AppState.ENROLLED):
    return RegistryRow(machine, tool, root, "", "", version, state)


def test_lignes_et_etats() -> None:
    local = MachineEntry("pc", True, "", (_row("pc", "omega-stress", "/a", "2.0.0"),))
    remote = MachineEntry("mpc", False, "", (_row("mpc", "omega-fire", "/b", "3.5"),
                                             _row("mpc", "omega-jail", "/c", "1.2.1", AppState.INCOMPLETE)),
                          "fp", ("mpc",), "kr@mpc")
    gone = MachineEntry("vieux", False, "", (_row("vieux", "omega-serv", "/d", "2.6.0"),), "fp2", ("v",), "kr@v",
                        reachable=False)
    rows = app_rows([remote, gone, local])
    assert [r.machine for r in rows][0] == "pc"  # cette machine d'abord
    assert rows[0].state is UpdateState.NOT_CHECKED
    releases = ChainedReleases(FakeSource("GitHub", {"omega-fire": "3.6.2", "omega-stress": "2.0.0"}),
                               FakeSource("site", {"omega-jail": "1.2.1", "omega-fire": "3.6.0"}))
    checked = {r.tool: r for r in check_versions(rows, releases)}
    assert checked["omega-stress"].state is UpdateState.UP_TO_DATE
    assert checked["omega-fire"].state is UpdateState.OUTDATED and checked["omega-fire"].latest == "3.6.2"
    assert checked["omega-fire"].origin == "GitHub"
    assert checked["omega-jail"].state is UpdateState.INCOMPLETE and checked["omega-jail"].origin == "site"
    assert checked["omega-serv"].state is UpdateState.UNREACHABLE
    assert checked["omega-fire"].actionable and checked["omega-jail"].actionable
    assert not checked["omega-stress"].actionable


def test_github_puis_kraynux_puis_craftdark() -> None:
    """Procedure de l'auteur (2026-11-22) : GitHub ; si absent ou injoignable, le site kraynux ; si absent ou
    injoignable, le site craftdark. La premiere source qui publie l'outil donne sa version."""
    github = FakeSource("GitHub", {"omega-fire": "3.6.2"})
    kraynux = FakeSource("kraynux", {"omega-stress": "2.0.0", "omega-fire": "3.6.3"})
    craftdark = FakeSource("craftdark", {"omega-connect": "0.2.0", "omega-stress": "2.0.0"})
    releases = ChainedReleases(github, kraynux, craftdark)
    assert releases.latest("omega-fire") == "3.6.2" and releases.origin("omega-fire") == "GitHub"
    assert releases.latest("omega-stress") == "2.0.0" and releases.origin("omega-stress") == "kraynux"
    assert craftdark.asked == []  # kraynux a repondu pour chacun : craftdark n'est pas interroge
    assert releases.latest("omega-connect") == "0.2.0" and releases.origin("omega-connect") == "craftdark"
    assert releases.latest("omega-inconnu") is ReleaseFailure.NO_RELEASE
    down = FakeSource("GitHub", {"omega-x": ReleaseFailure.NETWORK})
    assert ChainedReleases(down, FakeSource("kraynux", {"omega-x": "1.0"})).latest("omega-x") == "1.0"


def test_sites_kraynux_et_craftdark_meme_structure() -> None:
    from omega_lib.declaration.models import MIRROR_SITE_URL

    from omega_connect.infrastructure.updates.site_releases import SiteReleases

    kraynux, craftdark = SiteReleases(), SiteReleases(MIRROR_SITE_URL, "craftdark")
    assert kraynux.label == "kraynux" and craftdark.label == "craftdark"
    assert kraynux._sha_url("omega-log", "1.6.0") == "https://kraynux.snake-mackarel.ts.net/omega-log/download/sha.txt"
    assert craftdark._archive_url("omega-log", "1.6.0", "omega-log-1.6.0.tar.gz") == (
        "https://craftdark.snake-mackarel.ts.net/omega-log/download/omega-log-1.6.0.tar.gz")


def test_une_requete_par_outil() -> None:
    source = FakeSource("GitHub", {"omega-fire": "3.6.2"})
    rows = [AppRow("a", "", True, "omega-fire", "/x", "3.5"), AppRow("b", "t", False, "omega-fire", "/y", "3.5")]
    check_versions(rows, ChainedReleases(source))
    assert source.asked == ["omega-fire"]


def _archive(tmp: Path, tool: str, version: str) -> ReleaseArchive:
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as tar:
        for name, content, mode in ((f"{tool}/VERSION", version, 0o644),
                                    (f"{tool}/install.sh", "#!/bin/sh\necho installe > installe.txt\n", 0o755)):
            info = tarfile.TarInfo(name)
            payload = content.encode()
            info.size, info.mode = len(payload), mode
            tar.addfile(info, io.BytesIO(payload))
    folder = tmp / "dl"
    folder.mkdir(exist_ok=True)
    path = folder / f"{tool}-{version}.tar.gz"
    path.write_bytes(data.getvalue())
    return ReleaseArchive(tool, version, str(path), hashlib.sha256(data.getvalue()).hexdigest())


def test_mise_a_jour_de_cette_machine_de_bout_en_bout(tmp_path: Path) -> None:
    root = tmp_path / "omega-demo"
    root.mkdir()
    (root / "VERSION").write_text("1.0.0")
    (root / "var").mkdir()
    (root / "var" / "etat.json").write_text("garde")  # l'etat vivant n'est pas dans l'archive : jamais touche
    archive = _archive(tmp_path, "omega-demo", "2.0.0")
    releases = ChainedReleases(FakeSource("site", {"omega-demo": "2.0.0"}, {("omega-demo", "2.0.0"): archive}))
    row = check_versions([AppRow("pc", "", True, "omega-demo", str(root), "1.0.0")], releases)[0]
    assert row.actionable
    prepared = prepare_local([row], releases)
    assert not prepared.refused and (prepared.directory / "updates.json").is_file()
    code = run_local(prepared, run_in_terminal)
    ok, text = finish_local(prepared)
    assert code == 0 and ok, text
    assert (root / "VERSION").read_text() == "2.0.0"
    assert (root / "installe.txt").is_file()  # install.sh lance dans le dossier de l'application
    assert (root / "var" / "etat.json").read_text() == "garde"
    assert not prepared.directory.exists()  # dossier prive efface


def test_archive_refusee_rien_n_est_prepare(tmp_path: Path) -> None:
    releases = ChainedReleases(FakeSource("GitHub", {"omega-demo": "2.0.0"}))
    row = check_versions([AppRow("pc", "", True, "omega-demo", str(tmp_path), "1.0.0")], releases)[0]
    prepared = prepare_local([row], releases)
    assert prepared.refused and prepared.refused[0][1] is ReleaseFailure.NO_RELEASE
    assert not prepared.directory.exists()


def test_reparer_renvoie_vers_l_updater() -> None:
    from omega_connect.domain.problems import Problem, ProblemKind
    from omega_connect.interfaces.tui.screens.repair import actionable, who

    old = _row("mpc", "omega-fire", "/b", "3.5", AppState.OLD_VERSION)
    for local in (True, False):
        problem = Problem("mpc", local, ProblemKind.UPDATE, row=old, target="kr@mpc")
        assert who(problem) == "updater" and actionable(problem)


def _fake_suite(tmp: Path, version: str = "1.6.0", stress: str = "1.6.0") -> tuple[Path, Path]:
    suite = tmp / "omega-suite"
    (suite / "src" / "omega_suite").mkdir(parents=True)
    (suite / "omega-suite.sh").write_text("#!/bin/sh\n")
    (suite / "pyproject.toml").write_text(f'[project]\nname = "omega-suite"\nversion = "{version}"\n')
    (suite / ".venv" / "bin").mkdir(parents=True)
    (suite / ".venv" / "bin" / "activate").write_text("")
    (suite / ".venv" / "bin" / "python").write_text("")
    embedded = suite / "vendor" / "omega-stress"
    (embedded / "src" / "omega_stress").mkdir(parents=True)
    (embedded / "omega-stress.sh").write_text("#!/bin/sh\n")
    (embedded / "pyproject.toml").write_text(f'[project]\nname = "omega-stress"\nversion = "{stress}"\n')
    return suite, embedded


def test_omega_stress_d_omega_suite_reconnu_et_mis_a_jour_avec_elle(tmp_path: Path) -> None:
    """Decision de l'auteur (2026-11-22) : la copie embarquee fait partie d'omega-suite. Jamais « installation
    inachevee » (le .venv est celui de la suite) ; trop ancienne -> c'est omega-suite qui se met a jour."""
    from omega_connect.application.detect_installations import detect_installations
    from omega_connect.domain.detection import Source
    from omega_connect.domain.fleet import registry_rows
    from omega_connect.domain.links import VerificationReport
    from omega_connect.domain.versions import outdated
    from omega_connect.infrastructure.detection.filesystem_scan import FilesystemScanLocator
    from omega_connect.infrastructure.detection.layout import FilesystemInspector

    suite, embedded = _fake_suite(tmp_path)
    report = detect_installations(str(tmp_path), [FilesystemScanLocator(tmp_path, 4, Source.HOME)],
                                  FilesystemInspector(), None)
    item = next(found for found in report.installations if found.tool == "omega-stress")
    assert {found.tool for found in report.installations} == {"omega-stress", "omega-suite"}
    assert item.root == str(embedded) and item.suite == str(suite) and item.suite_version == "1.6.0"
    assert item.venv_ready is True  # celui de la suite
    found = outdated(item)  # omega-stress 1.6.0 < 2.0.0 (charge distribuee)
    assert found is not None and found.tool == "omega-suite" and found.root == str(suite)
    assert found.contains == "omega-stress" and not found.incomplete
    row = next(line for line in registry_rows(VerificationReport(report, ()), None, "pc")
               if line.tool == "omega-stress")
    assert row.state is AppState.OLD_VERSION and row.suite == str(suite)
    from omega_connect.domain.remote import rows_from_list, rows_to_list

    assert rows_from_list(rows_to_list([row]), "pc")[0].suite_version == "1.6.0"  # garde par le registre du parc
    (line,) = app_rows([MachineEntry("pc", True, "", tuple(registry_rows(VerificationReport(report, ()), None,
                                                                         "pc")))])
    assert (line.tool, line.root, line.version, line.contains) == ("omega-suite", str(suite), "1.6.0",
                                                                    "omega-stress 1.6.0")
    releases = ChainedReleases(FakeSource("site", {"omega-suite": "1.7.0", "omega-stress": "2.0.0"}))
    (checked,) = check_versions([line], releases)
    assert checked.state is UpdateState.OUTDATED and checked.latest == "1.7.0" and checked.actionable


def test_copie_vendor_sans_omega_suite_reste_un_omega_stress(tmp_path: Path) -> None:
    from omega_connect.infrastructure.detection.layout import embedding_suite

    _suite, embedded = _fake_suite(tmp_path)
    (tmp_path / "omega-suite" / "omega-suite.sh").unlink()
    assert embedding_suite(str(embedded)) == ("", "")
    assert embedding_suite("/home/kr/omega-stress") == ("", "")


def test_version_d_omega_fire_dans_pyproject_puis_ancienne_constante(tmp_path: Path) -> None:
    """2026-11-22 : omega-fire porte sa version dans pyproject.toml (seule source) ; une installation d'avant
    (pyproject.toml vide, constante OMEGA_FIRE_VERSION) reste lue."""
    from omega_connect.infrastructure.detection.layout import installed_version

    new, old = tmp_path / "neuf", tmp_path / "ancien"
    for root in (new, old):
        (root / "src" / "omega_fire" / "core").mkdir(parents=True)
    (new / "pyproject.toml").write_text('# commentaire\n[project]\nname = "omega-fire"\nversion = "3.6.3"\n')
    (new / "src/omega_fire/core/constants.py").write_text("OMEGA_FIRE_VERSION = project_version(ROOT)\n")
    (old / "pyproject.toml").write_text("")
    (old / "src/omega_fire/core/constants.py").write_text('OMEGA_FIRE_VERSION = "3.6.1"\n')
    assert installed_version(new, "omega-fire") == "3.6.3"
    assert installed_version(old, "omega-fire") == "3.6.1"


def test_omega_suite_reconnue_elle_meme_et_ses_outils_une_seule_ligne(tmp_path: Path) -> None:
    """2026-11-22 : omega-connect reconnait les 14 outils publies (omega-tail : 2026-11-25) ; omega-suite et son omega-stress embarque sont
    trouves tous les deux, l'Updater n'en fait qu'une ligne ; un outil sans liaison est « Installee »."""
    from omega_connect.application.detect_installations import detect_installations
    from omega_connect.domain.detection import Source
    from omega_connect.domain.fleet import registry_rows
    from omega_connect.domain.links import VerificationReport
    from omega_connect.infrastructure.detection.filesystem_scan import FilesystemScanLocator
    from omega_connect.infrastructure.detection.layout import FilesystemInspector

    suite, embedded = _fake_suite(tmp_path, stress="2.0.0")
    log = tmp_path / "omega-log"
    (log / "src" / "omega_log").mkdir(parents=True)
    (log / "omega-log.sh").write_text("#!/bin/sh\n")
    (log / "pyproject.toml").write_text('[project]\nname = "omega-log"\nversion = "1.6.0"\n')
    report = detect_installations(str(tmp_path), [FilesystemScanLocator(tmp_path, 4, Source.HOME)],
                                  FilesystemInspector(), None)
    assert sorted((item.tool, item.version) for item in report.installations) == [
        ("omega-log", "1.6.0"), ("omega-stress", "2.0.0"), ("omega-suite", "1.6.0")]
    rows = registry_rows(VerificationReport(report, ()), None, "pc")
    assert {row.tool: row.state for row in rows}["omega-log"] is AppState.INSTALLED
    assert {row.tool: row.state for row in rows}["omega-suite"] is AppState.INSTALLED
    lines = app_rows([MachineEntry("pc", True, "", rows)])
    assert sorted((line.tool, line.root, line.contains) for line in lines) == [
        ("omega-log", str(log), ""), ("omega-suite", str(suite), "omega-stress 2.0.0")]


def test_installer_lignes_par_machine(tmp_path: Path) -> None:
    """Installer (2026-11-22) : chaque machine joignable x les 14 outils publies ; deja la ou a installer dans
    ~/<outil> ; l'omega-stress d'omega-suite ne compte pas ; une machine injoignable n'est pas proposee."""
    from omega_connect.application.updater import install_rows
    from omega_connect.domain.tools import INSTALLABLE_TOOLS

    local = MachineEntry("pc", True, "", (_row("pc", "omega-fire", "/f", "3.6.2"),
                                          RegistryRow("pc", "omega-stress", "/s/vendor/omega-stress", "", "", "2.0.0",
                                                      AppState.ENROLLED, (), "/s", "1.7.0")))
    remote = MachineEntry("mpc", False, "", (), "fp", ("mpc",), "kr@mpc")
    gone = MachineEntry("vieux", False, "", (), "fp2", ("v",), "kr@v", reachable=False)
    rows = install_rows([remote, gone, local])
    assert len(rows) == 2 * len(INSTALLABLE_TOOLS) == 28
    by = {(row.machine, row.tool): row for row in rows}
    assert by[("pc", "omega-fire")].state is UpdateState.PRESENT and not by[("pc", "omega-fire")].actionable
    stress = by[("pc", "omega-stress")]
    assert stress.install and stress.root == "~/omega-stress" and stress.state is UpdateState.NOT_CHECKED
    checked = {row.key: row for row in check_versions(rows, ChainedReleases(FakeSource("site", {"omega-log": "1.6.0"})))}
    log = checked[by[("mpc", "omega-log")].key]
    assert log.state is UpdateState.TO_INSTALL and log.actionable and log.target == "kr@mpc"
    assert checked[by[("mpc", "omega-scan")].key].state is UpdateState.UNKNOWN  # rien de publie


def test_installer_cette_machine_de_bout_en_bout(tmp_path: Path, monkeypatch) -> None:
    """Nouveau dossier ~/omega-demo, archive verifiee, extraite, install.sh lance ; un dossier deja rempli est
    refuse (jamais par-dessus autre chose)."""
    from omega_connect.domain.updates import Purpose

    home = tmp_path / "maison"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    archive = _archive(tmp_path, "omega-demo", "1.0.0")
    releases = ChainedReleases(FakeSource("site", {"omega-demo": "1.0.0"}, {("omega-demo", "1.0.0"): archive}))
    row = check_versions([AppRow("pc", "", True, "omega-demo", "~/omega-demo", "", install=True)], releases)[0]
    prepared = prepare_local([row], releases, Purpose.INSTALL)
    assert not prepared.refused
    code = run_local(prepared, run_in_terminal)
    ok, text = finish_local(prepared)
    assert code == 0 and ok, text
    assert (home / "omega-demo" / "VERSION").read_text() == "1.0.0"
    assert (home / "omega-demo" / "installe.txt").is_file()
    # deuxieme fois : le dossier existe et n'est pas vide -> refus, rien n'est touche
    archive = _archive(tmp_path, "omega-demo", "1.0.0")
    releases = ChainedReleases(FakeSource("site", {"omega-demo": "1.0.0"}, {("omega-demo", "1.0.0"): archive}))
    prepared = prepare_local([row], releases, Purpose.INSTALL)
    run_local(prepared, run_in_terminal)
    ok, text = finish_local(prepared)
    assert not ok and "existe déjà" in text


def test_version_affichee_egale_pyproject() -> None:
    """Etape B (2026-11-22) : aucune copie du numero dans le code ; splash, barre, rapport et contact lisent
    pyproject.toml."""
    import re

    import omega_connect

    root = Path(omega_connect.__file__).resolve().parents[2]
    found = re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(), re.M)
    assert found is not None and omega_connect.__version__ == found.group(1)
    assert '__version__ = "' not in (root / "src/omega_connect/__init__.py").read_text()


async def test_ligne_omega_suite_courte_et_detail_sous_le_tableau() -> None:
    """Retour d'utilisation 2026-11-26 : la liste des 7 outils d'omega-suite dans la colonne « Application »
    (~130 caracteres) faisait un enorme ascenseur horizontal, les etats hors de vue. La cellule dit « omega-suite
    (7 outil(s)) » ; la liste et les versions sont sous le tableau, pour la ligne choisie."""
    from textual.app import App
    from textual.widgets import Static

    from omega_connect.interfaces.tui.screens.updater import UpdaterScreen
    from omega_connect.interfaces.tui.widgets.tables import WideTable

    tools = ("check", "deep", "fold", "fuzz", "scan", "stress", "track")
    suite_rows = tuple(RegistryRow("pc", f"omega-{name}", f"/s/vendor/omega-{name}", "", "", "1.6.0",
                                   AppState.INSTALLED, (), "/s", "1.7.0") for name in tools)
    entry = MachineEntry("pc", True, "", (_row("pc", "omega-fire", "/f", "3.6.2"), *suite_rows))

    class Parc:
        def load(self):
            return (entry,)

    screen = UpdaterScreen(parc=Parc(), releases=ChainedReleases(), remote_sync=None, rescan_local=lambda: None,
                           runner=lambda argv: 0, machine="pc")

    class Host(App):
        def on_mount(self) -> None:
            self.push_screen(screen)

    app = Host()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        table = screen.query_one("#updater-table", WideTable)
        cells = [str(table.get_row_at(index)[2]) for index in range(table.row_count)]
        assert cells == ["omega-fire", "omega-suite (7 outil(s))"]
        assert table.virtual_size.width <= 120  # plus d'ascenseur horizontal : l'etat reste visible
        detail = screen.query_one("#updater-detail", Static)
        assert str(detail.render()) == ""  # omega-fire : rien a detailler
        table.move_cursor(row=1)
        await pilot.pause()
        text = str(detail.render())
        assert "omega-suite 1.7.0 contient : omega-check 1.6.0" in text and "omega-track 1.6.0" in text
        assert "seule la ligne omega-suite est à mettre à jour" in text


def test_colonne_machine_abregee_adresses_sous_le_tableau() -> None:
    from omega_connect.interfaces.tui.screens.updater import machine_cell, row_detail

    long = "omega-server (192.168.1.109, kraynux.snake-mackarel.ts.net)"
    assert machine_cell(long) == "omega-server (192.168.1.109 +1)"
    assert machine_cell("craftdark (192.168.1.103)") == "craftdark (192.168.1.103)"
    assert machine_cell("pc") == "pc"
    assert row_detail(AppRow(long, "kr@x", False, "omega-fire", "/f", "3.6.2")) == f"Machine : {long}"
    assert row_detail(AppRow("pc", "", True, "omega-fire", "/f", "3.6.2")) == ""
