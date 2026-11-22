# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Point d'entree du scanner execute SUR la machine distante (lot R2) : envoye en memoire par SSH, rien n'y est
installe ni ecrit. Lecture seule, sous le compte de la connexion : detection, verification des liens, lecture de
l'espace partage sans sudo. Ecrit sur la sortie standard un seul document JSON (`omega-connect-scan-distant` v1).

N'importe jamais Textual ni rich (absents de la machine distante) : seulement la bibliotheque standard, omega-lib
et omega-connect hors interface."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from omega_lib.infrastructure.synchro.install_token import read_machine_fingerprint
from omega_lib.synchro.policies import format_utc

from omega_connect.app.main import build_detect, build_verify, build_zone
from omega_connect.domain.distributed_load import STRESS_LAUNCHER, STRESS_TOOL, facts_link, helper_roots
from omega_connect.domain.fleet import RegistryRow, registry_rows
from omega_connect.domain.links import Link
from omega_connect.domain.remote import RemoteScan, scan_to_dict
from omega_connect.domain.versions import too_old, version_key
from omega_connect.interfaces.cli.main import DetectRequest

TEST_DIRS_ENV = {"systemd_dir": "OMEGA_CONNECT_SYSTEMD_DIR", "openrc_dir": "OMEGA_CONNECT_OPENRC_DIR",
                 "runit_dir": "OMEGA_CONNECT_RUNIT_DIR", "srv_dir": "OMEGA_CONNECT_SRV_DIR"}
"""Dossiers remplacables pour les tests (comme OMEGA_SYNCHRO_DIR) : jamais le vrai /etc pendant un test."""
FAIL2BAN_DIR_ENV = "OMEGA_CONNECT_FAIL2BAN_DIR"
HOME_ENV = "OMEGA_CONNECT_HOME"
"""Dossier personnel a examiner a la place de celui du compte (tests seulement)."""


def stress_helper_links(rows: tuple[RegistryRow, ...] | list[RegistryRow]) -> tuple[Link, ...]:
    """Charge distribuee (lot L2) : etat de chaque omega-stress de cette machine en tant que machine qui aide
    (`worker etat --format json` : lecture seule, jamais de sudo, terminal detache)."""
    links = []
    versions = helper_roots(rows)
    for root, version in versions.items():
        launcher = Path(root) / STRESS_LAUNCHER
        output = None
        if too_old(STRESS_TOOL, version) or version_key(version) is None:
            # Version sans charge distribuee : jamais lancee (elle ne connait pas `worker`).
            links.append(facts_link(root, None, old_version=version or "?"))
            continue
        if launcher.is_file() and not launcher.is_symlink():
            try:
                done = subprocess.run([str(launcher), "worker", "etat", "--format", "json"],  # noqa: S603
                                      capture_output=True, text=True, timeout=30, check=False,
                                      stdin=subprocess.DEVNULL, start_new_session=True, cwd=root,
                                      env={**os.environ, "PATH": "/usr/local/bin:/usr/bin:/bin:"
                                           + os.environ.get("PATH", "")})
                lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
                output = lines[-1] if done.returncode == 0 and lines else None
            except (OSError, subprocess.SubprocessError):
                output = None
        links.append(facts_link(root, output))
    return tuple(links)


def main() -> int:
    hostname = (socket.gethostname() or "?").split(".")[0][:64]
    overrides = {key: os.environ[name] for key, name in TEST_DIRS_ENV.items() if os.environ.get(name)}
    home = os.environ.get(HOME_ENV)
    detect = build_detect(home=Path(home) if home else None, **overrides)  # type: ignore[arg-type]
    zone = build_zone()
    fail2ban = os.environ.get(FAIL2BAN_DIR_ENV)
    verify = build_verify(detect, zone=zone, **({"fail2ban_dir": fail2ban} if fail2ban else {}))
    report = verify(DetectRequest(manual_paths=[], with_sheets=True))
    facts = zone.inspector.inspect(elevated=False)
    rows = registry_rows(report, facts, hostname)
    scan = RemoteScan(hostname, read_machine_fingerprint(), format_utc(datetime.now(timezone.utc)), rows,
                      (*report.links, *stress_helper_links(rows)))
    sys.stdout.write(json.dumps(scan_to_dict(scan), ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
