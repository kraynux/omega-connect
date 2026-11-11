# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Seul module qui lance une commande root (lot D) : `sudo -n -- <commande>`, jamais de shell, jamais
d'elevation de tout omega-connect (decision Q3). Le contenu d'une copie passe par un fichier temporaire prive
(dossier 0700, fichier 0600), supprime aussitot."""
from __future__ import annotations

import grp
import os
import pwd
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from omega_connect.core.constants import PRIVILEGED_TIMEOUT_SECONDS
from omega_connect.domain.zone import CommandOutcome, Operation, OperationKind, ZoneSubject


def running_as_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _last_line(text: bytes) -> str:
    lines = [line.strip() for line in text.decode("utf-8", errors="replace").splitlines() if line.strip()]
    return lines[-1] if lines else ""


class SudoRunner:
    def __init__(self, sudo: str = "sudo", timeout: float = PRIVILEGED_TIMEOUT_SECONDS) -> None:
        self._sudo = sudo
        self._timeout = timeout

    def _prefix(self) -> list[str]:
        return [] if running_as_root() else [self._sudo, "-n", "--"]

    def authenticate(self) -> bool:
        if running_as_root():
            return True
        try:
            return subprocess.run([self._sudo, "-v"], check=False).returncode == 0  # noqa: S603
        except OSError:
            return False

    def capture(self, argv: Sequence[str]) -> tuple[int, bytes, str]:
        """Commande de LECTURE en root (find, stat, cat) : code, sortie, derniere ligne d'erreur."""
        try:
            done = subprocess.run([*self._prefix(), *argv], capture_output=True, check=False,  # noqa: S603
                                  timeout=self._timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            return 1, b"", str(error)
        return done.returncode, done.stdout, _last_line(done.stderr)

    def run(self, operation: Operation) -> CommandOutcome:
        if operation.kind is not OperationKind.WRITE_FILE:
            code, _output, error = self.capture(operation.argv())
            return CommandOutcome(code, error)
        directory = tempfile.mkdtemp(prefix="omega-connect-")
        try:
            source = Path(directory) / "contenu"
            descriptor = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(operation.content)
            code, _output, error = self.capture(operation.argv(str(source)))
            return CommandOutcome(code, error)
        finally:
            shutil.rmtree(directory, ignore_errors=True)


class SessionSubject:
    """La personne : `SUDO_USER` si omega-connect tourne en root sous sudo, sinon le compte qui lance."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def subject(self) -> ZoneSubject:
        user = ""
        if running_as_root():
            user = self._environ.get("SUDO_USER", "")
        if not user:
            try:
                user = pwd.getpwuid(os.getuid()).pw_name
            except KeyError:
                user = ""
        groups = []
        for gid in {*os.getgroups(), os.getgid()}:
            try:
                groups.append(grp.getgrgid(gid).gr_name)
            except KeyError:
                continue
        return ZoneSubject(user=user, session_groups=tuple(sorted(groups)))
