# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Groupe de la zone neutre pris au lancement (retour de l'auteur, 2026-11-10 : « il faut une commande universelle,
l'utilisateur va être perdu »).

Après « Établir », la personne est membre du groupe omega-synchro, mais sa session ne le sait qu'après une
reconnexion. Si c'est le cas, omega-connect se relance lui-même avec ce groupe, quelle que soit la façon dont il a
été lancé (`omega-connect.sh`, `python -m omega_connect`) : `sg` s'il existe, sinon `newgrp` (Manjaro n'a pas `sg`),
à qui la commande est donnée sur son entrée avant de rendre le terminal (`</dev/tty`). Aucun mot de passe (membre
du groupe), une seule fois (variable de garde), arguments protégés, code de sortie conservé. Sans `sg` ni terminal
(script) : rien ne change, la zone reste lue avec sudo après accord."""
from __future__ import annotations

import grp
import os
import pwd
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence

from omega_lib.synchro.constants import ZONE_GROUP

GUARD = "OMEGA_CONNECT_GROUP_SWITCHED"


def needs_switch(group: str = ZONE_GROUP, environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    if os.geteuid() == 0 or env.get(GUARD):
        return False
    try:
        entry = grp.getgrnam(group)
        account = pwd.getpwuid(os.getuid())
    except KeyError:
        return False
    if entry.gr_gid in {os.getgid(), *os.getgroups()}:
        return False
    return account.pw_name in entry.gr_mem or account.pw_gid == entry.gr_gid


def switch_command(arguments: Sequence[str]) -> str:
    return shlex.join([sys.executable, "-m", "omega_connect", *arguments])


def relaunch_with_zone_group(arguments: Sequence[str], group: str = ZONE_GROUP) -> int | None:
    """Code de sortie de la relance ; None : pas de relance, continuer normalement."""
    if not needs_switch(group):
        return None
    environment = {**os.environ, GUARD: "1"}
    command = switch_command(arguments)
    sg = shutil.which("sg")
    if sg is not None:
        sys.stdout.flush()
        os.execve(sg, [sg, group, "-c", f"exec {command}"], environment)  # noqa: S606
    newgrp = shutil.which("newgrp")
    if newgrp is None or not sys.stdin.isatty():
        return None
    try:
        done = subprocess.run([newgrp, group], input=f"exec {command} </dev/tty\n".encode(),  # noqa: S603
                              env=environment, check=False)
    except OSError:
        return None
    return done.returncode
