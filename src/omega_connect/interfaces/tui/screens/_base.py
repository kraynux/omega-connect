# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Classe de base des ecrans navigables (Echap -> retour, fleches). Reprise d'omega-log 1.6.0, avec
`_maybe_suspend` (lot D) : rend le vrai terminal a `sudo -v` pour le mot de passe, puis le reprend. Le filet
`_ensure_terminal_truly_released` est garde tel quel : sans lui, le fil clavier de Textual lit le mot de passe en
meme temps que sudo (bug deja rencontre chez omega-serv).

`_reset_terminal_for_prompt` (2026-11-10, constate par l'auteur : invite de sudo affichee dans l'en-tete de
l'interface, mot de passe refuse) : sur certains terminaux l'ecran alternatif n'est pas quitte et le protocole
clavier etendu (kitty) reste actif — Entree et les lettres arrivent alors en sequences d'echappement, sudo recoit
un mot de passe faux. Avant l'invite, on force donc soi-meme un terminal « ordinaire » : ecran normal, protocole
clavier a zero (pas seulement « depile »), modifyOtherKeys, souris et collage coupes, mode ligne avec echo, ecran
efface et une ligne qui dit ce qui est demande."""
from __future__ import annotations

import sys
import termios
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import TYPE_CHECKING, ClassVar

from textual.app import SuspendNotSupported
from textual.binding import Binding, BindingType
from textual.screen import Screen

from omega_connect.shared.i18n import N_, _

if TYPE_CHECKING:
    from textual.app import App

_INPUT_THREAD_JOIN_TIMEOUT_SECONDS = 1.0


def _ensure_terminal_truly_released(app: App[None]) -> None:
    """Best-effort (`getattr` partout) : attend que le fil d'entree du pilote soit arrete et vide l'entree."""
    driver = getattr(app, "_driver", None)
    if driver is None:
        return
    key_thread = getattr(driver, "_key_thread", None)
    if key_thread is not None and key_thread.is_alive():
        exit_event = getattr(driver, "exit_event", None)
        if exit_event is not None:
            exit_event.set()
        key_thread.join(timeout=_INPUT_THREAD_JOIN_TIMEOUT_SECONDS)
        if exit_event is not None:
            exit_event.clear()
    writer_thread = getattr(driver, "_writer_thread", None)
    if writer_thread is not None and writer_thread.is_alive():
        stop = getattr(writer_thread, "stop", None)
        if callable(stop):
            stop()
        else:
            writer_thread.join(timeout=_INPUT_THREAD_JOIN_TIMEOUT_SECONDS)
    fileno = getattr(driver, "fileno", None)
    if isinstance(fileno, int):
        with suppress(OSError):
            termios.tcflush(fileno, termios.TCIFLUSH)


PLAIN_TERMINAL = (
    "\x1b[?1049l"   # ecran normal (quitte l'ecran alternatif de l'interface)
    "\x1b[=0;1u"    # protocole clavier kitty : drapeaux a zero sur cet ecran
    "\x1b[>4;0m"    # xterm modifyOtherKeys coupe
    "\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l"  # souris
    "\x1b[?2004l"   # collage encadre
    "\x1b[?1004l"   # evenements de focus
    "\x1b[?25h"     # curseur visible
    "\x1b[0m\x1b[2J\x1b[H"  # couleurs, ecran efface, curseur en haut
)


def _reset_terminal_for_prompt(message: str) -> None:
    """Terminal ordinaire avant l'invite de sudo (voir la note en tete de fichier). Best-effort."""
    stream = sys.__stdout__
    if stream is None or not stream.isatty():
        return
    try:
        stream.write(PLAIN_TERMINAL + (message + "\n\n" if message else ""))
        stream.flush()
    except OSError:
        return
    stdin = sys.__stdin__
    if stdin is None or not stdin.isatty():
        return
    try:
        attrs = termios.tcgetattr(stdin.fileno())
        attrs[0] |= termios.ICRNL
        attrs[3] |= termios.ICANON | termios.ECHO | termios.ISIG | termios.IEXTEN
        termios.tcsetattr(stdin.fileno(), termios.TCSANOW, attrs)
        termios.tcflush(stdin.fileno(), termios.TCIFLUSH)
    except (termios.error, OSError, ValueError):
        return


SUDO_MESSAGE = N_("omega-connect — authentification sudo pour les commandes affichées (le mot de passe ne "
                  "s'affiche pas pendant la saisie). L'interface revient ensuite.")


@contextmanager
def suspended(app: App[None], message: str = "") -> Iterator[None]:
    """A utiliser autour de `PrivilegedRunner.authenticate()` (mot de passe sudo sur le vrai terminal)."""
    caught: BaseException | None = None
    try:
        with app.suspend():
            _ensure_terminal_truly_released(app)
            _reset_terminal_for_prompt(_(message) if message else "")
            try:
                yield
            except BaseException as exc:  # noqa: BLE001 - repropagee plus bas, jamais avalee
                caught = exc
    except SuspendNotSupported:
        yield
        return
    if caught is not None:
        raise caught


def copy_commands(app: App[None], commands: tuple[str, ...] | list[str]) -> None:
    """Une commande par ligne (retour de l'auteur, 2026-11-11 : « on ne peut meme pas les copier, il faut les
    retaper a la main » ; « il faut que l'utilisateur puisse le faire quel que soit son presse-papiers »).

    1. presse-papiers du SYSTEME (wl-copy, xclip, xsel : fourni par l'application, `system_clipboard`) ;
    2. celui du terminal (OSC 52), en plus : certains terminaux ne l'acceptent pas, on ne peut pas le savoir ;
    3. sans outil systeme : les commandes s'affichent en clair dans le terminal, interface mise de cote ; la
       selection a la souris du terminal marche partout (meme sans affichage graphique)."""
    lines = [command for command in dict.fromkeys(commands) if command]
    if not lines:
        app.notify(_("Aucune commande à copier."))
        return
    text = "\n".join(lines) + "\n"
    system = getattr(app, "system_clipboard", None)
    tool = system(text) if callable(system) else ""
    app.copy_to_clipboard(text)
    if tool:
        app.notify(_("{count} commande(s) copiée(s) dans le presse-papiers ({tool}) : collez-les dans un terminal "
                     "(Ctrl+Maj+V).").format(count=len(lines), tool=tool))
        return
    show_commands_in_terminal(app, lines)


def show_commands_in_terminal(app: App[None], lines: list[str]) -> None:
    """Repli universel : terminal ordinaire (souris rendue au terminal), commandes seules, Entree pour revenir."""
    with suspended(app, _("omega-connect — commandes à copier. Sélectionnez-les à la souris puis copiez avec le "
                          "raccourci de votre terminal (souvent Ctrl+Maj+C) :")):
        stream = sys.__stdout__
        if stream is not None:
            with suppress(OSError):
                stream.write("\n".join(lines) + "\n\n")
                stream.flush()
        with suppress(EOFError, OSError):
            input(_("Entrée pour revenir à omega-connect… "))


class OmegaScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", _("Retour"), show=True),
        Binding("up", "focus_previous_item", _("Monter"), show=False),
        Binding("down", "focus_next_item", _("Descendre"), show=False),
    ]

    def action_back(self) -> None:
        self.dismiss()

    def action_focus_previous_item(self) -> None:
        self.focus_previous()

    def action_focus_next_item(self) -> None:
        self.focus_next()
