# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lot R3 : synchroniser une machine distante sans rien y taper (ETUDE_REFONTE §16).

Aucun reseau, aucun vrai sudo : le faux `ssh` de test_remote execute les commandes en local (Python du systeme
isole), dans un TMPDIR de test ; GitHub est remplace par une source d'archives locale ; seul `reparer`/`synchroniser`
(qui demanderaient sudo) est remplace dans le programme envoye, et teste a part."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
import urllib.error
from pathlib import Path

import pytest
from conftest import make_installation
from test_remote import _Parc, fake_remote  # noqa: F401 - fixture reutilisee

from omega_connect.application.remote_actions import RemoteTools
from omega_connect.application.remote_sync import (
    MachinePlan,
    PrepareFailure,
    RemoteSyncTools,
    finish_machine,
    machine_plan,
    prepare_machine,
    run_prepared,
)
from omega_connect.domain.detection import DetectedInstallation, DetectionReport, Source
from omega_connect.domain.remote import RemoteTarget
from omega_connect.domain.updates import (
    Purpose,
    ReleaseArchive,
    ReleaseFailure,
    RemotePlan,
    RemoteResult,
    RemoteStepResult,
    StepName,
    UpdateOrder,
    choose_update,
    plan_from_dict,
    plan_to_dict,
    result_from_dict,
    result_to_dict,
    updates_from_dict,
    updates_to_dict,
)
from omega_connect.domain.versions import (
    Outdated,
    UpdateMode,
    archive_name,
    asset_url,
    expected_sha,
    outdated,
    read_version,
    too_old,
    version_from_tag_url,
    version_key,
)
from omega_connect.infrastructure.remote.apply_update import UpdateError, apply_update, copy_over, extract
from omega_connect.infrastructure.remote.payload import build_payload
from omega_connect.infrastructure.remote.ssh import SshRemoteSession
from omega_connect.interfaces.cli.remote_sync_view import render_machine_plan, render_sync_outcome

# ---- regles pures --------------------------------------------------------------------------------

def test_versions_are_read_and_compared():
    assert version_key("3.6") == (3, 6, 0) and version_key("2.6.1") == (2, 6, 1) and version_key("abc") is None
    assert read_version('[project]\nname = "omega-jail"\nversion = "1.1.0"\n', "omega-jail") == "1.1.0"
    assert read_version('OMEGA_FIRE_VERSION = "3.5"\n', "omega-fire") == "3.5"
    assert read_version("rien", "omega-serv") == ""
    assert too_old("omega-jail", "1.1.0") and not too_old("omega-jail", "1.2.1")
    assert too_old("omega-fire", "3.6") and not too_old("omega-fire", "3.6.1")
    assert not too_old("omega-jail", "") and not too_old("omega-check", "0.1")  # inconnue : jamais « trop ancienne »


def test_github_addresses_and_sha_list():
    assert version_from_tag_url("https://github.com/kraynux/omega-serv/releases/tag/v2.6.1") == "2.6.1"
    assert version_from_tag_url("https://github.com/kraynux/omega-serv/releases") == ""
    assert asset_url("omega-serv", "2.6.1", archive_name("omega-serv", "2.6.1")) == (
        "https://github.com/kraynux/omega-serv/releases/download/v2.6.1/omega-serv-2.6.1.tar.gz")
    sha = "a" * 64
    listing = f"Controle\n\n{sha}  omega-serv-2.6.1.tar.gz\n{'b' * 64}  omega-serv-2.6.0.tar.gz\n"
    assert expected_sha(listing, "omega-serv-2.6.1.tar.gz") == sha
    assert expected_sha(listing, "omega-serv-9.tar.gz") == ""
    assert expected_sha("pas-une-empreinte  omega-serv-2.6.1.tar.gz", "omega-serv-2.6.1.tar.gz") == ""


def test_outdated_from_version_even_without_card_or_sheet():
    from omega_lib.synchro.models import ReadStatus

    old = DetectedInstallation("/h/omega-jail", "omega-jail", (Source.HOME,), "k", ReadStatus.ABSENT,
                               version="1.1.0")
    new = DetectedInstallation("/h/omega-jail", "omega-jail", (Source.HOME,), "k", ReadStatus.ABSENT,
                               version="1.2.1")
    assert outdated(old) == Outdated("omega-jail", "/h/omega-jail", "1.1.0", "1.2.1")
    assert outdated(new) is None


