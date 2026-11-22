# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lance les commandes d'omega-stress (charge distribuee, lot L2, 2026-11-21) : sur cette machine, ou sur une
machine du reseau par SSH (cle deja acceptee, BatchMode : jamais de mot de passe demande ici). Les commandes
`coordinateur` et `worker` d'omega-stress ne demandent jamais sudo ; le pare-feu, lui, passe par SudoRunner
(sudo -v dans le vrai terminal, puis sudo -n)."""
from __future__ import annotations

import json
import shlex
import subprocess
from collections.abc import Sequence
from typing import Any

from omega_connect.infrastructure.remote.ssh import PATH_PREFIX

TIMEOUT_SECONDS = 60


def _run(argv: Sequence[str], data: bytes = b"", timeout: float = TIMEOUT_SECONDS,
         cwd: str | None = None) -> tuple[int, bytes, str]:
    try:
        done = subprocess.run(list(argv), input=data, capture_output=True, check=False,  # noqa: S603
                              timeout=timeout, start_new_session=True, cwd=cwd or None)
    except subprocess.TimeoutExpired:
        return 124, b"", "timed out"
    except OSError as error:
        return 127, b"", str(error)
    lines = [line for line in done.stderr.decode("utf-8", "replace").splitlines() if line.strip()]
    return done.returncode, done.stdout, lines[-1] if lines else ""


def last_json(output: bytes) -> Any:
    for line in reversed(output.decode("utf-8", "replace").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                return None
    return None


def _folder(argv: Sequence[str]) -> str:
    """Dossier d'omega-stress (celui de son lanceur) : omega-stress range son var/ dans le dossier
    COURANT ; lance depuis ailleurs, il ecrivait la liaison au mauvais endroit (essai reel de l'auteur,
    2026-11-21 : dans le dossier d'omega-connect, et dans ~/var sur craftdark)."""
    first = argv[0] if argv else ""
    return first.rsplit("/", 1)[0] if "/" in first and first.endswith(".sh") else ""


class StressRunner:
    def __init__(self, ssh: str = "ssh", connect_timeout: int = 10) -> None:
        self._ssh = ssh
        self._connect_timeout = connect_timeout

    def local(self, argv: Sequence[str], data: bytes = b"") -> tuple[int, bytes, str]:
        return _run(argv, data, cwd=_folder(argv))

    def remote(self, target: str, argv: Sequence[str], data: bytes = b"") -> tuple[int, bytes, str]:
        folder = _folder(argv)
        command = PATH_PREFIX + (f"cd {shlex.quote(folder)} && " if folder else "") + shlex.join(argv)
        return _run([self._ssh, "-o", "BatchMode=yes", "-o", f"ConnectTimeout={self._connect_timeout}",
                     "--", target, command], data)


def local_address_towards(host: str) -> str:
    """Adresse de cette machine telle que la voit `host` (route du systeme ; UDP : rien n'est envoye)."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((socket.gethostbyname(host), 9))
        return str(probe.getsockname()[0])
