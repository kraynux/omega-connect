# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""`<omega-connect>/var/omega-connect.db` : registre du parc en SQLite (decision de l'auteur, 2026-11-22).

Une table par fonction :
- `machines` : une ligne par machine (cette machine et le reseau), comme les entrees de l'ancien parc.json ;
- `applications` : les applications trouvees au dernier scan de chaque machine (Registre, Updater, Reparer) ;
- `liaisons` : les liaisons relevees au dernier scan (Liaisons, Dashboard, Reparer, charge distribuee) ;
- `scans` : l'historique des scans (date, machine, joignable ou non, nombre d'applications).

Meme interface que l'ancien `FileParcStore` (`load`, `save`, `remove`) : les ecrans n'y voient pas de difference.
Au premier lancement, `parc.json` est repris puis garde a cote (`parc.json.repris-<date>`), jamais efface. Sous
sudo, la base est rendue au proprietaire du dossier (jamais un fichier root dans le dossier de l'utilisateur)."""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from omega_connect.domain.parc import MachineEntry, parc_from_dict, parc_to_dict
from omega_connect.infrastructure.fleet.parc_store import FileParcStore
from omega_connect.infrastructure.zone.system import running_as_root

DB_FILE = "omega-connect.db"
SCHEMA_VERSION = 1
SCAN_HISTORY = 500
"""Scans gardes dans l'historique (les plus recents)."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS machines (
    key TEXT PRIMARY KEY, position INTEGER NOT NULL, name TEXT NOT NULL, local INTEGER NOT NULL,
    scanned_at TEXT NOT NULL, fingerprint TEXT NOT NULL, addresses TEXT NOT NULL, target TEXT NOT NULL,
    reachable INTEGER NOT NULL, last_error TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS applications (
    machine_key TEXT NOT NULL REFERENCES machines(key) ON DELETE CASCADE, position INTEGER NOT NULL,
    tool TEXT NOT NULL, root TEXT NOT NULL, instance TEXT NOT NULL, service_state TEXT NOT NULL,
    version TEXT NOT NULL, state TEXT NOT NULL, suite TEXT NOT NULL, suite_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS liaisons (
    machine_key TEXT NOT NULL REFERENCES machines(key) ON DELETE CASCADE, position INTEGER NOT NULL,
    kind TEXT NOT NULL, root TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, machine_key TEXT NOT NULL, machine TEXT NOT NULL,
    scanned_at TEXT NOT NULL, reachable INTEGER NOT NULL, applications INTEGER NOT NULL, error TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS applications_machine ON applications(machine_key);
CREATE INDEX IF NOT EXISTS liaisons_machine ON liaisons(machine_key);
"""

_APP_FIELDS = ("tool", "root", "instance", "service_state", "version", "state", "suite", "suite_version")


class SqliteParcStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._path = directory / DB_FILE
        self._lock = threading.Lock()
        self._ready = False

    # ---- interface du registre du parc ----
    def load(self) -> tuple[MachineEntry, ...]:
        if not self._path.is_file() and not (self._directory / "parc.json").is_file():
            return ()
        try:
            with self._connect() as db:
                return self._read(db)
        except (OSError, sqlite3.Error):
            return ()

    def save(self, machine: MachineEntry) -> None:
        with self._connect() as db:
            if machine.local:  # une seule « cette machine »
                for (key,) in db.execute("SELECT key FROM machines WHERE local = 1 AND key != ?", (machine.key,)):
                    db.execute("DELETE FROM machines WHERE key = ?", (key,))
            known = db.execute("SELECT position FROM machines WHERE key = ?", (machine.key,)).fetchone()
            if machine.local:
                position = -1
            elif known is not None:
                position = known[0]
            else:
                position = (db.execute("SELECT COALESCE(MAX(position), 0) FROM machines").fetchone()[0] or 0) + 1
            self._write_machine(db, machine, position)
            db.execute("INSERT INTO scans (machine_key, machine, scanned_at, reachable, applications, error) "
                       "VALUES (?, ?, ?, ?, ?, ?)", (machine.key, machine.label, machine.scanned_at,
                                                     int(machine.reachable), len(machine.rows), machine.last_error))
            db.execute("DELETE FROM scans WHERE id NOT IN (SELECT id FROM scans ORDER BY id DESC LIMIT ?)",
                       (SCAN_HISTORY,))

    def remove(self, key: str) -> bool:
        with self._connect() as db:
            done = db.execute("DELETE FROM machines WHERE key = ? AND local = 0", (key,))
            return done.rowcount > 0

    def scans(self, limit: int = 50) -> list[dict[str, object]]:
        """Historique des scans, le plus recent d'abord."""
        with self._connect() as db:
            rows = db.execute("SELECT machine, scanned_at, reachable, applications, error FROM scans "
                              "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"machine": r[0], "scanned_at": r[1], "reachable": bool(r[2]), "applications": r[3],
                 "error": r[4]} for r in rows]

    # ---- interne ----
    @contextlib.contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._directory.mkdir(parents=True, exist_ok=True)
            if self._path.is_symlink():
                raise OSError(f"{self._path} est un lien")
            created = not self._path.exists()
            db = sqlite3.connect(self._path, timeout=10)
            try:
                db.execute("PRAGMA foreign_keys = ON")
                if not self._ready:
                    db.executescript(SCHEMA)
                    db.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                               (str(SCHEMA_VERSION),))
                    self._take_over_json(db)
                    db.commit()
                    self._ready = True
                with db:
                    yield db
            finally:
                db.close()
                if created:
                    self._fix_owner()

    def _take_over_json(self, db: sqlite3.Connection) -> None:
        """Premier lancement : parc.json repris une fois, puis garde a cote (jamais efface)."""
        if db.execute("SELECT COUNT(*) FROM machines").fetchone()[0]:
            return
        legacy = self._directory / "parc.json"
        if not legacy.is_file() or legacy.is_symlink():
            return
        machines = FileParcStore(self._directory).load()
        for position, machine in enumerate(machines):
            self._write_machine(db, machine, -1 if machine.local else position + 1)
        legacy.rename(legacy.with_name(f"parc.json.repris-{datetime.now():%Y%m%d-%H%M%S}"))

    @staticmethod
    def _write_machine(db: sqlite3.Connection, machine: MachineEntry, position: int) -> None:
        raw = parc_to_dict([machine])["machines"][0]  # type: ignore[index]
        db.execute("DELETE FROM machines WHERE key = ?", (machine.key,))
        db.execute("INSERT INTO machines (key, position, name, local, scanned_at, fingerprint, addresses, target, "
                   "reachable, last_error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (machine.key, position, raw["name"], int(raw["local"]), raw["scanned_at"], raw["fingerprint"],
                    json.dumps(raw["addresses"]), raw["target"], int(raw["reachable"]), raw["last_error"]))
        for index, app in enumerate(raw["applications"]):
            db.execute("INSERT INTO applications (machine_key, position, tool, root, instance, service_state, "
                       "version, state, suite, suite_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (machine.key, index, *(str(app.get(field, "")) for field in _APP_FIELDS)))
        for index, link in enumerate(raw["links"]):
            db.execute("INSERT INTO liaisons (machine_key, position, kind, root, data) VALUES (?, ?, ?, ?, ?)",
                       (machine.key, index, str(link.get("kind", "")), str(link.get("root", "")),
                        json.dumps(link, ensure_ascii=False)))

    @staticmethod
    def _read(db: sqlite3.Connection) -> tuple[MachineEntry, ...]:
        machines = []
        for row in db.execute("SELECT key, name, local, scanned_at, fingerprint, addresses, target, reachable, "
                              "last_error FROM machines ORDER BY position, key").fetchall():
            key = row[0]
            apps = [dict(zip(_APP_FIELDS, app, strict=True)) for app in db.execute(
                "SELECT " + ", ".join(_APP_FIELDS) + " FROM applications WHERE machine_key = ? ORDER BY position",
                (key,))]
            for app in apps:  # meme forme que parc.json : champs de la suite seulement s'ils existent
                if not app["suite"]:
                    del app["suite"], app["suite_version"]
            links = [json.loads(data) for (data,) in db.execute(
                "SELECT data FROM liaisons WHERE machine_key = ? ORDER BY position", (key,))]
            try:
                addresses = json.loads(row[5])
            except ValueError:
                addresses = []
            machines.append({"name": row[1], "local": bool(row[2]), "scanned_at": row[3], "fingerprint": row[4],
                             "addresses": addresses, "target": row[6], "reachable": bool(row[7]),
                             "last_error": row[8], "applications": apps, "links": links})
        data = parc_to_dict([])
        data["machines"] = machines
        return parc_from_dict(data)

    def _fix_owner(self) -> None:
        with contextlib.suppress(OSError):
            os.chmod(self._path, 0o644)
            if running_as_root():
                owner = self._directory.parent.stat()
                os.chown(self._path, owner.st_uid, owner.st_gid)
                os.chown(self._directory, owner.st_uid, owner.st_gid)