def test_choose_update():
    item = Outdated("omega-jail", "/h/omega-jail", "1.1.0", "1.2.1")
    assert choose_update(item, "1.2.1").possible
    assert choose_update(item, "1.2.0").failure is ReleaseFailure.TOO_OLD_RELEASE
    assert choose_update(item, ReleaseFailure.NO_RELEASE).failure is ReleaseFailure.NO_RELEASE
    fire = choose_update(Outdated("omega-fire", "/h/omega-fire", "3.5", "3.6.1"), "3.6.1")
    assert fire.mode is UpdateMode.ASIDE


def test_documents_round_trip_and_future_versions_refused():
    plan = RemotePlan("craftdark", "f" * 16, (Outdated("omega-jail", "/h/j", "1.1.0", "1.2.1"),), "R\n", "S\n",
                      True, True)
    assert plan_from_dict(plan_to_dict(plan)) == plan
    assert plan_from_dict({**plan_to_dict(plan), "schema_version": 9}) is None
    orders = (UpdateOrder("omega-jail", "/h/j", "1.2.1", "omega-jail-1.2.1.tar.gz", "a" * 64, UpdateMode.OVER),)
    assert updates_from_dict(updates_to_dict(orders)) == orders
    bad = updates_to_dict(orders)
    bad["updates"][0]["archive"] = "../../etc/passwd"
    assert updates_from_dict(bad) is None
    result = RemoteResult((RemoteStepResult(StepName.UPDATE, 0, "omega-jail"), RemoteStepResult(StepName.REPAIR, 1)))
    assert result_from_dict(result_to_dict(result)) == result and not result.ok


# ---- une version trop ancienne n'a jamais de commande qu'elle ne connait pas ----------------------

def test_outdated_jail_gets_no_update_command(tmp_path):
    """Constat du 2026-11-10 (craftdark) : `omega-jail --apply --update` propose a omega-jail 1.1.0."""
    from omega_lib.synchro.models import ReadStatus

    from omega_connect.domain.links import jail_fix_command, jail_repair
    from omega_connect.domain.repair import plan_repair

    jail = DetectedInstallation("/h/omega-jail", "omega-jail", (Source.HOME,), "k", ReadStatus.ABSENT,
                                version="1.1.0")
    detection = DetectionReport("/h", (jail,), (), ())
    assert jail_fix_command(detection) == ("", True)
    assert jail_repair(detection) is not None  # retiree ensuite par without_outdated_repairs
    from omega_connect.domain.links import VerificationReport

    plan = plan_repair(VerificationReport(detection, ()), "k", as_root=False)
    assert plan.outdated == (Outdated("omega-jail", "/h/omega-jail", "1.1.0", "1.2.1"),) and not plan.empty


def test_installed_version_is_read_from_files(tmp_path):
    from omega_connect.infrastructure.detection.layout import installed_version

    root = make_installation(tmp_path / "omega-jail", "omega-jail")
    (root / "pyproject.toml").write_text('[project]\nversion = "1.1.0"\n', encoding="utf-8")
    assert installed_version(root, "omega-jail") == "1.1.0"
    fire = make_installation(tmp_path / "omega-fire", "omega-fire")
    (fire / "src" / "omega_fire" / "core").mkdir(parents=True)
    (fire / "src" / "omega_fire" / "core" / "constants.py").write_text('OMEGA_FIRE_VERSION = "3.5"\n',
                                                                      encoding="utf-8")
    assert installed_version(fire, "omega-fire") == "3.5"
    (root / "pyproject.toml").unlink()
    (root / "pyproject.toml").symlink_to(fire / "src" / "omega_fire" / "core" / "constants.py")
    assert installed_version(root, "omega-jail") == ""  # jamais un lien


# ---- mise a jour sur la machine (sans sudo reel) ------------------------------------------------

