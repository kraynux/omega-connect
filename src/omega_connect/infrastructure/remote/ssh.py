# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Transport SSH du scanner distant (lot R2 ; decisions Q1/Q2 de la refonte, §14 de l'etude).

- vos cles seulement : `BatchMode=yes`, jamais de mot de passe tape dans omega-connect (agent SSH pour une cle
  protegee) ; `~/.ssh/config` respecte (alias, port, utilisateur) ;
- clef de machine verifiee AVANT : connue -> scan ; inconnue -> lue dans un fichier temporaire, empreintes montrees,
  ajoutee a `~/.ssh/known_hosts` seulement apres accord ; CHANGEE -> refus ;
- rien d'installe : la commande distante est une seule ligne, `python3 -I -c '<lire et executer l'amorce>'` ;
  l'amorce puis l'archive du scanner arrivent par l'entree standard (aucun fichier ecrit la-bas, aucun guillemet
  imbrique, quel que soit le shell distant) ;
- delais : connexion 10 s, scan 60 s ; sortie limitee a 4 Mo."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from omega_connect.domain.remote import (
    MAX_SCAN_BYTES,
    HostCheck,
    HostKey,
    RemoteFailure,
    RemoteScan,
    RemoteTarget,
    scan_from_dict,
)
from omega_connect.domain.updates import RemotePlan, RemoteResult, plan_from_dict, result_from_dict
from omega_connect.infrastructure.remote.payload import BOOTSTRAP, build_payload

CONNECT_TIMEOUT_SECONDS = 10
SCAN_TIMEOUT_SECONDS = 60
UPLOAD_TIMEOUT_SECONDS = 300
REMOTE_COMMAND = ("PATH=/usr/local/bin:/usr/bin:/bin:$PATH "
                  "python3 -I -c 'import sys;exec(sys.stdin.buffer.read(int(sys.stdin.buffer.readline())))'")
"""Seule commande envoyee : lit la longueur de l'amorce, l'amorce, et l'execute (elle lit ensuite l'archive).
Dossiers standards en tete du PATH : constate le 2026-11-10 sur cpc-103 (Archcraft), dont la configuration zsh
REMPLACE le PATH des connexions sans terminal par /usr/share/archcraft/scripts — python3 « introuvable » alors
qu'il est dans /usr/bin."""
UNKNOWN_NAME_MARKS = ("could not resolve", "name or service not known", "nodename nor servname")
UNREACHABLE_MARKS = ("timed out", "no route to host", "network is unreachable", "connection closed",
                     "connection reset", "host is down")


def _last_line(text: bytes) -> str:
    lines = [line.strip() for line in text.decode("utf-8", errors="replace").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def classify(code: int, stderr: bytes) -> RemoteFailure | None:
    text = stderr.decode("utf-8", errors="replace").lower()
    if "remote host identification has changed" in text:
        return RemoteFailure.CHANGED_HOST
    if "host key verification failed" in text:
        return RemoteFailure.UNKNOWN_HOST
    if "permission denied" in text or "too many authentication failures" in text:
        return RemoteFailure.AUTHENTICATION
    if any(mark in text for mark in UNKNOWN_NAME_MARKS):
        return RemoteFailure.UNKNOWN_NAME
    if "connection refused" in text:
        return RemoteFailure.NO_SSH_SERVER
    if any(mark in text for mark in UNREACHABLE_MARKS) or code == 255:
        return RemoteFailure.UNREACHABLE
    if code == 127 or "python3: not found" in text or "python >= 3.10" in text or "command not found" in text:
        return RemoteFailure.NO_PYTHON
    return None if code == 0 else RemoteFailure.SCAN_FAILED


class SshRemoteScanner:
    def __init__(self, *, ssh: str = "ssh", keygen: str = "ssh-keygen", known_hosts: Path | None = None,
                 connect_timeout: int = CONNECT_TIMEOUT_SECONDS, scan_timeout: int = SCAN_TIMEOUT_SECONDS) -> None:
        self._ssh = ssh
        self._keygen = keygen
        self._known_hosts = known_hosts or Path.home() / ".ssh" / "known_hosts"
        self._connect_timeout = connect_timeout
        self._scan_timeout = scan_timeout

    def _command(self, target: RemoteTarget, *options: str, remote: str = "true") -> list[str]:
        return [self._ssh, "-o", "BatchMode=yes", "-o", f"ConnectTimeout={self._connect_timeout}",
                "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2", *options, "--", target.text, remote]

    def _run(self, command: list[str], data: bytes = b"", timeout: float | None = None) -> tuple[int, bytes, bytes]:
        try:
            done = subprocess.run(command, input=data, capture_output=True, check=False,  # noqa: S603
                                  timeout=timeout or self._connect_timeout + 5, start_new_session=True)
        except subprocess.TimeoutExpired:
            return 124, b"", b"timed out"
        except OSError as error:
            return 127, b"", str(error).encode()
        return done.returncode, done.stdout, done.stderr

    def check_host(self, target: RemoteTarget) -> HostCheck:
        if shutil.which(self._ssh) is None:
            return HostCheck(target, HostKey.FAILED, failure=RemoteFailure.NO_SSH, detail=self._ssh)
        code, _out, error = self._run(self._command(target, "-o", "StrictHostKeyChecking=yes"))
        failure = classify(code, error)
        if failure is None or failure is RemoteFailure.AUTHENTICATION:
            # Clef connue (la connexion a depasse la verification de la machine) ; l'authentification est jugee
            # au scan.
            return HostCheck(target, HostKey.KNOWN)
        if failure is RemoteFailure.CHANGED_HOST:
            return HostCheck(target, HostKey.CHANGED, failure=failure, detail=_last_line(error))
        if failure is not RemoteFailure.UNKNOWN_HOST:
            return HostCheck(target, HostKey.FAILED, failure=failure, detail=_last_line(error))
        return self._unknown(target)

    def _unknown(self, target: RemoteTarget) -> HostCheck:
        """Clef lue dans un fichier temporaire (jamais dans le vrai known_hosts avant l'accord)."""
        directory = tempfile.mkdtemp(prefix="omega-connect-hote-")
        try:
            pending_file = Path(directory) / "known_hosts"
            code, _out, error = self._run(self._command(
                target, "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={pending_file}",
                "-o", "GlobalKnownHostsFile=/dev/null"))
            pending = pending_file.read_bytes() if pending_file.exists() else b""
            if not pending:
                return HostCheck(target, HostKey.FAILED, failure=classify(code, error) or RemoteFailure.UNREACHABLE,
                                 detail=_last_line(error))
            done = subprocess.run([self._keygen, "-l", "-f", str(pending_file)], capture_output=True,  # noqa: S603
                                  check=False, timeout=10)
            fingerprints = tuple(line.strip() for line in done.stdout.decode("utf-8", errors="replace").splitlines()
                                 if line.strip())
            return HostCheck(target, HostKey.UNKNOWN, fingerprints, pending)
        except (OSError, subprocess.TimeoutExpired) as error:
            return HostCheck(target, HostKey.FAILED, failure=RemoteFailure.UNREACHABLE, detail=str(error))
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def trust(self, check: HostCheck) -> bool:
        if check.key is not HostKey.UNKNOWN or not check.pending:
            return False
        try:
            self._known_hosts.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(self._known_hosts, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(descriptor, "ab") as handle:
                handle.write(check.pending if check.pending.endswith(b"\n") else check.pending + b"\n")
        except OSError:
            return False
        return True

    def scan(self, target: RemoteTarget) -> RemoteScan | tuple[RemoteFailure, str]:
        if shutil.which(self._ssh) is None:
            return RemoteFailure.NO_SSH, self._ssh
        bootstrap = BOOTSTRAP.encode("utf-8")
        data = str(len(bootstrap)).encode() + b"\n" + bootstrap + build_payload()
        code, out, error = self._run(self._command(target, "-o", "StrictHostKeyChecking=yes", remote=REMOTE_COMMAND),
                                     data, timeout=self._connect_timeout + self._scan_timeout)
        failure = classify(code, error)
        if failure is not None:
            return failure, _last_line(error)
        if len(out) > MAX_SCAN_BYTES:
            return RemoteFailure.SCAN_FAILED, "answer too large"
        try:
            scan = scan_from_dict(json.loads(out.decode("utf-8")))
        except (UnicodeDecodeError, ValueError):
            scan = None
        return scan if scan is not None else (RemoteFailure.SCAN_FAILED, "unexpected answer")


# ---- lot R3 : plan, puis lancement dans un terminal --------------------------------------------------

SESSION_DIRECTORY = re.compile(r"^/[A-Za-z0-9._/-]*/omega-connect\.[A-Za-z0-9]{8,}$")
"""Dossier prive cree par `mktemp` sur la machine distante ; tout autre texte est refuse (il est repris dans une
commande)."""
STANDARD_PATH = "/usr/local/bin:/usr/bin:/bin"
PATH_PREFIX = f"PATH={STANDARD_PATH}:$PATH; "
"""En tete de CHAQUE commande distante : constate le 2026-11-11 sur craftdark (Archcraft), le PATH des connexions
sans terminal ne contient que /usr/share/archcraft/scripts — `cat` et `rm` introuvables, resultat jamais relu."""
PREPARE_SCRIPT = (PATH_PREFIX + 'umask 077; '
                  'find "${TMPDIR:-/tmp}" -maxdepth 1 -name "omega-connect.*" -type d -user "$(id -u)" -mmin +120 '
                  '-exec rm -rf {} + 2>/dev/null; '
                  'd=$(mktemp -d -t omega-connect.XXXXXXXX) || exit 70; '
                  'cd "$d" && tar -xf - || { rm -rf "$d"; exit 71; }; printf "%s\\n" "$d"')
"""Execute par `/bin/sh -c` : identique quel que soit le shell de connexion (bash, zsh, fish...). Efface d'abord
les dossiers de session de ce compte vieux de plus de 2 h (session interrompue : coupure, terminal ferme)."""


def _sh(script: str) -> str:
    if "'" in script:
        raise ValueError("script")
    return f"/bin/sh -c '{script}'"


def bundle(files: dict[str, bytes]) -> bytes:
    """Fichiers de la session dans une archive tar (noms simples, droits 0600)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content in files.items():
            if "/" in name or name.startswith("."):
                raise ValueError(name)
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


class SshRemoteSession(SshRemoteScanner):
    """Plan (lecture seule, sans terminal) et lancement dans un terminal (`ssh -t`), dossier prive efface."""

    def plan(self, target: RemoteTarget) -> RemotePlan | tuple[RemoteFailure, str]:
        if shutil.which(self._ssh) is None:
            return RemoteFailure.NO_SSH, self._ssh
        bootstrap = BOOTSTRAP.encode("utf-8")
        data = str(len(bootstrap)).encode() + b"\n" + bootstrap + build_payload()
        code, out, error = self._run(self._command(target, "-o", "StrictHostKeyChecking=yes",
                                                   remote=REMOTE_COMMAND + " plan"),
                                     data, timeout=self._connect_timeout + self._scan_timeout)
        failure = classify(code, error)
        if failure is not None:
            return failure, _last_line(error)
        try:
            plan = plan_from_dict(json.loads(out.decode("utf-8")))
        except (UnicodeDecodeError, ValueError):
            plan = None
        return plan if plan is not None else (RemoteFailure.SCAN_FAILED, "unexpected answer")

    def prepare(self, target: RemoteTarget, files: dict[str, bytes]) -> str | tuple[RemoteFailure, str]:
        code, out, error = self._run(self._command(target, "-o", "StrictHostKeyChecking=yes",
                                                   remote=_sh(PREPARE_SCRIPT)),
                                     bundle(files), timeout=self._connect_timeout + UPLOAD_TIMEOUT_SECONDS)
        failure = classify(code, error)
        directory = out.decode("utf-8", errors="replace").strip()
        if failure is not None:
            return failure, _last_line(error)
        if not SESSION_DIRECTORY.match(directory):
            return RemoteFailure.SCAN_FAILED, "unexpected directory"
        return directory

    def run(self, target: RemoteTarget, directory: str) -> int:
        """Dans le terminal de la personne (l'interface est suspendue par l'appelant) ; code de sortie."""
        if not SESSION_DIRECTORY.match(directory):
            return 2
        script = (PATH_PREFIX + f'cd "{directory}" && '
                  f'python3 -I "{directory}/agent.pyz" run "{directory}"')
        command = [self._ssh, "-t", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={self._connect_timeout}",
                   "-o", "StrictHostKeyChecking=yes", "--", target.text, _sh(script)]
        try:
            return subprocess.run(command, check=False).returncode  # noqa: S603
        except OSError:
            return 127

    def finish(self, target: RemoteTarget, directory: str) -> RemoteResult | None:
        """Resultat relu, puis dossier efface (toujours, meme en cas d'echec)."""
        if not SESSION_DIRECTORY.match(directory):
            return None
        script = PATH_PREFIX + f'cat "{directory}/result.json" 2>/dev/null; rm -rf "{directory}"'
        code, out, _error = self._run(self._command(target, "-o", "StrictHostKeyChecking=yes", remote=_sh(script)),
                                      timeout=self._connect_timeout + 30)
        try:
            return result_from_dict(json.loads(out.decode("utf-8"))) if out.strip() else None
        except (UnicodeDecodeError, ValueError):
            return None
