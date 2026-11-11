# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""`<omega-connect>/var/parc.json` : registre du parc (decision Q3 de la refonte). Ecriture atomique ; sous sudo,
le fichier est rendu au proprietaire du dossier (jamais un fichier root dans le dossier de l'utilisateur)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from omega_connect.domain.parc import MachineEntry, parc_from_dict, parc_to_dict
from omega_connect.infrastructure.zone.system import running_as_root

PARC_FILE = "parc.json"
MAX_PARC_BYTES = 4 * 1024 * 1024


class FileParcStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._path = directory / PARC_FILE

    def load(self) -> tuple[MachineEntry, ...]:
        try:
            if self._path.is_symlink() or self._path.stat().st_size > MAX_PARC_BYTES:
                return ()
            return parc_from_dict(json.loads(self._path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return ()

    def save(self, machine: MachineEntry) -> None:
        machines = [entry for entry in self.load() if entry.key != machine.key
                    and not (entry.local and machine.local)]
        machines.insert(0 if machine.local else len(machines), machine)
        self._write(machines)

    def remove(self, key: str) -> bool:
        machines = list(self.load())
        kept = [entry for entry in machines if entry.local or entry.key != key]
        if len(kept) == len(machines):
            return False
        self._write(kept)
        return True

    def _write(self, machines: list[MachineEntry]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".parc-", dir=self._directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(parc_to_dict(machines), handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.chmod(temporary, 0o644)
            if running_as_root():
                owner = self._directory.parent.stat()
                os.chown(temporary, owner.st_uid, owner.st_gid)
                os.chown(self._directory, owner.st_uid, owner.st_gid)
            os.replace(temporary, self._path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