def _tar(members: dict[str, bytes], *, extra: list[tarfile.TarInfo] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o755 if name.endswith(".sh") else 0o644
            archive.addfile(info, io.BytesIO(content))
        for info in extra or []:
            archive.addfile(info)
    return buffer.getvalue()


INSTALL_SH = b"#!/bin/sh\necho installe > installe.txt\n"


def _order(session: Path, tool: str, root: Path, data: bytes, mode: UpdateMode = UpdateMode.OVER) -> UpdateOrder:
    name = archive_name(tool, "1.2.1")
    (session / name).write_bytes(data)
    return UpdateOrder(tool, str(root), "1.2.1", name, hashlib.sha256(data).hexdigest(), mode)


def test_update_over_replaces_code_keeps_state_and_never_follows_links(tmp_path):
    root = tmp_path / "omega-jail"
    (root / "var").mkdir(parents=True)
    (root / "var" / "etat.json").write_text("garde", encoding="utf-8")
    (root / "jail.py").write_text("ancien", encoding="utf-8")
    outside = tmp_path / "ailleurs.txt"
    outside.write_text("intact", encoding="utf-8")
    (root / "lien.py").symlink_to(outside)
    session = tmp_path / "session"
    session.mkdir()
    data = _tar({"omega-jail/jail.py": b"nouveau", "omega-jail/lien.py": b"remplace", "omega-jail/install.sh": INSTALL_SH})
    assert apply_update(_order(session, "omega-jail", root, data), session) == ""
    assert (root / "jail.py").read_text(encoding="utf-8") == "nouveau"
    assert (root / "var" / "etat.json").read_text(encoding="utf-8") == "garde"
    assert not (root / "lien.py").is_symlink() and outside.read_text(encoding="utf-8") == "intact"
    assert (root / "installe.txt").exists()  # install.sh lance dans la racine


def test_update_refuses_bad_digest_and_dangerous_archives(tmp_path):
    root = tmp_path / "omega-jail"
    root.mkdir()
    session = tmp_path / "session"
    session.mkdir()
    order = _order(session, "omega-jail", root, _tar({"omega-jail/install.sh": INSTALL_SH}))
    (session / order.archive).write_bytes(b"altere")
    with pytest.raises(UpdateError, match="empreinte"):
        apply_update(order, session)
    for members, extra in (({"omega-jail/../../evil": b"x"}, None), ({"autre/x": b"x"}, None),
                           ({}, [tarfile.TarInfo("omega-jail/lien")])):
        if extra:
            extra[0].type = tarfile.SYMTYPE
            extra[0].linkname = "/etc/passwd"
        archive = tmp_path / "a.tar.gz"
        archive.write_bytes(_tar(members, extra=extra))
        target = tmp_path / f"x{len(list(tmp_path.iterdir()))}"
        target.mkdir()
        with pytest.raises(UpdateError):
            extract(archive, "omega-jail", target)


def test_update_aside_moves_old_install_with_sudo(tmp_path):
    """omega-fire : `sudo mv` (ici un faux sudo qui lance la commande), puis install.sh reprend l'ancienne."""
    fake_sudo = tmp_path / "sudo"
    fake_sudo.write_text('#!/bin/sh\nexec "$@"\n', encoding="utf-8")
    fake_sudo.chmod(0o755)
    root = tmp_path / "maison" / "omega-fire"
    (root / "var" / "db").mkdir(parents=True)
    (root / "var" / "db" / "base").write_text("donnees", encoding="utf-8")
    session = tmp_path / "session"
    session.mkdir()
    data = _tar({"omega-fire/install.sh": INSTALL_SH, "omega-fire/migrate-state.sh": MIGRATE_SH,
                 "omega-fire/var/db/.garde": b""})
    from datetime import datetime

    aside = apply_update(_order(session, "omega-fire", root, data, UpdateMode.ASIDE), session,
                         now=datetime(2026, 11, 11), sudo=str(fake_sudo))
    assert aside.endswith("omega-fire.old-20261111")
    assert (Path(aside) / "var" / "db" / "base").read_text(encoding="utf-8") == "donnees"
    assert (root / "installe.txt").exists()
    assert not (root / "repris-de.txt").exists()  # une seule ancienne : install.sh s'en charge seul


MIGRATE_SH = b'#!/bin/sh\necho "$1 $2" > repris-de.txt\n'


def test_update_aside_with_other_old_installs_names_the_right_one(tmp_path):
    """Constate le 2026-11-11 sur omega-server : un vieux omega-fire.old-20260927 a cote ; install.sh refuse de
    deviner, omega-connect designe celle qu'il vient de mettre de cote."""
    fake_sudo = tmp_path / "sudo"
    fake_sudo.write_text('#!/bin/sh\nexec "$@"\n', encoding="utf-8")
    fake_sudo.chmod(0o755)
    home = tmp_path / "maison"
    root = home / "omega-fire"
    (root / "var" / "db").mkdir(parents=True)
    (root / "var" / "db" / "base").write_text("actuelle", encoding="utf-8")
    old = home / "omega-fire.old-20260927"
    (old / "config").mkdir(parents=True)
    (old / "config" / "omega-fire.conf").write_text("vieux", encoding="utf-8")
    (home / "omega-fire.old-20260905").mkdir()  # vide : pas une ancienne installation
    session = tmp_path / "session"
    session.mkdir()
    data = _tar({"omega-fire/install.sh": INSTALL_SH, "omega-fire/migrate-state.sh": MIGRATE_SH})
    from datetime import datetime

    aside = apply_update(_order(session, "omega-fire", root, data, UpdateMode.ASIDE), session,
                         now=datetime(2026, 11, 11), sudo=str(fake_sudo))
    assert (root / "repris-de.txt").read_text(encoding="utf-8").strip() == f"{aside} --yes"
    assert (old / "config" / "omega-fire.conf").read_text(encoding="utf-8") == "vieux"  # jamais touchee


def test_copy_over_refuses_a_linked_directory(tmp_path):
    source = tmp_path / "src" / "omega-jail"
    (source / "sous").mkdir(parents=True)
    (source / "sous" / "f").write_text("x", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "cible").mkdir()
    (root / "sous").symlink_to(tmp_path / "cible")
    with pytest.raises(UpdateError):
        copy_over(source, root)
    assert not (tmp_path / "cible" / "f").exists()


# ---- GitHub (sans reseau) -----------------------------------------------------------------------

class _Answer(io.BytesIO):
    def __init__(self, data: bytes, url: str = "") -> None:
        super().__init__(data)
        self._url = url

    def geturl(self) -> str:
        return self._url

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *args):  # type: ignore[no-untyped-def]
        self.close()


