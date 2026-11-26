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


# ---- 2026-11-26 : jamais de scan automatique ; scan du parc en arriere-plan, en parallele, interruptible ----

def test_interface_jamais_de_scan_a_la_lecture() -> None:
    """Retour d'utilisation 2026-11-26 : avant le premier scan, etat vide ; lire ne scanne jamais ; seul `rescan`."""
    calls: list[int] = []
    cache = ScanCache(lambda: calls.append(1) or len(calls), empty=lambda: 0)
    assert cache() == 0 and cache() == 0 and calls == [] and not cache.scanned
    assert cache.rescan() == 1 and cache() == 1 and cache.scanned and cache.peek() == 1
    request_rescan(cache)
    assert cache() == 1 and calls == [1]  # une demande de rescan ne scanne pas toute seule


def test_pendant_un_rescan_la_lecture_rend_l_ancien_scan_sans_attendre() -> None:
    release = threading.Event()
    values = iter([1, 2])

    def scan() -> int:
        value = next(values)
        if value == 2:
            release.wait(5)
        return value

    cache = ScanCache(scan, empty=lambda: 0)
    cache.rescan()
    worker = threading.Thread(target=cache.rescan)
    worker.start()
    time.sleep(0.05)
    started = time.monotonic()
    assert cache() == 1 and time.monotonic() - started < 0.5  # l'ancien, tout de suite
    release.set()
    worker.join()
    assert cache() == 2


def _service(**kwargs):
    from omega_connect.application.scan_service import ScanService

    return ScanService(**kwargs)


def _wait(service, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while service.running and time.monotonic() < deadline:
        time.sleep(0.01)


def test_parc_scanne_en_parallele() -> None:
    """50 machines : 8 a la fois (reglable), pas une par une."""
    from omega_connect.application.scan_service import LOCAL, ScanJob

    lock = threading.Lock()
    active = [0]
    peak = [0]
    done: list[str] = []

    def remote(target: str) -> None:
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
            done.append(target)

    service = _service(scan_local=lambda: (time.sleep(0.05), done.append("local")), scan_remote=remote,
                       workers=lambda: 8)
    jobs = [ScanJob(LOCAL, "ici"), *(ScanJob(f"k@m{index}", f"m{index}") for index in range(50))]
    started = time.monotonic()
    assert service.start(jobs) == 51
    assert service.start(jobs) == 0  # deja en file : pas deux fois
    _wait(service)
    assert sorted(done) == sorted(["local", *(f"k@m{index}" for index in range(50))])
    assert peak[0] == 8 and time.monotonic() - started < 1.5  # ~7 vagues de 50 ms, pas 50
    progress = service.progress()
    assert not progress.running and progress.done == 51 and progress.total == 51


def test_arreter_le_scan_n_attend_pas_et_garde_ce_qui_est_fait() -> None:
    from omega_connect.application.scan_service import ScanJob

    release = threading.Event()
    stopped: list[int] = []
    done: list[str] = []

    def remote(target: str) -> None:
        if target == "k@lente":
            release.wait(5)
            return
        time.sleep(0.03)
        done.append(target)

    service = _service(scan_local=lambda: None, scan_remote=remote, workers=lambda: 2,
                       stop_processes=lambda: (stopped.append(1), release.set()))
    service.start([ScanJob("k@rapide", "rapide"), ScanJob("k@lente", "lente"),
                   *(ScanJob(f"k@m{index}", f"m{index}") for index in range(20))])
    time.sleep(0.1)
    service.stop()
    _wait(service)
    progress = service.progress()
    assert stopped == [1] and progress.stopped and not progress.running
    assert "k@rapide" in done and len(done) < 21  # ce qui est fait reste ; le reste n'est jamais lance
    assert all(thread.daemon for thread in threading.enumerate() if thread.name == "omega-connect-scan")


def test_ssh_en_cours_arrete_par_stop_all_processes() -> None:
    """Fermeture de l'interface : un `ssh` en cours est arrete (ici `sleep 30`), jamais attendu."""
    from omega_connect.infrastructure.remote.ssh import allow_processes, run_tracked, stop_all_processes

    allow_processes()
    result: list[int] = []
    worker = threading.Thread(target=lambda: result.append(run_tracked(["sleep", "30"], timeout=60)[0]))
    started = time.monotonic()
    worker.start()
    time.sleep(0.2)
    assert stop_all_processes() == 1
    worker.join(5)
    assert result == [130] and time.monotonic() - started < 3
    assert run_tracked(["true"])[0] == 130  # plus rien ne demarre apres l'arret...
    allow_processes()
    assert run_tracked(["true"])[0] == 0  # ...jusqu'au prochain scan
