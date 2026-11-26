# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan relu (decision 2026-11-22 : « faire un scan, l'enregistrer, et les ecrans relisent ce scan »), revu le
2026-11-26 (retour d'utilisation : « scan auto au lancement, apres l'operation, au retour… sur un parc d'une
cinquantaine de machines c'est intenable ») :

- `ScanCache` : le scan de CETTE machine (verification complete, fiches comprises : ~4 s), relu par tous les ecrans.
  Il s'appelle comme l'ancienne fonction `verify` (meme signature). Avec `empty` (l'interface), un appel ne scanne
  JAMAIS : avant le premier scan, il renvoie un rapport vide (etat vide, le scan est propose) ; pendant un nouveau
  scan, il renvoie le precedent sans attendre. Seul `rescan()` scanne.
- Sans `empty` (ligne de commande, tests) : le premier appel scanne, comme avant.
- `request_rescan()` : le prochain appel rescanne (mode sans `empty` seulement)."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Generic, TypeVar

Report = TypeVar("Report")


class ScanCache(Generic[Report]):
    def __init__(self, verify: Callable[[], Report], *, empty: Callable[[], Report] | None = None) -> None:
        self._verify = verify
        self._empty = empty
        self._lock = threading.Lock()
        self._report: Report | None = None
        self._stale = True
        self.scanned_at: datetime | None = None
        self.duration = 0.0
        self.scanning = False

    @property
    def scanned(self) -> bool:
        """Vrai une fois cette machine scannee (depuis le lancement)."""
        return self._report is not None

    def peek(self) -> Report | None:
        return self._report

    def __call__(self) -> Report:
        report = self._report
        if self._empty is not None:
            return report if report is not None else self._empty()
        with self._lock:
            if self._stale or self._report is None:
                self._scan()
            assert self._report is not None
            return self._report

    def _scan(self) -> None:
        self.scanning = True
        try:
            started = time.monotonic()
            report = self._verify()
            self.duration = time.monotonic() - started
            self._report = report
            self.scanned_at = datetime.now().astimezone()
            self._stale = False
        finally:
            self.scanning = False

    def request_rescan(self) -> None:
        self._stale = True

    def rescan(self) -> Report:
        """Scanne maintenant ; un seul scan a la fois (un second appel attend la fin du premier et le relit)."""
        if not self._lock.acquire(blocking=False):
            with self._lock:  # un scan est deja en cours : on attend sa fin, puis on le relit
                pass
            return self()
        try:
            self._scan()
            assert self._report is not None
            return self._report
        finally:
            self._lock.release()


def request_rescan(verify: object) -> None:
    """Le prochain appel de `verify` rescanne (sans effet si ce n'est pas un `ScanCache`, cas des tests)."""
    if isinstance(verify, ScanCache):
        verify.request_rescan()


def rescan_now(verify: Callable[[], object]) -> object:
    """Scan de cette machine maintenant (un `ScanCache` est rescanne ; une simple fonction est appelee)."""
    if isinstance(verify, ScanCache):
        return verify.rescan()
    return verify()


def local_scanned(verify: object) -> bool:
    """Cette machine a-t-elle ete scannee ? (une simple fonction, dans les tests : toujours vrai)"""
    return verify.scanned if isinstance(verify, ScanCache) else True
