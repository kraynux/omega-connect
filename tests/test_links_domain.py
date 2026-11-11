# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lecture des fichiers d'omega-jail et etat d'un lien (lot B), sur des temoins rendus par omega-jail lui-meme
(`tests/fixtures/fail2ban/`, produits par render_jail / render_action_conf d'omega-jail 1.2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from omega_connect.domain.fail2ban import jail_file_key, parse_bridge_action, parse_jail_file, riposte_service
from omega_connect.domain.links import Check, CheckCode, CheckStatus, LinkState, link_state

FIXTURES = Path(__file__).parent / "fixtures" / "fail2ban"


def test_jail_rendered_by_omega_jail():
    text = (FIXTURES / "jail-omega-serv-waf-block.conf").read_text(encoding="utf-8")
    jails, error = parse_jail_file("/etc/fail2ban/jail.d/omega-jail-omega-serv-waf-block.conf", text)
    assert error == "" and len(jails) == 1
    jail = jails[0]
    assert jail.name == "omega-serv-waf-block" and jail.enabled
    assert jail.filter == "omega-jail-omega-serv-waf-block"
    assert jail.logpaths == ("/srv/blog/var/log/waf-alerts.log",)
    assert jail.ignoreip == ("100.64.0.0/10", "10.0.0.0/8")  # %(known/ignoreip)s ecarte
    assert jail.actions == ("omega-jail-tailscale-bridge-blog",)  # %(action_)s ecarte
    assert jail.file_key == "waf-log"


def test_damaged_jail_file_is_reported():
    jails, error = parse_jail_file("x.conf", "enabled = true\n[sans fin")
    assert jails == () and error


def test_bridge_action_rendered_by_omega_jail():
    text = (FIXTURES / "action-omega-jail-tailscale-bridge-blog.conf").read_text(encoding="utf-8")
    action = parse_bridge_action("/etc/fail2ban/action.d/omega-jail-tailscale-bridge-blog.conf", text)
    assert action is not None
    assert action.name == "omega-jail-tailscale-bridge-blog"
    assert action.script == "/usr/local/lib/omega-jail/omega-jail-tailscale-bridge.py"
    assert action.servcli == "/srv/blog/.venv/bin/omega-serv"
    assert action.target_root == "/srv/blog"
    assert action.exempt == ("100.64.0.0/10", "10.0.0.0/8")
    assert parse_bridge_action("y.conf", "[Definition]\nactionstart =\n") is None


@pytest.mark.parametrize(("name", "key", "service"), [
    ("omega-serv-scan", "access-log", None),
    ("omega-waf-magnet-alerts", "magnet-alerts-log", None),
    ("omega-serv-blog-riposte-24h", "riposte-decisions", "omega-serv-blog"),
    ("omega-serv-riposte-7d", "riposte-decisions", "omega-serv"),
    ("autre-jail", None, None),
])
def test_jail_names(name, key, service):
    assert jail_file_key(name) == key and riposte_service(name) == service


def test_link_state_precedence():
    def check(status: CheckStatus) -> Check:
        return Check(CheckCode.JAIL_LOG_OK, status)

    assert link_state([]) is LinkState.ABSENT
    assert link_state([check(CheckStatus.INFO)]) is LinkState.ABSENT
    assert link_state([check(CheckStatus.OK)]) is LinkState.ACTIVE
    assert link_state([check(CheckStatus.OK), check(CheckStatus.UNVERIFIABLE)]) is LinkState.UNVERIFIABLE
    assert link_state([check(CheckStatus.UNVERIFIABLE), check(CheckStatus.WARNING)]) is LinkState.DEGRADED
    assert link_state([check(CheckStatus.WARNING), check(CheckStatus.FAILURE)]) is LinkState.BROKEN
