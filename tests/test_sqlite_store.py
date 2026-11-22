# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Registre du parc en SQLite (decision de l'auteur, 2026-11-22) : memes entrees que parc.json, une table par
fonction, parc.json repris une fois puis garde a cote, historique des scans."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from omega_connect.domain.fleet import AppState, RegistryRow
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind
from omega_connect.domain.parc import MachineEntry
from omega_connect.infrastructure.fleet.parc_store import FileParcStore
from omega_connect.infrastructure.fleet.sqlite_store import DB_FILE, SqliteParcStore

AT, LATER = "2026-11-22T10:00:00Z", "2026-11-22T11:00:00Z"


def _local(at: str = AT) -> MachineEntry:
    rows = (RegistryRow("pc", "omega-stress", "/s/omega-suite/vendor/omega-stress", "", "", "2.0.0",
                        AppState.ENROLLED, (), "/s/omega-suite", "1.7.0"),
            RegistryRow("pc", "omega-fire", "/f", "", "", "3.6.2", AppState.LINKED))
    return MachineEntry("pc", True, at, rows)


def _remote(name: str = "mpc", reachable: bool = True) -> MachineEntry:
    link = Link(LinkKind.TOKENS, "", "", (Check(CheckCode.TOKEN_OK, CheckStatus.OK, "/x", "abcd"),), machine=name)
    return MachineEntry(name, False, AT, (RegistryRow(name, "omega-jail", "/j", "", "", "1.2.1", AppState.LINKED),),
                        name[0] * 16, ("192.168.1.5",), f"kr@{name}", reachable, (link,), "" if reachable else "x")


def test_aller_retour_et_une_seule_machine_locale(tmp_path: Path) -> None:
    store = SqliteParcStore(tmp_path / "var")
    assert store.load() == ()
    store.save(_local())
    store.save(_remote("mpc"))
    store.save(_remote("craftdark"))
    store.save(_local(LATER))
    machines = store.load()
    assert [m.name for m in machines] == ["pc", "mpc", "craftdark"]  # cette machine d'abord, puis l'ordre d'ajout
    assert machines[0].scanned_at == LATER and machines[0].rows == _local().rows  # suite gardee
    assert machines[1] == _remote("mpc")  # liaisons et adresses gardees
    store.save(_remote("mpc", reachable=False))
    assert [m.name for m in store.load()] == ["pc", "mpc", "craftdark"]  # place gardee au rescan
    assert not store.remove("pc") and store.remove(_remote("mpc").key) and not store.remove("rien")
    assert [m.name for m in store.load()] == ["pc", "craftdark"]
    db = sqlite3.connect(tmp_path / "var" / DB_FILE)
    assert db.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 3  # pc (2) + craftdark (1)
    assert db.execute("SELECT COUNT(*) FROM liaisons").fetchone()[0] == 1
    assert len(store.scans()) == 5 and store.scans(1)[0]["machine"].startswith("mpc")


def test_parc_json_repris_une_fois_puis_garde(tmp_path: Path) -> None:
    var = tmp_path / "var"
    old = FileParcStore(var)
    old.save(_local())
    old.save(_remote("mpc"))
    store = SqliteParcStore(var)
    assert [m.name for m in store.load()] == ["pc", "mpc"]
    assert not (var / "parc.json").exists()
    kept = list(var.glob("parc.json.repris-*"))
    assert len(kept) == 1 and kept[0].stat().st_size > 0
    assert [m.name for m in SqliteParcStore(var).load()] == ["pc", "mpc"]  # pas repris deux fois
