# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Droits des fichiers (stat sans suivre de lien) et lecture des fichiers d'omega-jail dans fail2ban."""
from __future__ import annotations

import grp
import os
import pwd
import stat
from pathlib import Path

from omega_connect.core.constants import FAIL2BAN_CONFIG_SIZE_LIMIT
from omega_connect.domain.fail2ban import (
    BRIDGE_ACTION_PREFIX,
    JAIL_FILE_PREFIX,
    ConfigText,
    Fail2banSnapshot,
    FileFacts,
    Presence,
)


def _name(lookup: str, ident: int) -> str:
    try:
        return pwd.getpwuid(ident).pw_name if lookup == "user" else grp.getgrgid(ident).gr_name
    except KeyError:
        return str(ident)


def file_facts(path: str) -> FileFacts:
    try:
        info = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return FileFacts(path, Presence.MISSING)
    except OSError as exc:
        return FileFacts(path, Presence.UNKNOWN, detail=exc.strerror or type(exc).__name__)
    return FileFacts(path, Presence.PRESENT, is_file=stat.S_ISREG(info.st_mode),
                     owner=_name("user", info.st_uid), group=_name("group", info.st_gid),
                     mode=stat.S_IMODE(info.st_mode), is_dir=stat.S_ISDIR(info.st_mode),
                     is_symlink=stat.S_ISLNK(info.st_mode))


class StatFileProbe:
    def facts(self, path: str) -> FileFacts:
        return file_facts(path)


def _read(path: Path) -> str | None:
    """Texte d'un fichier de configuration ordinaire ; None si illisible, lien symbolique ou trop gros."""
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > FAIL2BAN_CONFIG_SIZE_LIMIT:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


class Fail2banFilesReader:
    """Lit `<fail2ban>/jail.d/omega-jail-*.conf`, `filter.d/omega-jail-*.conf` et
    `action.d/omega-jail-tailscale-bridge*.conf` ; jamais les copies `.bak`, jamais un autre fichier."""

    def __init__(self, fail2ban_dir: str) -> None:
        self.root = Path(fail2ban_dir)

    def _listing(self, subdir: str, prefix: str) -> list[Path]:
        directory = self.root / subdir
        if not directory.is_dir():
            return []
        return sorted(path for path in directory.iterdir()
                      if path.name.startswith(prefix) and path.name.endswith(".conf"))

    def read(self) -> Fail2banSnapshot:
        if not self.root.is_dir():
            return Fail2banSnapshot(installed=False)
        try:
            jails = self._listing("jail.d", JAIL_FILE_PREFIX)
            filters = self._listing("filter.d", JAIL_FILE_PREFIX)
            actions = self._listing("action.d", BRIDGE_ACTION_PREFIX)
        except OSError as exc:
            return Fail2banSnapshot(installed=True, readable=False, detail=exc.strerror or type(exc).__name__)
        return Fail2banSnapshot(
            installed=True,
            jail_files=tuple(ConfigText(file_facts(str(path)), _read(path)) for path in jails),
            filter_files=tuple(file_facts(str(path)) for path in filters),
            action_files=tuple(ConfigText(file_facts(str(path)), _read(path)) for path in actions),
        )
