# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Reglages dans `var/settings.json` (port SettingsStore d'omega-lib), ecriture atomique, comme le reste de la
suite."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class JsonSettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.all().get(key, default)

    def set(self, key: str, value: str) -> None:
        data = self.all()
        data[key] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self._path.parent, prefix=".settings-")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            os.chmod(temporary, 0o644)
            os.replace(temporary, self._path)
        except OSError:
            Path(temporary).unlink(missing_ok=True)
            raise

    def all(self) -> dict[str, str]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {str(key): str(value) for key, value in data.items()} if isinstance(data, dict) else {}
