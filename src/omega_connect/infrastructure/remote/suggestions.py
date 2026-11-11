# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Machines que cet ordinateur sait deja joindre (retour de l'auteur, 2026-11-10 : il n'entre jamais en SSH lui-meme,
seul Unison le fait) : profils Unison (`~/.unison/*.prf`), `~/.ssh/config`, `~/.ssh/known_hosts`. Lecture seule,
fichiers de la personne, taille bornee, liens symboliques ignores."""
from __future__ import annotations

import getpass
import socket
from collections.abc import Iterable
from pathlib import Path

from omega_connect.domain.remote import (
    Suggestion,
    SuggestionSource,
    known_hosts_names,
    merge_suggestions,
    ssh_config_hosts,
    unison_targets,
)

MAX_FILE_BYTES = 1024 * 1024


def _read(paths: Iterable[Path]) -> str:
    parts = []
    for path in paths:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                continue
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(parts)


class LocalSuggestions:
    def __init__(self, home: Path | None = None, user: str | None = None) -> None:
        self._home = home or Path.home()
        self._user = user

    def __call__(self) -> tuple[Suggestion, ...]:
        unison = sorted((self._home / ".unison").glob("*.prf")) if (self._home / ".unison").is_dir() else []
        name = socket.gethostname()
        try:
            user = self._user or getpass.getuser()
        except (KeyError, OSError):
            user = ""
        return merge_suggestions([
            (SuggestionSource.UNISON, unison_targets(_read(unison))),
            (SuggestionSource.SSH_CONFIG, ssh_config_hosts(_read([self._home / ".ssh" / "config"]))),
            (SuggestionSource.KNOWN_HOSTS, known_hosts_names(_read([self._home / ".ssh" / "known_hosts"]))),
        ], user, (name, name.split(".")[0]))
