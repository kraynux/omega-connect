# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Groupe de la zone pris au lancement : jamais de relance en boucle, ni pour un groupe inexistant, ni sans terminal
quand seul newgrp existe ; arguments proteges."""
from __future__ import annotations

import grp
import os
import shlex
import sys

from omega_connect.infrastructure.session import zone_group


def test_guard_and_unknown_group_never_relaunch():
    assert not zone_group.needs_switch(environ={zone_group.GUARD: "1"})
    assert not zone_group.needs_switch("groupe-qui-n-existe-pas-xyz", environ={})


def test_a_group_already_in_the_session_needs_nothing():
    current = grp.getgrgid(os.getgid()).gr_name
    assert not zone_group.needs_switch(current, environ={})


def test_arguments_are_quoted():
    command = zone_group.switch_command(["verifier", "--chemin", "/a b/l'outil"])
    assert shlex.split(command) == [sys.executable, "-m", "omega_connect", "verifier", "--chemin", "/a b/l'outil"]


def test_without_sg_and_without_terminal_nothing_happens(monkeypatch):
    monkeypatch.setattr(zone_group, "needs_switch", lambda _group: True)
    monkeypatch.setattr(zone_group.shutil, "which", lambda name: None if name == "sg" else "/usr/bin/newgrp")
    monkeypatch.setattr(zone_group.sys.stdin, "isatty", lambda: False, raising=False)
    assert zone_group.relaunch_with_zone_group(["verifier"]) is None
