# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lecture de la zone neutre (lot D) : stat sans suivre de lien, deux niveaux, registre et copies.

Sans le groupe omega-synchro dans la session (ajout pas encore pris en compte), la zone (2750) n'est pas
lisible : `elevated` la relit avec `sudo -n find / stat / cat`, commandes de lecture seule, apres une
authentification explicite. Jamais de lecture root silencieuse."""
from __future__ import annotations

import grp
import os
import posixpath
from collections.abc import Callable, Sequence

from omega_lib.synchro.constants import ZONE_GROUP, ZONE_REGISTRY, ZONE_SHEETS_DIR, ZONE_TOKENS_DIR
from omega_lib.synchro.service_group import DROP_IN_NAME, SYSTEMD_UNIT_DIR, grants_zone_group

from omega_connect.core.constants import ZONE_FILE_SIZE_LIMIT
from omega_connect.domain.fail2ban import FileFacts, Presence
from omega_connect.domain.zone import ZoneFacts
from omega_connect.infrastructure.verification.files import file_facts

Capture = Callable[[Sequence[str]], tuple[int, bytes, str]]
"""Commande de lecture lancee en root : code, sortie, erreur (SudoRunner.capture)."""


def _wanted(relative: str) -> bool:
    if relative == ZONE_REGISTRY:
        return True
    head, _sep, name = relative.partition("/")
    return head in (ZONE_TOKENS_DIR, ZONE_SHEETS_DIR) and name.endswith(".json") and "/" not in name


def _read_limited(path: str) -> bytes | None:
    with open(path, "rb") as handle:
        data = handle.read(ZONE_FILE_SIZE_LIMIT + 1)
    return data if len(data) <= ZONE_FILE_SIZE_LIMIT else None


_FILE_TYPES = {"directory": "dir", "symbolic link": "link"}


class SystemZoneInspector:
    def __init__(self, zone_dir: str, capture: Capture | None = None, group: str = ZONE_GROUP,
                 unit_dir: str = SYSTEMD_UNIT_DIR) -> None:
        self._zone = zone_dir.rstrip("/") or "/"
        self._capture = capture
        self._group = group
        self._unit_dir = unit_dir

    def _service_groups(self) -> frozenset[str]:
        """Services dont le complement `<service>.service.d/omega-synchro.conf` donne le groupe (lot E) : lu sans
        root (0644), sans suivre de lien."""
        names: set[str] = set()
        try:
            listing = sorted(os.listdir(self._unit_dir))
        except OSError:
            return frozenset()
        for name in listing:
            if not name.endswith(".service.d"):
                continue
            path = posixpath.join(self._unit_dir, name, DROP_IN_NAME)
            entry = file_facts(path)
            if not entry.is_file or entry.is_symlink:
                continue
            try:
                data = _read_limited(path)
            except OSError:
                continue
            if data is not None and grants_zone_group(data.decode("utf-8", errors="replace")):
                names.add(name.removesuffix(".service.d"))
        return frozenset(names)

    @property
    def zone_path(self) -> str:
        return self._zone

    def _group_facts(self) -> tuple[bool, tuple[str, ...]]:
        try:
            entry = grp.getgrnam(self._group)
        except KeyError:
            return False, ()
        return True, tuple(sorted(entry.gr_mem))

    def inspect(self, *, elevated: bool) -> ZoneFacts:
        group_exists, members = self._group_facts()
        services = self._service_groups()
        root = file_facts(self._zone)

        def facts(entries: dict[str, FileFacts], known: bool, contents: dict[str, bytes] | None = None) -> ZoneFacts:
            return ZoneFacts(self._zone, entries, known, contents or {}, group_exists, members, services)

        if root.presence is not Presence.PRESENT or root.is_symlink or not root.is_dir:
            return facts({"": root}, root.presence is Presence.MISSING)
        try:
            return facts(*self._direct(root))
        except PermissionError:
            pass
        if elevated and self._capture is not None:
            privileged = self._privileged(root)
            if privileged is not None:
                return facts(*privileged)
        return facts({"": root}, False)

    def _direct(self, root: FileFacts) -> tuple[dict[str, FileFacts], bool, dict[str, bytes]]:
        entries = {"": root}
        for name in sorted(os.listdir(self._zone)):
            path = posixpath.join(self._zone, name)
            entry = file_facts(path)
            entries[name] = entry
            if entry.is_dir and not entry.is_symlink:
                for child in sorted(os.listdir(path)):
                    entries[f"{name}/{child}"] = file_facts(posixpath.join(path, child))
        contents: dict[str, bytes] = {}
        for relative, entry in entries.items():
            if _wanted(relative) and entry.is_file and not entry.is_symlink:
                data = _read_limited(entry.path)
                if data is not None:
                    contents[relative] = data
        return entries, True, contents

    def _privileged(self, root: FileFacts) -> tuple[dict[str, FileFacts], bool, dict[str, bytes]] | None:
        assert self._capture is not None
        code, output, _error = self._capture(["find", "-P", self._zone, "-mindepth", "1", "-maxdepth", "2"])
        if code != 0:
            return None
        prefix = self._zone + "/"
        paths = [line for line in output.decode("utf-8", errors="replace").splitlines() if line.startswith(prefix)]
        entries = {"": root}
        if paths:
            code, output, _error = self._capture(["stat", "-c", "%U|%G|%a|%F|%n", "--", *paths])
            if code != 0:
                return None
            for line in output.decode("utf-8", errors="replace").splitlines():
                parts = line.split("|", 4)
                if len(parts) != 5 or not parts[4].startswith(prefix):
                    continue
                owner, group, mode, kind, path = parts
                file_type = _FILE_TYPES.get(kind, "file" if kind.startswith("regular") else "other")
                entries[path[len(prefix):]] = FileFacts(
                    path, Presence.PRESENT, is_file=file_type == "file", owner=owner, group=group,
                    mode=int(mode, 8) if mode.isdigit() else 0, is_dir=file_type == "dir",
                    is_symlink=file_type == "link")
        contents: dict[str, bytes] = {}
        for relative, entry in entries.items():
            if _wanted(relative) and entry.is_file:
                code, output, _error = self._capture(["cat", "--", entry.path])
                if code == 0 and len(output) <= ZONE_FILE_SIZE_LIMIT:
                    contents[relative] = output
        return entries, True, contents
