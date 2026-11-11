# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fiche d'une installation : `<racine>/<lanceur> synchro fiche --format json` (contrats de l'etape 2).

Regles (spec etape 2 §3.4, etape 3 §3.1) :
- le lanceur est deduit d'omega-lib (TOOL_LAUNCHERS), jamais lu dans le jeton ;
- il doit etre un fichier ordinaire appartenant au proprietaire du dossier, non modifiable par le
  groupe ni par les autres ;
- il est lance SOUS LE COMPTE PROPRIETAIRE du dossier, jamais en root : directement si c'est le compte
  courant, avec `runuser -u <compte>` si omega-connect tourne en root, et pas du tout sinon (autre compte) ;
- 10 secondes au plus ; environnement reduit (PATH, HOME, LANG=C.UTF-8) ;
- dans une NOUVELLE SESSION, sans terminal de controle : un outil ne peut jamais demander un mot de passe.
  Constate le 2026-11-10 : une ancienne version d'omega-fire (sans `synchro`) s'eleve avec sudo, et sudo ouvre
  /dev/tty directement (stdin ferme ne suffit pas) ; son invite s'affichait par-dessus l'interface et les frappes
  partaient a moitie dans Textual. Sans terminal, sudo echoue aussitot : fiche « non obtenue »."""
from __future__ import annotations

import json
import os
import pwd
import stat
import subprocess
from pathlib import Path

from omega_lib.synchro.codec import sheet_from_dict
from omega_lib.synchro.constants import TOOL_LAUNCHERS
from omega_lib.synchro.models import ReadStatus

from omega_connect.core.constants import SHEET_TIMEOUT_SECONDS
from omega_connect.domain.detection import SheetResult

MAX_SHEET_BYTES = 1024 * 1024
SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def verified_launcher(root: str, tool: str) -> tuple[Path | None, int, str]:
    """(lanceur, uid du proprietaire du dossier, raison du refus) : fichier ordinaire, meme proprietaire que le
    dossier, non modifiable par le groupe ni les autres. Aussi verifie avant chaque commande de `reparer`."""
    launcher_name = TOOL_LAUNCHERS.get(tool)
    if launcher_name is None:
        return None, -1, f"no launcher known for {tool}"
    root_path = Path(root)
    launcher = root_path / launcher_name
    try:
        root_uid = root_path.stat().st_uid
        info = launcher.lstat()
    except OSError:
        return None, -1, f"launcher missing: {launcher}"
    if not stat.S_ISREG(info.st_mode):
        return None, root_uid, f"launcher is not a regular file: {launcher}"
    if info.st_uid != root_uid:
        return None, root_uid, f"launcher not owned by the folder owner: {launcher}"
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return None, root_uid, f"launcher writable by group or others: {launcher}"
    return launcher, root_uid, ""


def owner_environment(root: str) -> dict[str, str]:
    """Environnement reduit pour une commande lancee sous le compte proprietaire."""
    try:
        owner_home = pwd.getpwuid(Path(root).stat().st_uid).pw_dir
    except (KeyError, OSError):
        owner_home = "/"
    return {"PATH": SAFE_PATH, "HOME": owner_home, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


class SubprocessSheetFetcher:
    def __init__(self, euid: int | None = None, timeout: float = SHEET_TIMEOUT_SECONDS) -> None:
        self._euid = os.geteuid() if euid is None else euid
        self._timeout = timeout

    def command(self, root: str, tool: str) -> tuple[list[str] | None, str]:
        """(commande, raison du refus) ; commande None si la fiche ne doit pas etre demandee."""
        launcher, root_uid, refusal = verified_launcher(root, tool)
        if launcher is None:
            return None, refusal
        arguments = [str(launcher), "synchro", "fiche", "--format", "json"]
        if self._euid == root_uid:
            return arguments, ""
        if self._euid == 0:
            try:
                account = pwd.getpwuid(root_uid).pw_name
            except KeyError:
                return None, f"owner {root_uid} has no account"
            return ["runuser", "-u", account, "--", *arguments], ""
        return None, "folder owned by another account: not examined"

    def fetch(self, root: str, tool: str) -> SheetResult:
        command, refusal = self.command(root, tool)
        if command is None:
            return SheetResult(ReadStatus.UNREADABLE, detail=refusal)
        environment = owner_environment(root)
        try:
            completed = subprocess.run(command, capture_output=True, timeout=self._timeout, check=False,
                                       cwd=root, env=environment, stdin=subprocess.DEVNULL,
                                       start_new_session=True)
        except subprocess.TimeoutExpired:
            return SheetResult(ReadStatus.UNREADABLE, detail=f"no answer after {self._timeout:.0f} s")
        except OSError as error:
            return SheetResult(ReadStatus.UNREADABLE, detail=f"cannot run launcher: {error.strerror}")
        if completed.returncode != 0:
            # Version anterieure aux contrats (pas de `synchro`) ou erreur de configuration.
            return SheetResult(ReadStatus.ABSENT, detail=f"launcher exited with code {completed.returncode}")
        if len(completed.stdout) > MAX_SHEET_BYTES:
            return SheetResult(ReadStatus.INVALID, detail="sheet too large")
        try:
            data = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return SheetResult(ReadStatus.INVALID, detail="sheet is not valid UTF-8 JSON")
        parsed = sheet_from_dict(data)
        return SheetResult(parsed.status, parsed.value, parsed.detail)
