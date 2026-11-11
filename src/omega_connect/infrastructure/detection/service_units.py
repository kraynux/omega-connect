# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Source 2 : services omega-serv declares a systemd, OpenRC ou runit (decision Q4 du 2026-11-10).

Lecture seule des fichiers (aucune commande lancee) : `/etc/systemd/system/omega-serv*.service`,
`/etc/init.d/omega-serv*`, `/etc/sv/omega-serv*/run`."""
from __future__ import annotations

from pathlib import Path

from omega_connect.core.constants import (
    OPENRC_INIT_DIR,
    RUNIT_SERVICE_DIR,
    SERV_SERVICE_PREFIX,
    SYSTEMD_UNIT_DIR,
)
from omega_connect.domain.detection import (
    Candidate,
    NoteKind,
    ScanNote,
    Source,
    is_server_service,
    parse_service_root,
)
from omega_connect.infrastructure.detection.layout import real_directory

MAX_UNIT_BYTES = 256 * 1024


class ServiceUnitsLocator:
    def __init__(self, systemd_dir: str = SYSTEMD_UNIT_DIR, openrc_dir: str = OPENRC_INIT_DIR,
                 runit_dir: str = RUNIT_SERVICE_DIR) -> None:
        self._dirs = ((Path(systemd_dir), Source.SYSTEMD), (Path(openrc_dir), Source.OPENRC),
                      (Path(runit_dir), Source.RUNIT))
        self._notes: list[ScanNote] = []

    def _files(self, directory: Path, source: Source) -> list[tuple[str, Path]]:
        try:
            entries = sorted(directory.glob(f"{SERV_SERVICE_PREFIX}*"))
        except OSError:
            return []
        files = []
        for entry in entries:
            if source is Source.SYSTEMD:
                if entry.suffix == ".service" and not entry.is_symlink():
                    files.append((entry.stem, entry))
            elif source is Source.OPENRC:
                if entry.is_file() and not entry.is_symlink():
                    files.append((entry.name, entry))
            elif (entry / "run").is_file():
                files.append((entry.name, entry / "run"))
        return files

    def candidates(self) -> list[Candidate]:
        self._notes = []
        found = []
        for directory, source in self._dirs:
            for service, path in self._files(directory, source):
                try:
                    with path.open("r", encoding="utf-8", errors="replace") as handle:
                        text = handle.read(MAX_UNIT_BYTES)
                except OSError:
                    self._notes.append(ScanNote(NoteKind.SERVICE_FILE_UNREADABLE, str(path)))
                    continue
                if not is_server_service(text):
                    continue  # tache annexe (rotation des journaux...), pas une instance
                parsed = parse_service_root(text)
                root = real_directory(parsed) if parsed else None
                if root is None:
                    self._notes.append(ScanNote(NoteKind.SERVICE_ROOT_MISSING, f"{service} ({source.value})"))
                    continue
                found.append(Candidate(root, source, "omega-serv", service))
        return found

    def notes(self) -> list[ScanNote]:
        return list(self._notes)
