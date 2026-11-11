# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lot R2 : scanner distant. Aucun reseau : un faux `ssh` (script place devant) simule machine inconnue, clef
changee, machine eteinte, cles refusees — et, pour une machine normale, execute VRAIMENT la commande distante en
local, avec le Python du systeme isole (ni venv, ni rich, ni textual), sur une fausse machine (HOME, /etc, zone
temporaires). Le vrai ~/.ssh/known_hosts n'est jamais touche."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import make_installation, sheet_for

from omega_connect.application.remote_actions import RemoteTools, failed, scan_remote
from omega_connect.domain.fleet import AppState, RegistryRow
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind, Provenance
from omega_connect.domain.parc import MachineEntry, entry_after_failure, entry_from_scan
from omega_connect.domain.remote import (
    HostCheck,
    HostKey,
    RemoteFailure,
    RemoteScan,
    RemoteTarget,
    parse_target,
    scan_from_dict,
    scan_to_dict,
)
from omega_connect.infrastructure.remote.ssh import SshRemoteScanner, classify
from omega_connect.interfaces.cli.main import run

# ---- regles pures ------------------------------------------------------------------------------

@pytest.mark.parametrize(("text", "expected"), [
    ("kraynux@hpc-109", RemoteTarget("kraynux", "hpc-109")),
    ("hpc-109.local", RemoteTarget("", "hpc-109.local")),
    ("kraynux@192.168.1.109", RemoteTarget("kraynux", "192.168.1.109")),
    ("root@[fe80::1]", RemoteTarget("root", "fe80::1")),
    ("-oProxyCommand=sh", None),
    ("kraynux@-oProxyCommand=sh", None),
    ("kray nux@hpc", None),
    ("kraynux@hpc;rm", None),
    ("", None),
])
def test_targets_never_become_ssh_options(text, expected):
    assert parse_target(text) == expected


def _scan(fingerprint: str = "f" * 16, hostname: str = "hpc-109") -> RemoteScan:
    row = RegistryRow(hostname, "omega-serv", "/srv/omega-serv", "omega-serv", "active", "2.6.1", AppState.ENROLLED)
    link = Link(LinkKind.BLOCKLIST, "omega-serv", "/srv/omega-serv",
                (Check(CheckCode.BLOCKLIST_OK, CheckStatus.OK, "/srv/omega-serv/var/b.json"),), machine=hostname)
    return RemoteScan(hostname, fingerprint, "2026-11-10T20:00:00Z", (row,), (link,))


def test_scan_document_round_trip_and_future_versions_refused():
    data = scan_to_dict(_scan())
    again = scan_from_dict(data)
    assert again == _scan()
    assert again.links[0].provenance is Provenance.NETWORK
    assert scan_from_dict({**data, "schema_version": 99}) is None
    assert scan_from_dict({"format": "autre"}) is None


def test_one_machine_two_networks_and_two_machines_one_address():
    """Reponse a l'auteur : l'identite est l'empreinte, jamais l'adresse."""
    lan, tailscale = RemoteTarget("k", "192.168.1.109"), RemoteTarget("k", "100.64.0.9")
    first = entry_from_scan((), _scan(), lan)
    second = entry_from_scan((first,), _scan(), tailscale)
    assert second.addresses == ("192.168.1.109", "100.64.0.9")
    assert second.label == "hpc-109 (192.168.1.109, 100.64.0.9)"
    other = entry_from_scan((second,), _scan("e" * 16, "bureau"), lan)  # meme adresse, autre reseau
    assert other.addresses == ("192.168.1.109",) and other.key != second.key


def test_a_known_machine_that_stops_answering_keeps_its_rows():
    entry = entry_from_scan((), _scan(), RemoteTarget("k", "hpc-109"))
    down = entry_after_failure((entry,), RemoteTarget("k", "hpc-109"), RemoteFailure.UNREACHABLE)
    assert down is not None and not down.reachable
    assert [row.state for row in down.shown_rows()] == [AppState.UNREACHABLE]
    assert entry_after_failure((), RemoteTarget("k", "inconnue"), RemoteFailure.UNREACHABLE) is None


