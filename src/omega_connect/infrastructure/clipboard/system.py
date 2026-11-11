# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Presse-papiers du systeme (retour de l'auteur, 2026-11-11 : « ca copie rien, juste la notification » — son
terminal n'accepte pas la copie OSC 52 de Textual).

wl-copy sous Wayland, sinon xclip, sinon xsel sous X11, comme lnav. Le programme est lance dans SA PROPRE session :
il reste en arriere-plan pour servir le presse-papiers apres la copie (X11 l'exige) ; meme lecon que la copie de
lnav dans omega-serv (tuer le groupe de processus effacait ce qui venait d'etre copie)."""
from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping

WAIT_SECONDS = 2.0


def _candidates(environ: Mapping[str, str]) -> list[list[str]]:
    found = []
    if environ.get("WAYLAND_DISPLAY"):
        found.append(["wl-copy"])
    if environ.get("DISPLAY"):
        found.append(["xclip", "-selection", "clipboard", "-in"])
        found.append(["xsel", "--clipboard", "--input"])
    return found


def copy_text(text: str, environ: Mapping[str, str] | None = None) -> str:
    """Nom de l'outil qui a pris le texte ; vide si aucun (pas d'affichage graphique, aucun outil installe)."""
    env = os.environ if environ is None else environ
    for argv in _candidates(env):
        if shutil.which(argv[0], path=env.get("PATH")) is None:
            continue
        try:
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,  # noqa: S603
                                       stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
                                       env=dict(env))
            assert process.stdin is not None
            process.stdin.write(text.encode("utf-8"))
            process.stdin.close()
        except OSError:
            continue
        try:
            code = process.wait(timeout=WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            return argv[0]  # reste au premier plan pour servir le presse-papiers : la copie est faite
        if code == 0:
            return argv[0]
    return ""
