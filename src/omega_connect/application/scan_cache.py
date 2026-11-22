# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan relu (decision de l'auteur, 2026-11-22 : « faire un scan au depart, l'enregistrer, et les ecrans relisent
ce scan ; pour d'autres operations, proposer de relancer le scan »).

- `ScanCache` : le scan de CETTE machine (verification complete, fiches comprises : ~4 s) fait une fois, puis relu
  par tous les ecrans ; il s'appelle comme l'ancienne fonction `verify` (meme signature), les ecrans n'ont rien a
  changer pour en profiter. `request_rescan()` : le prochain appel rescanne (bouton « Relancer le scan », ou apres
  une action sur cette machine).
- Les machines du reseau sont relues dans le registre du parc (SQLite) ; elles ne sont rescannees que sur demande,
  au demarrage, ou apres une action sur elles (`RemoteMachineScreen` rescanne la machine touchee)."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Generic, TypeVar

Report = TypeVar("Report")


class ScanCache(Generic[Report]):
    def __init__(self, verify: Callable[[], Report]) -> None:
        self._verify = verify
        self._lock = threading.Lock()
        self._report: Report | None = None
        self._stale = True
        self.scanned_at: datetime | None = None
        self.duration = 0.0

    def __call__(self) -> Report:
        """Le dernier scan ; le premier appel (ou apres `request_rescan`) scanne. Un seul scan a la fois : un ecran
        ouvert pendant le scan de demarrage attend sa fin au lieu d'en lancer un deuxieme."""
        with self._lock:
            if self._stale or self._report is None:
                started = time.monotonic()
                self._report = self._verify()
                self.duration = time.monotonic() - started
                self.scanned_at = datetime.now().astimezone()
                self._stale = False
            return self._report

    def request_rescan(self) -> None:
        self._stale = True

    def rescan(self) -> Report:
        self.request_rescan()
        return self()


def request_rescan(verify: object) -> None:
    """Le prochain appel de `verify` rescanne (sans effet si ce n'est pas un `ScanCache`, cas des tests)."""
    if isinstance(verify, ScanCache):
        verify.request_rescan()

