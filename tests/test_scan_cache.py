# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan relu (decision de l'auteur, 2026-11-22) : cette machine scannee une fois, relue par tous les ecrans ; un
nouveau scan seulement sur demande (« Relancer le scan ») ou apres une action sur cette machine."""
from __future__ import annotations

import threading
import time

from omega_connect.application.scan_cache import ScanCache, request_rescan


def test_un_seul_scan_relu_puis_rescan_sur_demande() -> None:
    calls: list[int] = []
    cache = ScanCache(lambda: calls.append(1) or len(calls))
    assert cache() == 1 and cache() == 1 and cache() == 1  # relu, pas rescanne
    assert cache.scanned_at is not None and len(calls) == 1
    request_rescan(cache)
    assert cache() == 2 and cache() == 2
    assert cache.rescan() == 3
    request_rescan(lambda: None)  # une simple fonction (tests) : sans effet, sans erreur


def test_deux_ecrans_pendant_le_scan_de_demarrage_un_seul_scan() -> None:
    calls: list[int] = []

    def slow() -> int:
        time.sleep(0.2)
        calls.append(1)
        return len(calls)

    cache = ScanCache(slow)
    results: list[int] = []
    threads = [threading.Thread(target=lambda: results.append(cache())) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [1, 1, 1] and len(calls) == 1