def test_github_fetch_checks_digest(monkeypatch, tmp_path):
    from omega_connect.infrastructure.updates import github_releases

    archive = b"archive omega-jail"
    good = hashlib.sha256(archive).hexdigest()
    files = {"sha.txt": f"{good}  omega-jail-1.2.1.tar.gz\n".encode(), "omega-jail-1.2.1.tar.gz": archive}

    def urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        name = request.full_url.rsplit("/", 1)[1]
        if name not in files:
            raise urllib.error.HTTPError(request.full_url, 404, "absent", {}, None)  # type: ignore[arg-type]
        return _Answer(files[name])

    monkeypatch.setattr(github_releases.urllib.request, "urlopen", urlopen)
    source = github_releases.GithubReleases(directory=tmp_path)
    fetched = source.fetch("omega-jail", "1.2.1")
    assert isinstance(fetched, ReleaseArchive) and Path(fetched.path).read_bytes() == archive
    assert oct(Path(fetched.path).stat().st_mode & 0o777) == "0o600"
    files["omega-jail-1.2.1.tar.gz"] = b"autre contenu"
    assert source.fetch("omega-jail", "1.2.1") is ReleaseFailure.BAD_SHA
    assert source.fetch("omega-jail", "9.9.9") is ReleaseFailure.NO_SHA  # sha.txt ne la cite pas
    del files["sha.txt"]
    assert source.fetch("omega-jail", "1.2.1") is ReleaseFailure.NO_RELEASE


def test_github_latest_reads_the_redirection(monkeypatch):
    from omega_connect.infrastructure.updates import github_releases

    class Opener:
        def __init__(self, location: str | None) -> None:
            self.location = location

        def open(self, request, timeout=0):  # type: ignore[no-untyped-def]
            if self.location is None:
                raise urllib.error.HTTPError(request.full_url, 404, "absent", {}, None)  # type: ignore[arg-type]
            raise urllib.error.HTTPError(request.full_url, 302, "found", {"Location": self.location},  # type: ignore[arg-type]
                                         None)

    monkeypatch.setattr(github_releases.urllib.request, "build_opener",
                        lambda *_a: Opener("https://github.com/kraynux/omega-serv/releases/tag/v2.6.1"))
    assert github_releases.GithubReleases().latest("omega-serv") == "2.6.1"
    monkeypatch.setattr(github_releases.urllib.request, "build_opener", lambda *_a: Opener(None))
    assert github_releases.GithubReleases().latest("omega-serv") is ReleaseFailure.NO_RELEASE


# ---- de bout en bout, par le faux ssh -----------------------------------------------------------

class _Releases:
    """GitHub remplace : une archive omega-jail 1.2.1 construite pour le test."""

    def __init__(self, tmp_path: Path, data: bytes) -> None:
        self._tmp = tmp_path
        self._data = data
        self.fetched = 0

    def latest(self, tool: str) -> str | ReleaseFailure:
        return "1.2.1" if tool == "omega-jail" else ReleaseFailure.NO_RELEASE

    def fetch(self, tool: str, version: str) -> ReleaseArchive | ReleaseFailure:
        self.fetched += 1
        directory = self._tmp / f"telecharge-{self.fetched}"
        directory.mkdir()
        path = directory / archive_name(tool, version)
        path.write_bytes(self._data)
        return ReleaseArchive(tool, version, str(path), hashlib.sha256(self._data).hexdigest())


