# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sources 3 et 4 : recherche bornee dans le HOME (profondeur 3) et dans /srv (profondeur 2).

Decision de l'auteur (Q4, 2026-11-10) : un HOME peut contenir des montages Samba, NFS ou sshfs qui
feraient balayer tout le reseau local. Donc :
- aucun lien symbolique suivi ;
- jamais de changement de systeme de fichiers (meme `st_dev` que le point de depart) ;
- montages reseau ignores (lus dans /proc/self/mounts), meme s'ils partageaient le `st_dev` ;
- dossiers caches, sauvegardes `*.old-*`, `.venv`, `node_modules`... ecartes ;
- une installation trouvee n'est pas parcourue plus loin ;
- au-dela de SCAN_MAX_DIRECTORIES dossiers lus, la recherche s'arrete et le dit."""
from __future__ import annotations

import os
import re
from pathlib import Path

from omega_connect.core.constants import (
    BACKUP_DIRECTORY_PATTERN,
    NETWORK_FILESYSTEMS,
    OLD_DIRECTORY_MARKER,
    SCAN_MAX_DIRECTORIES,
    SKIPPED_DIRECTORY_NAMES,
)
from omega_connect.domain.detection import Candidate, NoteKind, ScanNote, Source
from omega_connect.infrastructure.detection.layout import looks_like_installation, real_directory

MOUNTS_FILE = "/proc/self/mounts"


def _unescape_mount(path: str) -> str:
    """/proc/self/mounts code espaces et tabulations en octal (`\\040`)."""
    return (path.replace("\\040", " ").replace("\\011", "\t").replace("\\012", "\n")
            .replace("\\134", "\\"))


def network_mount_points(mounts_file: str = MOUNTS_FILE) -> frozenset[str]:
    try:
        lines = Path(mounts_file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return frozenset()
    points = set()
    for line in lines:
        fields = line.split()
        if len(fields) >= 3 and fields[2] in NETWORK_FILESYSTEMS:
            points.add(_unescape_mount(fields[1]))
    return frozenset(points)


_BACKUP = re.compile(BACKUP_DIRECTORY_PATTERN, re.IGNORECASE)


def _skipped_name(name: str) -> bool:
    return (name.startswith(".") or name in SKIPPED_DIRECTORY_NAMES or OLD_DIRECTORY_MARKER in name
            or _BACKUP.search(name) is not None)


class FilesystemScanLocator:
    def __init__(self, start: Path, depth: int, source: Source, *, mounts_file: str = MOUNTS_FILE,
                 max_directories: int = SCAN_MAX_DIRECTORIES) -> None:
        self._start = start
        self._depth = depth
        self._source = source
        self._mounts_file = mounts_file
        self._max = max_directories
        self._notes: list[ScanNote] = []
        self.visited = 0

    def candidates(self) -> list[Candidate]:
        self._notes = []
        self.visited = 0
        try:
            start = self._start.resolve(strict=True)
            device = start.stat().st_dev
        except (OSError, RuntimeError):
            return []
        network = network_mount_points(self._mounts_file)
        found: list[Candidate] = []
        skipped_network: set[str] = set()
        pending: list[tuple[Path, int]] = [(start, 0)]
        while pending:
            directory, level = pending.pop()
            if self.visited >= self._max:
                self._notes.append(ScanNote(NoteKind.SEARCH_STOPPED, str(start)))
                break
            self.visited += 1
            if level > 0 and looks_like_installation(directory):
                found.append(Candidate(str(directory), self._source))
                continue
            if level >= self._depth:
                continue
            try:
                entries = list(os.scandir(directory))
            except OSError:
                continue
            for entry in sorted(entries, key=lambda e: e.name, reverse=True):
                if _skipped_name(entry.name):
                    continue
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    child_device = entry.stat(follow_symlinks=False).st_dev
                except OSError:
                    continue
                if entry.path in network:
                    skipped_network.add(entry.path)
                    continue
                if child_device != device:
                    continue
                pending.append((Path(entry.path), level + 1))
        for path in sorted(skipped_network):
            self._notes.append(ScanNote(NoteKind.NETWORK_MOUNT_SKIPPED, path))
        return sorted(found, key=lambda c: c.root)

    def notes(self) -> list[ScanNote]:
        return list(self._notes)


class ManualLocator:
    """Source 5 : chemins saisis a la main (--chemin)."""

    def __init__(self, paths: list[str]) -> None:
        self._paths = paths
        self._notes: list[ScanNote] = []

    def candidates(self) -> list[Candidate]:
        self._notes = []
        found = []
        for raw in self._paths:
            root = real_directory(raw)
            if root is None:
                self._notes.append(ScanNote(NoteKind.MANUAL_NOT_FOUND, raw))
                continue
            if not looks_like_installation(Path(root)):
                self._notes.append(ScanNote(NoteKind.MANUAL_NOT_OMEGA, root))
                continue
            found.append(Candidate(root, Source.MANUAL))
        return found

    def notes(self) -> list[ScanNote]:
        return list(self._notes)
