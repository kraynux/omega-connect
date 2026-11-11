# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fiche demandee a l'outil et detection complete (lot A), sur de fausses installations uniquement."""
from __future__ import annotations

import json
import os
import pwd

from conftest import make_installation, sheet_for
from omega_lib.synchro.models import ReadStatus

from omega_connect.app.main import build_detect
from omega_connect.infrastructure.detection.sheet_fetcher import SubprocessSheetFetcher
from omega_connect.interfaces.cli.main import DetectRequest, run


def test_sheet_is_read_from_the_launcher(tmp_path):
    root = make_installation(tmp_path / "omega-serv", "omega-serv", sheet=sheet_for("omega-serv", "omega-serv-blog"))
    result = SubprocessSheetFetcher().fetch(str(root), "omega-serv")
    assert result.status is ReadStatus.OK and result.sheet is not None
    assert result.sheet.instance == "omega-serv-blog"


def test_sheet_failures_are_states(tmp_path):
    old = make_installation(tmp_path / "ancien", "omega-serv", exit_code=2)
    assert SubprocessSheetFetcher().fetch(str(old), "omega-serv").status is ReadStatus.ABSENT
    broken = make_installation(tmp_path / "casse", "omega-fire")
    (broken / "omega-fire.sh").write_text("#!/bin/sh\necho 'pas du json'\n")
    assert SubprocessSheetFetcher().fetch(str(broken), "omega-fire").status is ReadStatus.INVALID
    slow = make_installation(tmp_path / "lent", "omega-fire")
    (slow / "omega-fire.sh").write_text("#!/bin/sh\nsleep 5\n")
    result = SubprocessSheetFetcher(timeout=0.3).fetch(str(slow), "omega-fire")
    assert result.status is ReadStatus.UNREADABLE and "no answer" in result.detail


def test_unsafe_launcher_is_never_run(tmp_path):
    root = make_installation(tmp_path / "omega-serv", "omega-serv")
    marker = tmp_path / "lance"
    (root / "omega-serv.sh").write_text(f"#!/bin/sh\ntouch {marker}\n")
    (root / "omega-serv.sh").chmod(0o775)  # modifiable par le groupe
    result = SubprocessSheetFetcher().fetch(str(root), "omega-serv")
    assert result.status is ReadStatus.UNREADABLE and "writable" in result.detail
    assert not marker.exists()


def test_never_runs_as_root_and_never_for_another_account(tmp_path):
    root = make_installation(tmp_path / "omega-serv", "omega-serv")
    owner = pwd.getpwuid(root.stat().st_uid).pw_name
    command, _refusal = SubprocessSheetFetcher(euid=0).command(str(root), "omega-serv")
    assert command is not None and command[:4] == ["runuser", "-u", owner, "--"]
    command, refusal = SubprocessSheetFetcher(euid=os.getuid() + 1).command(str(root), "omega-serv")
    assert command is None and "another account" in refusal


def _detect(fake_system):
    return build_detect(home=fake_system["home"], systemd_dir=str(fake_system["systemd"]),
                        openrc_dir=str(fake_system["openrc"]), runit_dir=str(fake_system["runit"]),
                        srv_dir=str(fake_system["srv"]), mounts_file=str(fake_system["mounts"]))


def test_several_serv_instances_each_with_its_own_token(fake_system):
    home = fake_system["home"]
    main = make_installation(home / "omega-serv", "omega-serv", token_id="a" * 32,
                             sheet=sheet_for("omega-serv", "omega-serv"))
    blog = make_installation(fake_system["srv"] / "blog", "omega-serv", token_id="b" * 32,
                             sheet=sheet_for("omega-serv", "omega-serv-blog"))
    (fake_system["systemd"] / "omega-serv-blog.service").write_text(
        f"ExecStart={blog}/.venv/bin/python -m omega_serv --config {blog}/config/omega-serve.json serve\n")
    report = _detect(fake_system)(DetectRequest([], with_sheets=True))
    by_root = {item.root: item for item in report.installations}
    assert set(by_root) == {str(main), str(blog)}
    assert by_root[str(blog)].installation_id == "b" * 32
    assert by_root[str(blog)].sheet.sheet.instance == "omega-serv-blog"
    assert by_root[str(blog)].service_names == ("omega-serv-blog",)
    assert report.duplicates == ()


def test_copied_folder_is_reported_as_duplicate(fake_system):
    home = fake_system["home"]
    make_installation(home / "omega-serv", "omega-serv", token_id="c" * 32)
    make_installation(home / "omega-serv-copie", "omega-serv", token_id="c" * 32)
    report = _detect(fake_system)(DetectRequest([], with_sheets=False))
    assert len(report.installations) == 2 and len(report.duplicates) == 1


def test_cli_json_and_text(fake_system, capsys):
    make_installation(fake_system["home"] / "omega-jail", "omega-jail")
    assert run(["detecter", "--format", "json", "--sans-fiche"], _detect(fake_system)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "omega-connect-detection"
    assert payload["installations"][0]["tool"] == "omega-jail"
    assert payload["installations"][0]["token_status"] == "absent"
    assert run(["detecter", "--sans-fiche"], _detect(fake_system)) == 0
    text = capsys.readouterr().out
    assert "jeton : absent" in text and "synchro jeton" in text and "1 installation(s)" in text


def test_nothing_found(fake_system, capsys):
    assert run(["detecter"], _detect(fake_system)) == 0
    assert "Aucun outil omega trouvé" in capsys.readouterr().out


def test_a_tool_can_never_reach_the_terminal(tmp_path):
    """Ancien outil qui s'eleve avec sudo (omega-fire sans `synchro`, constate le 2026-11-10) : sudo ouvre /dev/tty
    directement. La fiche est demandee sans terminal de controle : /dev/tty ne s'ouvre pas, aucune invite possible.
    Le test tourne dans un pseudo-terminal pour que le processus parent, lui, ait bien un terminal."""
    import pty

    root = make_installation(tmp_path / "omega-fire-bak", "omega-fire")
    marker = tmp_path / "terminal"
    (root / "omega-fire.sh").write_text(
        "#!/bin/sh\n"
        f"if (exec 3</dev/tty) 2>/dev/null; then echo atteint > {marker}; else echo inaccessible > {marker}; fi\n"
        "exit 1\n")
    pid, fd = pty.fork()
    if pid == 0:  # enfant : a un terminal de controle (le pseudo-terminal)
        try:
            control = "atteint" if os.open("/dev/tty", os.O_RDONLY) >= 0 else "?"
            (tmp_path / "parent").write_text(control)
            SubprocessSheetFetcher().fetch(str(root), "omega-fire")
        finally:
            os._exit(0)
    while True:
        try:
            if not os.read(fd, 1024):
                break
        except OSError:
            break
    os.waitpid(pid, 0)
    assert (tmp_path / "parent").read_text() == "atteint"
    assert marker.read_text().strip() == "inaccessible"
