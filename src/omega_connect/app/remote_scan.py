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
import sys
from datetime import datetime, timezone
from pathlib import Path

from omega_lib.infrastructure.synchro.install_token import read_machine_fingerprint
from omega_lib.synchro.policies import format_utc

from omega_connect.app.main import build_detect, build_verify, build_zone
from omega_connect.domain.fleet import registry_rows
from omega_connect.domain.remote import RemoteScan, scan_to_dict
from omega_connect.interfaces.cli.main import DetectRequest

TEST_DIRS_ENV = {"systemd_dir": "OMEGA_CONNECT_SYSTEMD_DIR", "openrc_dir": "OMEGA_CONNECT_OPENRC_DIR",
                 "runit_dir": "OMEGA_CONNECT_RUNIT_DIR", "srv_dir": "OMEGA_CONNECT_SRV_DIR"}
"""Dossiers remplacables pour les tests (comme OMEGA_SYNCHRO_DIR) : jamais le vrai /etc pendant un test."""
FAIL2BAN_DIR_ENV = "OMEGA_CONNECT_FAIL2BAN_DIR"
HOME_ENV = "OMEGA_CONNECT_HOME"
"""Dossier personnel a examiner a la place de celui du compte (tests seulement)."""


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
    scan = RemoteScan(hostname, read_machine_fingerprint(), format_utc(datetime.now(timezone.utc)),
                      registry_rows(report, facts, hostname), report.links)
    sys.stdout.write(json.dumps(scan_to_dict(scan), ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