@pytest.mark.parametrize(("code", "stderr", "expected"), [
    (255, b"@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED! @\nHost key verification failed.",
     RemoteFailure.CHANGED_HOST),
    (255, b"Host key verification failed.", RemoteFailure.UNKNOWN_HOST),
    (255, b"k@h: Permission denied (publickey).", RemoteFailure.AUTHENTICATION),
    (255, b"ssh: connect to host h port 22: Connection refused", RemoteFailure.NO_SSH_SERVER),
    (255, b"ssh: Could not resolve hostname hpc-109: Name or service not known", RemoteFailure.UNKNOWN_NAME),
    (255, b"ssh: connect to host h port 22: Connection timed out", RemoteFailure.UNREACHABLE),
    (127, b"sh: python3: not found", RemoteFailure.NO_PYTHON),
    (1, b"Traceback ...", RemoteFailure.SCAN_FAILED),
    (0, b"", None),
])
def test_failures_are_classified(code, stderr, expected):
    assert classify(code, stderr) is expected


# ---- faux ssh : de bout en bout sans reseau -----------------------------------------------------

FAKE_SSH = """#!/bin/bash
args=("$@"); target=""; cmd=""
for ((i=0; i<${#args[@]}; i++)); do
  if [ "${args[$i]}" = "--" ]; then target="${args[$((i+1))]}"; cmd="${args[$((i+2))]}"; break; fi
done
echo "$target" >> "{log}"
case "$target" in
  *inconnue*)
    if grep -q "^inconnue " "{known}" 2>/dev/null; then exec sh -c "$cmd"; fi
    for a in "$@"; do case "$a" in UserKnownHostsFile=*) echo "inconnue $(cat {pub})" > "${a#UserKnownHostsFile=}"; exit 0;; esac; done
    echo "Host key verification failed." >&2; exit 255;;
  *changee*) echo "@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED! @" >&2; echo "Host key verification failed." >&2; exit 255;;
  *eteinte*) echo "ssh: connect to host eteinte port 22: Connection refused" >&2; exit 255;;
  *refus*) echo "k@refus: Permission denied (publickey)." >&2; exit 255;;
  *archcraft*) PATH=/usr/share/archcraft/scripts exec /bin/sh -c "$cmd";;
esac
exec sh -c "$cmd"
"""


@pytest.fixture
def fake_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_system) -> dict[str, Path]:
    if shutil.which("ssh-keygen") is None or shutil.which("python3") is None:
        pytest.skip("ssh-keygen et python3 requis")
    key = tmp_path / "hostkey"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "ssh.log"
    ssh = bin_dir / "ssh"
    known_hosts = tmp_path / "dot-ssh" / "known_hosts"
    ssh.write_text(FAKE_SSH.replace("{log}", str(log)).replace("{pub}", f"{key}.pub")
                   .replace("{known}", str(known_hosts)), encoding="utf-8")
    ssh.chmod(0o755)
    # La « machine distante » : un HOME avec omega-serv, des dossiers systeme vides.
    make_installation(fake_system["home"] / "omega-serv", "omega-serv", token_id="c" * 32,
                      sheet=sheet_for("omega-serv", "omega-serv"))
    monkeypatch.setenv("HOME", str(fake_system["home"]))
    monkeypatch.setenv("OMEGA_CONNECT_HOME", str(fake_system["home"]))  # jamais le vrai dossier personnel
    monkeypatch.delenv("SUDO_USER", raising=False)
    for name, key_name in (("OMEGA_CONNECT_SYSTEMD_DIR", "systemd"), ("OMEGA_CONNECT_OPENRC_DIR", "openrc"),
                           ("OMEGA_CONNECT_RUNIT_DIR", "runit"), ("OMEGA_CONNECT_SRV_DIR", "srv")):
        monkeypatch.setenv(name, str(fake_system[key_name]))
    monkeypatch.setenv("OMEGA_CONNECT_FAIL2BAN_DIR", str(tmp_path / "fail2ban-absent"))
    return {"ssh": ssh, "log": log, "known_hosts": known_hosts}


class _Parc:
    def __init__(self) -> None:
        self.machines: list[MachineEntry] = []

    def load(self) -> tuple[MachineEntry, ...]:
        return tuple(self.machines)

    def save(self, machine: MachineEntry) -> None:
        self.machines = [entry for entry in self.machines if entry.key != machine.key] + [machine]

    def remove(self, key: str) -> bool:
        before = len(self.machines)
        self.machines = [entry for entry in self.machines if entry.key != key]
        return len(self.machines) != before