AGENT_WITHOUT_SUDO = """
import sys
import omega_connect.app.remote_agent as agent
agent._cli = lambda argv: (print("CLI", " ".join(argv)), 0)[1]
sys.exit(agent.main(sys.argv[1:]))
"""


def _test_payload() -> bytes:
    """Le vrai programme, sauf `reparer`/`synchroniser` (sudo) remplaces par un affichage."""
    import zipfile

    buffer = io.BytesIO(build_payload())
    with zipfile.ZipFile(buffer, "a") as archive:
        archive.writestr("__main__.py", AGENT_WITHOUT_SUDO)
    return buffer.getvalue()


@pytest.fixture
def remote_jail(fake_remote, tmp_path, monkeypatch):  # noqa: F811  # type: ignore[no-untyped-def]
    home = Path(__import__("os").environ["OMEGA_CONNECT_HOME"])
    jail = make_installation(home / "omega-jail", "omega-jail")
    (jail / "pyproject.toml").write_text('[project]\nname = "omega-jail"\nversion = "1.1.0"\n', encoding="utf-8")
    (jail / "regles.conf").write_text("ancien", encoding="utf-8")
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp-distant"))
    (tmp_path / "tmp-distant").mkdir()
    data = _tar({"omega-jail/pyproject.toml": b'[project]\nname = "omega-jail"\nversion = "1.2.1"\n',
                 "omega-jail/regles.conf": b"nouveau", "omega-jail/install.sh": INSTALL_SH})
    session = SshRemoteSession(ssh=str(fake_remote["ssh"]), known_hosts=fake_remote["known_hosts"],
                               scan_timeout=90)
    parc = _Parc()
    tools = RemoteSyncTools(session, _Releases(tmp_path, data), RemoteTools(session, parc), payload=_test_payload)
    return {"jail": jail, "tools": tools, "parc": parc, "tmp": tmp_path / "tmp-distant"}


def test_plan_is_computed_on_the_machine_without_sudo(remote_jail):
    plan = machine_plan(RemoteTarget("k", "hpc-109"), remote_jail["tools"], Purpose.UPDATE)
    assert isinstance(plan, MachinePlan), plan
    assert plan.plan.outdated == (Outdated("omega-jail", str(remote_jail["jail"]), "1.1.0", "1.2.1"),)
    assert plan.updates[0].possible and plan.updates[0].latest == "1.2.1"
    assert "--apply --update" not in plan.plan.repair_text  # jamais une commande inconnue de la 1.1.0
    text = render_machine_plan(plan)
    assert "omega-jail 1.1.0 → 1.2.1" in text and "mot de passe sudo" in text and "Rien d'autre" in text
    sync = machine_plan(RemoteTarget("k", "hpc-109"), remote_jail["tools"], Purpose.SYNC)
    assert isinstance(sync, MachinePlan) and sync.updates == ()  # synchroniser : jamais de mise a jour
    assert "Mettre à jour l'application" in render_machine_plan(sync)


def test_end_to_end_update_only_then_rescan(remote_jail, capfd):
    tools = remote_jail["tools"]
    target = RemoteTarget("k", "hpc-109")
    plan = machine_plan(target, tools, Purpose.UPDATE)
    assert isinstance(plan, MachinePlan)
    prepared = prepare_machine(plan, tools)
    assert not isinstance(prepared, PrepareFailure), prepared
    assert Path(prepared.directory).parent == remote_jail["tmp"]
    assert oct(Path(prepared.directory).stat().st_mode & 0o777) == "0o700"
    assert not list(remote_jail["tmp"].parent.glob("telecharge-*/*"))  # archives locales effacees
    code = run_prepared(prepared, tools)
    printed = capfd.readouterr().out
    assert code == 0, printed
    assert "CLI reparer" not in printed and "CLI synchroniser" not in printed  # mettre a jour : rien d'autre
    assert (remote_jail["jail"] / "regles.conf").read_text(encoding="utf-8") == "nouveau"
    assert (remote_jail["jail"] / "installe.txt").exists()
    outcome = finish_machine(prepared, code, tools)
    assert outcome.ok and [step.name for step in outcome.result.steps] == [StepName.UPDATE]  # type: ignore[union-attr]
    assert not Path(prepared.directory).exists()  # dossier prive efface
    assert outcome.rescan is not None and outcome.rescan.ok
    jail_row = next(row for row in remote_jail["parc"].machines[0].rows if row.tool == "omega-jail")
    assert jail_row.version == "1.2.1"
    assert "✓ Mise à jour omega-jail" in render_sync_outcome(outcome)


