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


def test_github_puis_le_site_la_plus_haute_version() -> None:
    github = FakeSource("GitHub", {"omega-stress": "1.6.0"})
    site = FakeSource("site", {"omega-stress": "2.0.0", "omega-connect": "0.2.0"})
    releases = ChainedReleases(github, site)
    assert releases.latest("omega-stress") == "2.0.0" and releases.origin("omega-stress") == "site"
    assert releases.latest("omega-connect") == "0.2.0"
    assert releases.latest("omega-inconnu") is ReleaseFailure.NO_RELEASE
    egal = ChainedReleases(FakeSource("GitHub", {"x": "1.0"}), FakeSource("site", {"x": "1.0"}))
    assert egal.latest("x") == "1.0" and egal.origin("x") == "GitHub"  # GitHub a egalite


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
    (item,) = report.installations
    assert item.root == str(embedded) and item.suite == str(suite) and item.suite_version == "1.6.0"
    assert item.venv_ready is True  # celui de la suite
    found = outdated(item)  # omega-stress 1.6.0 < 2.0.0 (charge distribuee)
    assert found is not None and found.tool == "omega-suite" and found.root == str(suite)
    assert found.contains == "omega-stress" and not found.incomplete
    (row,) = registry_rows(VerificationReport(report, ()), None, "pc")
    assert row.state is AppState.OLD_VERSION and row.suite == str(suite)
    from omega_connect.domain.remote import rows_from_list, rows_to_list

    assert rows_from_list(rows_to_list([row]), "pc")[0].suite_version == "1.6.0"  # garde par le registre du parc
    (line,) = app_rows([MachineEntry("pc", True, "", (row,))])
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
