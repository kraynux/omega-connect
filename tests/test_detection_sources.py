# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sources de la detection (lot A) : recherche bornee, registre omega-serv, services, saisie, HOME sous sudo."""
from __future__ import annotations

import json
import os
import pwd
from pathlib import Path

from conftest import make_installation

from omega_connect.domain.detection import NoteKind, Source
from omega_connect.infrastructure.detection.filesystem_scan import (
    FilesystemScanLocator,
    ManualLocator,
    network_mount_points,
)
from omega_connect.infrastructure.detection.home import target_home
from omega_connect.infrastructure.detection.serv_registry import ServRegistryLocator
from omega_connect.infrastructure.detection.service_units import ServiceUnitsLocator


def _scan(home: Path, mounts: Path, depth: int = 3, **kwargs) -> FilesystemScanLocator:
    return FilesystemScanLocator(home, depth, Source.HOME, mounts_file=str(mounts), **kwargs)


def test_scan_finds_installations_within_depth_only(fake_system):
    home = fake_system["home"]
    make_installation(home / "omega-serv", "omega-serv", token_id="a" * 32)
    make_installation(home / "DEV" / "FIRE" / "omega-fire", "omega-fire")
    make_installation(home / "a" / "b" / "c" / "omega-jail", "omega-jail")  # profondeur 4 : hors limite
    roots = [c.root for c in _scan(home, fake_system["mounts"]).candidates()]
    assert roots == sorted([str(home / "DEV" / "FIRE" / "omega-fire"), str(home / "omega-serv")])


def test_scan_skips_symlinks_hidden_backups_and_venvs(fake_system):
    home = fake_system["home"]
    real = make_installation(fake_system["srv"] / "omega-serv", "omega-serv")
    (home / "lien").symlink_to(real)  # jamais suivi
    make_installation(home / ".cache" / "omega-serv", "omega-serv")
    make_installation(home / "omega-serv.old-20261018", "omega-serv")
    make_installation(home / ".venv" / "omega-serv", "omega-serv")
    make_installation(home / "node_modules" / "omega-fire", "omega-fire")
    for name in ("omega-fire-bak", "omega-serv.bak", "omega-serv_BAK", "omega-fire.bak-20261110"):
        make_installation(home / "DEV" / name, "omega-fire")  # copies de sauvegarde (decision 2026-11-10)
    assert _scan(home, fake_system["mounts"]).candidates() == []


def test_backup_rule_does_not_hide_real_names(fake_system):
    home = fake_system["home"]
    make_installation(home / "omega-serv-bakery", "omega-serv")  # « bak » au milieu d'un mot : pas une sauvegarde
    assert [candidate.root.rsplit("/", 1)[-1] for candidate in _scan(home, fake_system["mounts"]).candidates()] == [
        "omega-serv-bakery"]


def test_scan_never_enters_network_mounts(fake_system):
    home = fake_system["home"]
    share = home / "Reseau" / "nas home"
    make_installation(share / "omega-serv", "omega-serv")
    fake_system["mounts"].write_text(
        f"//nas/home {str(share).replace(' ', chr(92) + '040')} cifs rw 0 0\n"
        "server:/x /mnt/x nfs4 rw 0 0\n/dev/sda1 / ext4 rw 0 0\n", encoding="utf-8")
    assert str(share) in network_mount_points(str(fake_system["mounts"]))
    locator = _scan(home, fake_system["mounts"])
    assert locator.candidates() == []
    assert [(n.kind, n.detail) for n in locator.notes()] == [(NoteKind.NETWORK_MOUNT_SKIPPED, str(share))]


def test_scan_does_not_descend_into_an_installation(fake_system):
    home = fake_system["home"]
    outer = make_installation(home / "omega-serv", "omega-serv")
    make_installation(outer / "copie", "omega-serv")
    assert [c.root for c in _scan(home, fake_system["mounts"]).candidates()] == [str(outer)]


