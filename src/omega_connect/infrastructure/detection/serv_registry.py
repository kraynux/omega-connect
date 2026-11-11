# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Source 1 : registre des instances d'omega-serv (`~/.config/omega-serv/instances.json`), lu sans
dependre du code d'omega-serv (seulement les champs `path` et `service_name`)."""
from __future__ import annotations

import json
from pathlib import Path

from omega_connect.core.constants import SERV_REGISTRY_RELATIVE
from omega_connect.domain.detection import Candidate, NoteKind, ScanNote, Source
from omega_connect.infrastructure.detection.layout import real_directory


class ServRegistryLocator:
    def __init__(self, home: Path) -> None:
        self._path = home / SERV_REGISTRY_RELATIVE
        self._notes: list[ScanNote] = []

    def candidates(self) -> list[Candidate]:
        self._notes = []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            self._notes.append(ScanNote(NoteKind.REGISTRY_UNREADABLE, str(self._path)))
            return []
        entries = data if isinstance(data, list) else data.get("instances", []) if isinstance(data, dict) else []
        found = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue
            root = real_directory(entry["path"])
            if root is None:
                self._notes.append(ScanNote(NoteKind.REGISTERED_INSTANCE_MISSING, entry["path"]))
                continue
            raw_service = entry.get("service_name")
            service = raw_service if isinstance(raw_service, str) else ""
            found.append(Candidate(root, Source.SERV_REGISTRY, "omega-serv", service))
        return found

    def notes(self) -> list[ScanNote]:
        return list(self._notes)
