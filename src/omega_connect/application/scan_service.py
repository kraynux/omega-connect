# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan en arriere-plan (retour d'utilisation 2026-11-26 ; etude ETUDE_PARCOURS_SCAN_REPARER, lots S2-S3).

- Jamais lance tout seul : seulement « Scanner cette machine », « Scanner tout le parc », « Scanner la machine
  choisie », ou la machine qu'une action vient de toucher.
- Plusieurs machines a la fois (`workers`, 8 par defaut, reglable) ; cette machine d'abord, dans le meme lot.
- Interruptible : `stop()` (« Arreter le scan », fermeture de l'interface) ; les fils sont des fils « daemon » qui ne
  retiennent jamais la fermeture, et les `ssh` en cours sont arretes par `stop_processes`.
- L'etat (`progress()`) se lit depuis n'importe quel fil ; `generation` change a chaque machine terminee : les
  ecrans s'en servent pour se remettre a jour, ligne par ligne, pendant le scan."""
from __future__ import annotations

import contextlib
import queue
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass

DEFAULT_WORKERS = 8
MAX_WORKERS = 32
LOCAL = ""
"""Cle de cette machine dans la file (les machines du reseau : leur cible `utilisateur@machine`)."""


@dataclass(frozen=True)
class ScanProgress:
    running: bool
    done: int
    total: int
    current: tuple[str, ...]
    """Machines en cours (noms affiches)."""
    stopped: bool
    generation: int


@dataclass(frozen=True)
class ScanJob:
    key: str
    """`LOCAL` pour cette machine, sinon la cible ssh."""
    label: str


class ScanService:
    def __init__(self, *, scan_local: Callable[[], None], scan_remote: Callable[[str], None],
                 workers: Callable[[], int] = lambda: DEFAULT_WORKERS,
                 stop_processes: Callable[[], object] = lambda: None,
                 allow_processes: Callable[[], object] = lambda: None) -> None:
        self._scan_local = scan_local
        self._scan_remote = scan_remote
        self._workers = workers
        self._stop_processes = stop_processes
        self._allow_processes = allow_processes
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._running = 0
        self._done = 0
        self._total = 0
        self._current: dict[str, str] = {}
        self._stopped = False
        self._generation = 0
        self._queued: set[str] = set()
        self._queue: queue.Queue[ScanJob] = queue.Queue()

    # ---- etat ----
    def progress(self) -> ScanProgress:
        with self._lock:
            return ScanProgress(self._running > 0, self._done, self._total, tuple(self._current.values()),
                                self._stopped, self._generation)

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running > 0

    def busy_with(self, key: str) -> bool:
        with self._lock:
            return key in self._queued

    # ---- commandes ----
    def start(self, jobs: Sequence[ScanJob]) -> int:
        """Ajoute des machines a scanner (une machine deja en file n'est pas ajoutee deux fois) ; renvoie le nombre
        ajoute. Plusieurs appels pendant un scan s'ajoutent au meme scan."""
        with self._lock:
            fresh = [job for job in jobs if job.key not in self._queued]
            if not fresh:
                return 0
            if self._running == 0:
                self._done = self._total = 0
                self._stopped = False
                self._stop.clear()
                self._allow_processes()
            self._total += len(fresh)
            for job in fresh:
                self._queued.add(job.key)
                self._queue.put(job)
            wanted = max(1, min(MAX_WORKERS, self._workers()))
            to_start = max(0, min(wanted, self._total - self._done) - self._running)
            self._running += to_start
        for _index in range(to_start):
            threading.Thread(target=self._work, name="omega-connect-scan", daemon=True).start()
        return len(fresh)

    def stop(self) -> None:
        """Arrete le scan : plus aucune machine ne demarre, les `ssh` en cours sont arretes. Ce qui est fini reste."""
        with self._lock:
            if self._running == 0:
                return
            self._stopped = True
        self._stop.set()
        with self._lock:
            while True:
                try:
                    job = self._queue.get_nowait()
                except queue.Empty:
                    break
                self._queued.discard(job.key)
                self._total -= 1
        self._stop_processes()

    # ---- fils ----
    def _work(self) -> None:
        while True:
            with self._lock:  # prendre une machine et decider de s'arreter sous le meme verrou que `start`
                job = None
                if not self._stop.is_set():
                    with contextlib.suppress(queue.Empty):
                        job = self._queue.get_nowait()
                if job is None:
                    self._running -= 1
                    if self._running == 0:
                        self._generation += 1
                    return
                self._current[job.key] = job.label
            with contextlib.suppress(Exception):  # une machine ne bloque jamais les autres
                if job.key == LOCAL:
                    self._scan_local()
                else:
                    self._scan_remote(job.key)
            with self._lock:
                self._current.pop(job.key, None)
                self._queued.discard(job.key)
                self._done += 1
                self._generation += 1
