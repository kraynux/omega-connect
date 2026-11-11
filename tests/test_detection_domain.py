# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regles pures de la detection (lot A)."""
from __future__ import annotations

import pytest
from omega_lib.synchro.models import InstallToken, ReadStatus

from omega_connect.domain.detection import (
    Candidate,
    DetectedInstallation,
    Source,
    find_duplicate_ids,
    is_server_service,
    merge_candidates,
    parse_service_root,
    tool_for,
)


def test_merge_keeps_one_entry_per_root_with_ordered_sources():
    merged = merge_candidates([
        Candidate("/b", Source.HOME), Candidate("/a", Source.HOME),
        Candidate("/a", Source.SYSTEMD, "omega-serv", "omega-serv"),
        Candidate("/a", Source.SERV_REGISTRY, "omega-serv", "omega-serv"),
    ])
    assert [m.root for m in merged] == ["/a", "/b"]
    assert merged[0].sources == (Source.SERV_REGISTRY, Source.SYSTEMD, Source.HOME)
    assert merged[0].tool_hint == "omega-serv" and merged[0].service_names == ("omega-serv",)


@pytest.mark.parametrize(("text", "root"), [
    ("ExecStart=/x/.venv/bin/python -m omega_serv --config /srv/blog/config/omega-serve.json serve\n"
     "WorkingDirectory=/ailleurs\n", "/srv/blog"),
    ("[Service]\nWorkingDirectory=/home/k/omega-serv\n", "/home/k/omega-serv"),
    ('#!/sbin/openrc-run\ndirectory="/srv/omega-serv"\ncommand=/srv/omega-serv/omega-serv.sh\n', "/srv/omega-serv"),
    ("#!/bin/sh\ncd /opt/omega-serv-b\nexec chpst -u omega-serv ./omega-serv.sh serve\n", "/opt/omega-serv-b"),
    ("WorkingDirectory=relatif/dossier\n", None),
    ("cd /srv/../etc\n", None),
    ("cd $HOME/omega-serv\n", None),
    ("rien\n", None),
])
def test_parse_service_root(text, root):
    assert parse_service_root(text) == root


def test_server_service_vs_side_task():
    assert is_server_service("ExecStart=/r/.venv/bin/python -m omega_serv --config /r/config/omega-serve.json serve")
    assert is_server_service("exec chpst -u omega-serv ./omega-serv.sh serve")
    assert not is_server_service("ExecStart=/r/.venv/bin/python -m omega_serv logs run-automations")


def _token(identifier: str, tool: str = "omega-serv") -> InstallToken:
    return InstallToken(tool, "1.0", identifier, "m", "/x", "k", "2026-11-10T00:00:00Z", "2026-11-10T00:00:00Z")


def test_duplicate_ids_are_reported_not_merged():
    same = "a" * 32
    items = [DetectedInstallation(root, "omega-serv", (Source.HOME,), "k", ReadStatus.OK, _token(same))
             for root in ("/a", "/b")]
    items.append(DetectedInstallation("/c", "omega-serv", (Source.HOME,), "k", ReadStatus.OK, _token("b" * 32)))
    duplicates = find_duplicate_ids(items)
    assert len(duplicates) == 1 and duplicates[0].roots == ("/a", "/b")


def test_tool_for_prefers_token_then_layout_then_hint():
    assert tool_for(_token("a" * 32, "omega-fire"), "omega-serv", "omega-serv") == "omega-fire"
    assert tool_for(None, "omega-jail", "omega-serv") == "omega-jail"
    assert tool_for(None, "", "omega-serv") == "omega-serv"