def test_a_refused_archive_sends_nothing(remote_jail):
    tools = remote_jail["tools"]

    class Altered(_Releases):
        def fetch(self, tool, version):  # type: ignore[no-untyped-def]
            return ReleaseFailure.BAD_SHA

    altered = RemoteSyncTools(tools.session, Altered(remote_jail["tmp"].parent, b""), tools.remote, tools.payload)
    plan = machine_plan(RemoteTarget("k", "hpc-109"), altered, Purpose.UPDATE)
    assert isinstance(plan, MachinePlan)
    failure = prepare_machine(plan, altered)
    assert isinstance(failure, PrepareFailure) and failure.release
    assert not list(remote_jail["tmp"].iterdir())  # rien d'envoye
    assert (remote_jail["jail"] / "regles.conf").read_text(encoding="utf-8") == "ancien"


def test_run_mode_runs_repair_then_sync_and_stops_at_first_failure(tmp_path, monkeypatch):
    from omega_connect.app import remote_agent

    session = tmp_path / "s"
    session.mkdir()
    (session / "updates.json").write_text(json.dumps(updates_to_dict((), Purpose.SYNC)), encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(remote_agent, "_cli", lambda argv: (calls.append(argv), 1 if argv[0] == "reparer" else 0)[1])
    assert remote_agent.main(["run", str(session)]) == 1
    assert calls == [["reparer", "--oui"]]
    result = result_from_dict(json.loads((session / "result.json").read_text(encoding="utf-8")))
    assert result is not None and [step.code for step in result.steps] == [1]


def test_cli_remote_sync_simulation(remote_jail, capsys):
    from omega_connect.interfaces.cli.main import run

    tools = remote_jail["tools"]
    assert run(["mettre-a-jour", "--machine", "k@hpc-109", "--simulation"], lambda _r: None,  # type: ignore[arg-type,return-value]
               remote_sync=tools) == 0
    out = capsys.readouterr().out
    assert "omega-jail 1.1.0 → 1.2.1" in out
    assert run(["synchroniser", "--machine", "k@hpc-109", "--simulation"], lambda _r: None,  # type: ignore[arg-type,return-value]
               remote_sync=tools) == 0
    assert "1.1.0 → 1.2.1" not in capsys.readouterr().out
    assert (remote_jail["jail"] / "regles.conf").read_text(encoding="utf-8") == "ancien"
    assert run(["synchroniser", "--toutes-machines", "--simulation"], lambda _r: None,  # type: ignore[arg-type,return-value]
               remote_sync=tools) == 2  # registre vide : rien a faire
    assert run(["mettre-a-jour", "--simulation"], lambda _r: None,  # type: ignore[arg-type,return-value]
               remote_sync=tools) == 2  # quelle machine ?


def test_archcraft_path_is_set_for_every_remote_command(fake_remote, tmp_path, monkeypatch):  # noqa: F811
    """Constate le 2026-11-11 sur craftdark : tout avait reussi la-bas, mais le resultat n'etait jamais relu ni le
    dossier efface (`cat`, `rm` introuvables : PATH remplace par la configuration zsh d'Archcraft)."""
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp-distant"))
    (tmp_path / "tmp-distant").mkdir()
    session = SshRemoteSession(ssh=str(fake_remote["ssh"]), known_hosts=fake_remote["known_hosts"], scan_timeout=90)
    target = RemoteTarget("k", "archcraft")
    directory = session.prepare(target, {"result.json": json.dumps(result_to_dict(
        RemoteResult((RemoteStepResult(StepName.ENROLL, 0),)))).encode()})
    assert isinstance(directory, str), directory
    result = session.finish(target, directory)
    assert result is not None and result.ok
    assert not Path(directory).exists()


def test_a_tool_that_cannot_answer_is_never_launched(tmp_path):
    """Constate le 2026-11-11 (omega-server) : un vieil omega-fire se relance avec sudo ; sans terminal sudo echoue
    sans rien demander, mais pam_faillock compte l'echec — trois scans et le compte est verrouille 10 minutes."""
    from omega_lib.synchro.models import ReadStatus

    from omega_connect.application.detect_installations import detect_installations
    from omega_connect.domain.detection import Candidate
    from omega_connect.domain.versions import may_ask_sheet

    assert not may_ask_sheet("omega-fire", ReadStatus.ABSENT, "")      # version illisible, pas de carte
    assert not may_ask_sheet("omega-fire", ReadStatus.ABSENT, "3.5")   # trop ancienne
    assert may_ask_sheet("omega-fire", ReadStatus.ABSENT, "3.6.1")     # a contrats, carte effacee
    assert may_ask_sheet("omega-fire", ReadStatus.OK, "")              # carte presente

    root = make_installation(tmp_path / "omega-fire", "omega-fire")
    asked: list[str] = []

    class Locator:
        def candidates(self):
            return [Candidate(str(root), Source.HOME)]

        def notes(self):
            return []

    class Fetcher:
        def fetch(self, root_path, tool):
            asked.append(root_path)
            raise AssertionError("jamais lance")

    from omega_connect.infrastructure.detection.layout import FilesystemInspector

    report = detect_installations(str(tmp_path), [Locator()], FilesystemInspector(), Fetcher())
    assert asked == [] and outdated(report.installations[0]) is not None


def test_a_broken_venv_is_set_aside_never_deleted(tmp_path):
    """Constate le 2026-11-11 sur omega-server : `.venv` sans `bin/activate` (creation interrompue) ; l'install.sh
    d'omega-serv le gardait et echouait (« .venv/bin/activate: No such file or directory »)."""
    from datetime import datetime

    from omega_connect.infrastructure.remote.apply_update import set_aside_broken_venv

    root = tmp_path / "omega-serv"
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    moved = set_aside_broken_venv(root, datetime(2026, 11, 11, 0, 40))
    assert moved.endswith(".venv.casse-20261111-004000")
    assert not (root / ".venv").exists() and (Path(moved) / "pyvenv.cfg").exists()
    import venv

    venv.create(root / ".venv", with_pip=False)
    assert set_aside_broken_venv(root, datetime(2026, 11, 11)) == ""  # un .venv qui marche n'est pas touche


# ---- brique 2 : installation inachevee ; brique 3 : reparer a distance -----------------------------

def test_incomplete_installation_is_reinstalled_with_the_same_version():
    """omega-server, 2026-11-11 : fichiers 2.6.1, install.sh arrete sur un .venv casse, pas de carte."""
    from omega_lib.synchro.models import ReadStatus

    half = DetectedInstallation("/h/omega-serv", "omega-serv", (Source.HOME,), "k", ReadStatus.ABSENT,
                                version="2.6.1", venv_ready=False)
    found = outdated(half)
    assert found is not None and found.incomplete and found.version == "2.6.1"
    assert choose_update(found, "2.6.1").possible  # meme version : reinstallation
    assert outdated(DetectedInstallation("/h/omega-serv", "omega-serv", (Source.HOME,), "k", ReadStatus.ABSENT,
                                         version="2.6.1", venv_ready=True)) is None  # carte effacee seulement
    from omega_connect.domain.fleet import AppState, registry_rows
    from omega_connect.domain.links import VerificationReport

    rows = registry_rows(VerificationReport(DetectionReport("/h", (half,), (), ()), ()), None, "m")
    assert rows[0].state is AppState.INCOMPLETE
    assert plan_from_dict(plan_to_dict(RemotePlan("m", "", (found,), "", ""))).outdated[0].incomplete


def test_venv_readiness_is_read_without_running_anything(tmp_path):
    from omega_connect.infrastructure.detection.layout import FilesystemInspector

    root = tmp_path / "omega-serv"
    (root / ".venv" / "bin").mkdir(parents=True)
    inspector = FilesystemInspector()
    assert not inspector.venv_ready(str(root))
    (root / ".venv" / "bin" / "activate").write_text("", encoding="utf-8")
    (root / ".venv" / "bin" / "python").symlink_to("/usr/bin/python3")
    assert inspector.venv_ready(str(root))


def test_run_mode_repair_runs_only_reparer(tmp_path, monkeypatch):
    from omega_connect.app import remote_agent

    session = tmp_path / "s"
    session.mkdir()
    (session / "updates.json").write_text(json.dumps(updates_to_dict((), Purpose.REPAIR)), encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(remote_agent, "_cli", lambda argv: (calls.append(argv), 0)[1])
    assert remote_agent.main(["run", str(session)]) == 0
    assert calls == [["reparer", "--oui"]]


def test_repair_plan_text_announces_the_manual_commands_it_will_run():
    plan = MachinePlan(RemoteTarget("k", "hpc"), RemotePlan("hpc", "", (), "Réparer : …\n", "", False, True, True,
                                                            True, ("sudo chmod 0640 /x",)), (), Purpose.REPAIR)
    text = render_machine_plan(plan)
    assert "« Réparer hpc »" in text and "lancées AUSSI sur hpc" in text and "      sudo chmod 0640 /x" in text
    assert plan.needs_work


def test_system_clipboard_tools_in_order_and_none_without_display(tmp_path):
    """« Il faut que l'utilisateur puisse le faire quel que soit son presse-papiers » : wl-copy (Wayland), xclip,
    xsel (X11) ; rien sans affichage graphique (l'interface affiche alors les commandes en clair)."""
    from omega_connect.infrastructure.clipboard.system import copy_text

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("xsel", "wl-copy"):
        tool = bin_dir / name
        tool.write_text(f'#!/bin/sh\n/bin/cat > "{tmp_path}/{name}.txt"\n', encoding="utf-8")
        tool.chmod(0o755)
    env = {"PATH": str(bin_dir), "DISPLAY": ":0"}
    assert copy_text("sudo x\n", env) == "xsel"  # pas de xclip ici : xsel
    assert (tmp_path / "xsel.txt").read_text(encoding="utf-8") == "sudo x\n"
    assert copy_text("sudo y\n", {**env, "WAYLAND_DISPLAY": "wayland-0"}) == "wl-copy"
    assert copy_text("sudo z\n", {"PATH": str(bin_dir)}) == ""  # ni DISPLAY ni WAYLAND_DISPLAY


def test_repair_runs_announced_manual_commands_only(tmp_path, monkeypatch):
    """Retour de l'auteur : « un bouton Réparer et ça lance directement la commande distante ». Seules les commandes
    ANNONCEES et encore necessaires sont lancees ; une commande nouvelle (non annoncee) ne l'est jamais."""
    from omega_connect.app import remote_agent
    from omega_connect.infrastructure.remote import apply_update

    session = tmp_path / "s"
    session.mkdir()
    (session / "updates.json").write_text(json.dumps(updates_to_dict(
        (), Purpose.REPAIR, ("sudo chmod 0640 /a", "sudo chmod 0640 /b"))), encoding="utf-8")
    ran: list[str] = []
    monkeypatch.setattr(remote_agent, "_cli", lambda argv: 0)
    monkeypatch.setattr(remote_agent, "_current_manual", lambda: ("sudo chmod 0640 /a", "sudo rm -rf /nouveau"))
    monkeypatch.setattr(apply_update, "run_shell", lambda command: (ran.append(command), 0)[1])
    assert remote_agent.main(["run", str(session)]) == 0
    assert ran == ["sudo chmod 0640 /a"]  # /b deja regle ; /nouveau jamais annonce : jamais lance
    result = result_from_dict(json.loads((session / "result.json").read_text(encoding="utf-8")))
    assert result is not None and [(step.name, step.detail) for step in result.steps] == [
        (StepName.REPAIR, ""), (StepName.MANUAL, "sudo chmod 0640 /a")]


def test_problems_list_every_machine_and_who_fixes_it():
    """Retour de l'auteur : « dans Réparer, la liste de tout ce qui ne va pas, et là on choisit »."""
    from omega_connect.domain.fleet import AppState, RegistryRow
    from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind, Repair, RepairKind
    from omega_connect.domain.parc import MachineEntry
    from omega_connect.domain.problems import ProblemKind, problems

    fixable = Link(LinkKind.TOKENS, "", "", (Check(CheckCode.TOKEN_RIGHTS, CheckStatus.WARNING, "/j", "0600",
                                                   repair=Repair(RepairKind.TOKEN, "/r", "omega-serv")),))
    manual = Link(LinkKind.BLOCKLIST, "omega-serv", "/r", (Check(CheckCode.BLOCKLIST_MODE, CheckStatus.FAILURE, "/b",
                                                                 fix="sudo chmod 0660 /b"),), machine="craftdark")
    ok = Link(LinkKind.ZONE, "", "", (Check(CheckCode.TOKEN_OK, CheckStatus.OK),))
    old = RegistryRow("craftdark", "omega-jail", "/h/j", "", "", "1.1.0", AppState.OLD_VERSION)
    craftdark = MachineEntry("craftdark", False, "2026-11-11T00:00:00Z", (old,), "f" * 16, ("192.168.1.103",),
                             "k@192.168.1.103", links=(manual,))
    down = MachineEntry("hpc", False, "", (), "e" * 16, ("192.168.1.109",), "k@192.168.1.109", reachable=False)
    found = problems("vpc", (fixable, ok), (), (craftdark, down))
    assert [(item.machine, item.kind) for item in found] == [
        ("vpc", ProblemKind.REPAIR), ("craftdark (192.168.1.103)", ProblemKind.UPDATE),
        ("craftdark (192.168.1.103)", ProblemKind.REPAIR), ("hpc (192.168.1.109)", ProblemKind.UNREACHABLE)]
    assert found[0].by_tool and found[0].local and not found[2].by_tool and found[2].blocking
    assert found[2].target == "k@192.168.1.103"
