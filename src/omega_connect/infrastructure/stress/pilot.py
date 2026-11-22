# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""omega-stress de cette machine en PILOTE (charge distribuee, lot L2, 2026-11-21) : `coordinateur etat --format
json`, lecture seule, jamais de sudo. Le dossier d'omega-stress est celui que la detection a trouve (premier
trouve s'il y en a plusieurs) ; aucun : pas de pilote."""
from __future__ import annotations

from collections.abc import Callable

from omega_connect.domain.distributed_load import STRESS_LAUNCHER, PilotState, pilot_from_json
from omega_connect.infrastructure.stress.runner import StressRunner, last_json


class LocalPilot:
    def __init__(self, roots: Callable[[], list[str]], runner: StressRunner | None = None) -> None:
        self._roots = roots
        self._runner = runner or StressRunner()
        self._root_cache: str | None = None

    def root(self) -> str:
        if self._root_cache is None:
            try:
                roots = self._roots()
            except Exception:  # noqa: BLE001 - detection impossible : pas de pilote
                roots = []
            self._root_cache = roots[0] if roots else ""
        return self._root_cache

    def __call__(self) -> PilotState | None:
        root = self.root()
        if not root:
            return None
        code, output, _error = self._runner.local(
            [f"{root.rstrip('/')}/{STRESS_LAUNCHER}", "coordinateur", "etat", "--format", "json"])
        return pilot_from_json(root, last_json(output)) if code == 0 else None
