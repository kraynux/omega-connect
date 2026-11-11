# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""HOME examine (spec etape 3, Q6) : celui de la personne qui lance, ou de SUDO_USER sous sudo (sinon
sous sudo on examinerait /root et le registre d'omega-serv serait introuvable, etude §2 point 4)."""
from __future__ import annotations

import os
import pwd
from collections.abc import Mapping
from pathlib import Path


def target_home(environ: Mapping[str, str] | None = None, euid: int | None = None) -> Path:
    env = os.environ if environ is None else environ
    uid = os.geteuid() if euid is None else euid
    sudo_user = env.get("SUDO_USER", "")
    if uid == 0 and sudo_user and sudo_user != "root":
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            pass
    try:
        return Path(pwd.getpwuid(uid).pw_dir)
    except KeyError:
        return Path(env.get("HOME", "/"))