def _scanner(fake_remote) -> SshRemoteScanner:
    return SshRemoteScanner(ssh=str(fake_remote["ssh"]), known_hosts=fake_remote["known_hosts"], scan_timeout=90)


def test_end_to_end_scan_runs_in_memory_with_an_isolated_python(fake_remote):
    scanner = _scanner(fake_remote)
    target = RemoteTarget("k", "hpc-109")
    assert scanner.check_host(target).key is HostKey.KNOWN
    parc = _Parc()
    outcome = scan_remote(target, RemoteTools(scanner, parc))
    assert outcome.ok, outcome.detail
    assert outcome.scan is not None and [row.tool for row in outcome.scan.rows] == ["omega-serv"]
    assert outcome.scan.rows[0].state is AppState.ENROLLED  # carte presente, pas encore d'espace partage
    assert all(link.provenance is Provenance.NETWORK for link in outcome.scan.links)
    assert parc.machines[0].addresses == ("hpc-109",) and parc.machines[0].target == "k@hpc-109"
    assert not fake_remote["known_hosts"].exists()


def test_unknown_machine_is_trusted_only_after_consent(fake_remote):
    scanner = _scanner(fake_remote)
    check = scanner.check_host(RemoteTarget("k", "inconnue"))
    assert check.key is HostKey.UNKNOWN and check.fingerprints and "SHA256:" in check.fingerprints[0]
    assert not fake_remote["known_hosts"].exists()  # rien d'ecrit avant l'accord
    assert scanner.trust(check)
    content = fake_remote["known_hosts"].read_text(encoding="utf-8")
    assert content.startswith("inconnue ssh-ed25519 ")
    assert oct(fake_remote["known_hosts"].stat().st_mode & 0o777) == "0o600"


@pytest.mark.parametrize(("host", "key", "failure"), [
    ("changee", HostKey.CHANGED, RemoteFailure.CHANGED_HOST),
    ("eteinte", HostKey.FAILED, RemoteFailure.NO_SSH_SERVER),
])
def test_changed_or_unreachable(fake_remote, host, key, failure):
    check = _scanner(fake_remote).check_host(RemoteTarget("k", host))
    assert check.key is key and check.failure is failure


def test_refused_keys_are_said_at_scan(fake_remote):
    scanner = _scanner(fake_remote)
    assert scanner.check_host(RemoteTarget("k", "refus")).key is HostKey.KNOWN
    assert scanner.scan(RemoteTarget("k", "refus"))[0] is RemoteFailure.AUTHENTICATION  # type: ignore[index]


def test_cli_scanner_remote_with_trust_question(fake_remote, capsys, tmp_path):
    from zone_fakes import FakeSystem

    from omega_connect.application.zone_actions import ZoneTools

    system = FakeSystem(tmp_path / "machine")
    terminal = ZoneTools(inspector=system, runner=system, subject=None, now=lambda: "",  # type: ignore[arg-type]
                         interactive=lambda: True)
    parc = _Parc()
    tools = RemoteTools(_scanner(fake_remote), parc)
    answers = iter(["o"])
    code = run(["scanner", "k@inconnue"], lambda _request: None, zone=terminal,  # type: ignore[arg-type,return-value]
               remote=tools, ask=lambda _question: next(answers))
    out = capsys.readouterr()
    assert "SHA256:" in out.out and "n'a jamais été jointe" in out.out
    assert code == 0 and "1 application(s) omega trouvée(s)" in out.out
    assert run(["scanner", "k@changee"], lambda _request: None, remote=tools) == 1  # type: ignore[arg-type,return-value]
    assert "a CHANGÉ" in capsys.readouterr().err
    assert run(["scanner", "--", "-oProxyCommand=x"], lambda _request: None,  # type: ignore[arg-type,return-value]
               remote=tools) == 2
    no_terminal = run(["scanner", "k@inconnue"], lambda _request: None, remote=tools)  # type: ignore[arg-type,return-value]
    assert no_terminal == 0  # deja acceptee : plus de question


def test_failed_marks_only_known_machines(fake_remote):
    parc = _Parc()
    tools = RemoteTools(_scanner(fake_remote), parc)
    assert scan_remote(RemoteTarget("k", "hpc-109"), tools).ok
    outcome = failed(RemoteTarget("k", "hpc-109"), RemoteFailure.UNREACHABLE, "", tools)
    assert outcome.entry is not None and not parc.machines[0].reachable
    assert failed(RemoteTarget("k", "jamais-vue"), RemoteFailure.UNREACHABLE, "", tools).entry is None


