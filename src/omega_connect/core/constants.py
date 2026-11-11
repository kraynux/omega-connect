# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Constantes d'omega-connect (spec ~/DEV/CONNECT/SPEC_ETAPE3_OMEGA_CONNECT_PLOMBERIE.md)."""
from __future__ import annotations

APP_NAME = "omega-connect"

# Recherche des installations (Q4, decision de l'auteur du 2026-11-10) : bornee, sans /opt.
HOME_SCAN_DEPTH = 3
SRV_SCAN_DEPTH = 2
SRV_DIR = "/srv"
SCAN_MAX_DIRECTORIES = 20_000
"""Garde-fou : au-dela, la recherche s'arrete et le signale (jamais de balayage sans fin)."""
SKIPPED_DIRECTORY_NAMES = frozenset({".venv", "venv", "node_modules", "__pycache__", "site-packages"})
OLD_DIRECTORY_MARKER = ".old-"
"""Dossiers de sauvegarde d'une mise a jour (`omega-serv.old-20261018`) : jamais pris pour une installation."""
BACKUP_DIRECTORY_PATTERN = r"[._-]bak(?:[._-]|$)"
"""Copies de sauvegarde (`omega-fire-bak`, `omega-serv.bak`, `omega-fire_bak-2026`...) : jamais examinees par la
recherche (decision de l'auteur, 2026-11-10 : une ancienne copie s'elevait avec sudo pendant la detection).
Un dossier donne explicitement avec --chemin reste examine."""

NETWORK_FILESYSTEMS = frozenset({
    "cifs", "smb3", "smbfs", "nfs", "nfs4", "fuse.sshfs", "sshfs", "davfs", "fuse.davfs2",
    "fuse.rclone", "fuse.gvfsd-fuse", "9p", "afs", "ceph", "glusterfs", "fuse.glusterfs",
})
"""Montages reseau jamais parcourus (un partage Samba dans le HOME ferait balayer le reseau local)."""

# Services omega-serv (systemd, OpenRC, runit).
SYSTEMD_UNIT_DIR = "/etc/systemd/system"
OPENRC_INIT_DIR = "/etc/init.d"
RUNIT_SERVICE_DIR = "/etc/sv"
SERV_SERVICE_PREFIX = "omega-serv"
SERV_REGISTRY_RELATIVE = ".config/omega-serv/instances.json"

SHEET_TIMEOUT_SECONDS = 10
SHEET_TOOLS = frozenset({"omega-serv", "omega-fire"})
"""Outils qui produisent une fiche (`synchro fiche`) ; omega-jail n'en a pas (ses fichiers sont a fail2ban)."""

# Verification des liens (lot B) : ce qu'omega-jail a pose dans fail2ban.
FAIL2BAN_DIR = "/etc/fail2ban"
FAIL2BAN_CONFIG_SIZE_LIMIT = 1_000_000
"""Un fichier de jail ou d'action plus gros n'est pas lu (ceux d'omega-jail font quelques centaines d'octets)."""

# Tableau de bord (lot C) : nouvelle verification tant que l'ecran est ouvert, jamais de demon.
DASHBOARD_REFRESH_SECONDS = 120.0
"""Une verification complete dure quelques secondes (recherche + fiches) : toutes les 2 minutes suffit."""

# Zone neutre (lot D) : commandes root lancees une a une avec sudo, jamais d'elevation de tout l'outil.
PRIVILEGED_TIMEOUT_SECONDS = 60.0
REPAIR_TIMEOUT_SECONDS = 180.0
"""Commande d'un outil lancee par `reparer` (omega-jail recharge fail2ban, omega-serv parcourt var/)."""
TOKEN_TIMEOUT_SECONDS = 30.0
ZONE_FILE_SIZE_LIMIT = 1_000_000
"""Un registre ou une copie plus gros n'est pas lu (ils font quelques kilo-octets)."""