def test_scan_stops_after_max_directories(fake_system):
    home = fake_system["home"]
    for index in range(10):
        (home / f"d{index}").mkdir()
    locator = _scan(home, fake_system["mounts"], max_directories=3)
    locator.candidates()
    assert locator.visited == 3
    assert locator.notes()[0].kind is NoteKind.SEARCH_STOPPED


def test_serv_registry(fake_system):
    home = fake_system["home"]
    instance = make_installation(home / "blog", "omega-serv")
    registry = home / ".config" / "omega-serv" / "instances.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps([
        {"name": "blog", "path": str(instance), "service_name": "omega-serv-blog"},
        {"name": "disparue", "path": str(home / "disparue"), "service_name": "omega-serv-x"},
    ]), encoding="utf-8")
    locator = ServRegistryLocator(home)
    found = locator.candidates()
    assert [(c.root, c.service_name, c.tool_hint) for c in found] == [
        (str(instance), "omega-serv-blog", "omega-serv")]
    assert locator.notes()[0].kind is NoteKind.REGISTERED_INSTANCE_MISSING
    registry.write_text("{casse", encoding="utf-8")
    assert locator.candidates() == [] and locator.notes()[0].kind is NoteKind.REGISTRY_UNREADABLE


def test_service_units_systemd_openrc_runit(fake_system):
    main = make_installation(fake_system["home"] / "omega-serv", "omega-serv")
    blog = make_installation(fake_system["srv"] / "blog", "omega-serv")
    shop = make_installation(fake_system["srv"] / "shop", "omega-serv")
    (fake_system["systemd"] / "omega-serv.service").write_text(
        f"ExecStart={main}/.venv/bin/python -m omega_serv --config {main}/config/omega-serve.json serve\n")
    (fake_system["systemd"] / "omega-serv-log-rotation.service").write_text(
        f"ExecStart={main}/.venv/bin/python -m omega_serv logs run-automations\nWorkingDirectory={main}\n")
    (fake_system["openrc"] / "omega-serv-blog").write_text(
        f'#!/sbin/openrc-run\ndirectory="{blog}"\ncommand_args="--config {blog}/config/omega-serve.json serve"\n')
    (fake_system["runit"] / "omega-serv-shop").mkdir()
    (fake_system["runit"] / "omega-serv-shop" / "run").write_text(
        f"#!/bin/sh\ncd {shop}\nexec chpst -u omega-serv ./omega-serv.sh serve\n")
    (fake_system["systemd"] / "omega-serv-perdu.service").write_text(
        "ExecStart=/nulle/part/.venv/bin/python -m omega_serv --config /nulle/part/config/omega-serve.json serve\n")
    locator = ServiceUnitsLocator(str(fake_system["systemd"]), str(fake_system["openrc"]), str(fake_system["runit"]))
    found = {(c.source, c.service_name): c.root for c in locator.candidates()}
    assert found == {(Source.SYSTEMD, "omega-serv"): str(main), (Source.OPENRC, "omega-serv-blog"): str(blog),
                     (Source.RUNIT, "omega-serv-shop"): str(shop)}
    assert [n.kind for n in locator.notes()] == [NoteKind.SERVICE_ROOT_MISSING]


def test_manual_paths(fake_system):
    installation = make_installation(fake_system["srv"] / "omega-fire", "omega-fire")
    locator = ManualLocator([str(installation), str(fake_system["srv"] / "absent"), str(fake_system["home"])])
    assert [c.root for c in locator.candidates()] == [str(installation)]
    assert [n.kind for n in locator.notes()] == [NoteKind.MANUAL_NOT_FOUND, NoteKind.MANUAL_NOT_OMEGA]


def test_target_home_under_sudo_is_the_invoking_user():
    user = pwd.getpwuid(os.getuid())
    assert target_home({"SUDO_USER": user.pw_name}, euid=0) == Path(user.pw_dir)
    assert target_home({}, euid=os.getuid()) == Path(user.pw_dir)
