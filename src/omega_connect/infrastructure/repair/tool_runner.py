# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Commandes des outils lancees par `reparer` (lot E) : le lanceur de l'outil, verifie juste avant (fichier
ordinaire, meme proprietaire que le dossier, non modifiable par le groupe ni les autres), jamais de shell.

- en root : `sudo -n -- <lanceur> ...` apres une seule authentification (`sudo -v`), comme les commandes de
  la zone ; directement si omega-connect tourne deja en root ;
- sous le compte proprietaire (jeton) : directement, ou `runuser -u` en root ; dans une nouvelle session, sans
  terminal (un outil ne peut jamais y demander de mot de passe), environnement reduit."""
from __future__ import annotations

import os
import subprocess

from omega_connect.core.constants import REPAIR_TIMEOUT_SECONDS, TOKEN_TIMEOUT_SECONDS
from omega_connect.domain.repair import RepairStep, StepOutcome
from omega_connect.infrastructure.detection.sheet_fetcher import SAFE_PATH, owner_environment, verified_launcher


def _last_line(text: bytes) -> str:
    lines = [line.strip() for line in text.decode("utf-8", errors="replace").splitlines() if line.strip()]
    return lines[-1] if lines else ""


class ToolCommandRunner:
    def __init__(self, sudo: str = "sudo", euid: int | None = None) -> None:
        self._sudo = sudo
        self._euid = os.geteuid() if euid is None else euid

    def command(self, step: RepairStep) -> tuple[list[str] | None, str]:
        launcher, _root_uid, refusal = verified_launcher(step.root, step.tool)
        if launcher is None:
            return None, refusal
        argv = [str(launcher), *step.argv()[1:]]
        if step.needs_root:
            return (argv if self._euid == 0 else [self._sudo, "-n", "--", *argv]), ""
        if self._euid == 0:
            return ["runuser", "-u", step.account, "--", *argv], ""
        return argv, ""

    def run(self, step: RepairStep) -> StepOutcome:
        command, refusal = self.command(step)
        if command is None:
            return StepOutcome(step, 1, refusal)
        if step.needs_root:
            # Comme les commandes de la zone : sudo -n garde le terminal (son jeton d'authentification en
            # depend) mais ne demande jamais de mot de passe ; l'outil lance n'a aucune question a poser.
            environment = {"PATH": SAFE_PATH, "LANG": os.environ.get("LANG", "C.UTF-8")}
            options: dict[str, object] = {"timeout": REPAIR_TIMEOUT_SECONDS}
        else:
            environment = owner_environment(step.root)
            options = {"timeout": TOKEN_TIMEOUT_SECONDS, "start_new_session": True}
        try:
            done = subprocess.run(command, capture_output=True, check=False, cwd=step.root,  # noqa: S603
                                  env=environment, stdin=subprocess.DEVNULL, **options)  # type: ignore[call-overload]
        except subprocess.TimeoutExpired:
            return StepOutcome(step, 124, f"no answer after {options['timeout']} s")
        except OSError as error:
            return StepOutcome(step, 1, str(error))
        return StepOutcome(step, done.returncode, _last_line(done.stderr) or _last_line(done.stdout))