def test_host_check_model():
    check = HostCheck(RemoteTarget("k", "h"), HostKey.UNKNOWN, ("256 SHA256:x h (ED25519)",), b"h ssh-ed25519 AAAA\n")
    assert check.target.text == "k@h"


# ---- machines deja joignables (Unison, ~/.ssh/config, known_hosts) ----------------------------

def test_suggestions_from_unison_ssh_config_and_known_hosts(tmp_path):
    from omega_connect.domain.remote import SuggestionSource
    from omega_connect.infrastructure.remote.suggestions import LocalSuggestions

    home = tmp_path / "home"
    (home / ".unison").mkdir(parents=True)
    (home / ".ssh").mkdir()
    (home / ".unison" / "107-109.prf").write_text(
        "root = /home/k/Documents\nroot = ssh://kraynux@192.168.1.109//home/kraynux/Documents\n", encoding="utf-8")
    (home / ".unison" / "monte.prf").write_text("root = /mnt/hpc\n", encoding="utf-8")  # pas SSH : ignore
    (home / ".ssh" / "config").write_text("Host serveur-perso\n  HostName 10.0.0.5\n  User admin\nHost *\n",
                                          encoding="utf-8")
    (home / ".ssh" / "known_hosts").write_text(
        "192.168.1.109 ssh-ed25519 AAAA\n192.168.1.103,poste ssh-ed25519 AAAA\n[192.168.1.50]:2222 ssh-rsa AAAA\n"
        "|1|haché= ssh-ed25519 AAAA\nlocalhost ssh-ed25519 AAAA\n# commentaire\n", encoding="utf-8")
    found = {item.target.text: item.sources for item in LocalSuggestions(home, "moi")()}
    assert found["kraynux@192.168.1.109"] == (SuggestionSource.UNISON, SuggestionSource.KNOWN_HOSTS)
    assert found["serveur-perso"] == (SuggestionSource.SSH_CONFIG,)  # ~/.ssh/config regle l'utilisateur
    assert found["moi@192.168.1.103"] == (SuggestionSource.KNOWN_HOSTS,)
    assert "moi@poste" in found and "moi@192.168.1.50" in found
    assert not any("localhost" in name or "|1|" in name for name in found)
    assert list(found)[0] == "kraynux@192.168.1.109"  # Unison d'abord : ces acces marchent deja


def test_cli_lists_suggestions(fake_remote, capsys):
    from omega_connect.domain.remote import Suggestion, SuggestionSource

    tools = RemoteTools(_scanner(fake_remote), _Parc(),
                        lambda: (Suggestion(RemoteTarget("k", "hpc-109"), (SuggestionSource.UNISON,)),))
    assert run(["scanner", "--liste"], lambda _request: None, remote=tools) == 0  # type: ignore[arg-type,return-value]
    out = capsys.readouterr().out
    assert "k@hpc-109" in out and "Unison" in out and "jamais scannée" in out


def test_a_remote_shell_that_replaces_path_still_finds_python(fake_remote):
    """cpc-103 (Archcraft) : zsh y remplace le PATH des connexions sans terminal ; python3 est dans /usr/bin."""
    scan = _scanner(fake_remote).scan(RemoteTarget("k", "archcraft"))
    assert isinstance(scan, RemoteScan), scan


def test_store_and_cli_forget_a_machine(tmp_path, fake_remote, capsys):
    from omega_connect.infrastructure.fleet.parc_store import FileParcStore

    store = FileParcStore(tmp_path / "var")
    tools = RemoteTools(_scanner(fake_remote), store)
    assert scan_remote(RemoteTarget("k", "hpc-109"), tools).ok
    store.save(MachineEntry("local", True, "x"))
    assert run(["scanner", "--retirer", "rien"], lambda _request: None, remote=tools) == 2  # type: ignore[arg-type,return-value]
    assert run(["scanner", "--retirer", "k@hpc-109"], lambda _request: None, remote=tools) == 0  # type: ignore[arg-type,return-value]
    assert "retirée du registre" in capsys.readouterr().out
    assert [machine.name for machine in store.load()] == ["local"]  # la machine locale ne se retire jamais
    assert not store.remove("local")
