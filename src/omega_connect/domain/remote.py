# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scanner distant (refonte du parcours, lot R2 ; ~/DEV/CONNECT/ETUDE_REFONTE_PARCOURS_OMEGA_CONNECT.md §14).

Regles pures : cible `utilisateur@machine` (jamais une option deguisee), format du resultat renvoye par le scanner
envoye sur la machine distante (`omega-connect-scan-distant` v1), causes d'echec lisibles. L'identite d'une machine
est son empreinte (celle des cartes d'identite, tiree de /etc/machine-id), jamais son adresse : une machine jointe
par deux reseaux reste une, deux machines de meme adresse sur deux reseaux restent deux."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from omega_connect.domain.fleet import AppState, RegistryRow
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind

SCAN_FORMAT = "omega-connect-scan-distant"
SCAN_SCHEMA_VERSION = 1
MAX_SCAN_BYTES = 4 * 1024 * 1024

_USER = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}$")
_HOST = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,252})$")
_IPV6 = re.compile(r"^[0-9A-Fa-f:]{2,39}$")


@dataclass(frozen=True)
class RemoteTarget:
    user: str
    host: str

    @property
    def text(self) -> str:
        return f"{self.user}@{self.host}" if self.user else self.host


def parse_target(text: str) -> RemoteTarget | None:
    """`utilisateur@machine` ou `machine` ; None si la saisie pourrait etre prise pour une option de ssh ou contient
    autre chose qu'un nom ou une adresse (espaces, guillemets, `-o...`)."""
    value = text.strip()
    user, _sep, host = value.rpartition("@")
    if not host or host.startswith("-") or (user and not _USER.match(user)):
        return None
    host = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    if not (_HOST.match(host) or (":" in host and _IPV6.match(host))):
        return None
    return RemoteTarget(user, host)


class RemoteFailure(str, Enum):
    UNREACHABLE = "unreachable"
    """Machine injoignable : delai depasse, pas de route, reseau coupe."""
    UNKNOWN_NAME = "unknown-name"
    """Nom de machine introuvable (pas de DNS local) : utiliser l'adresse, ou /etc/hosts, ou ~/.ssh/config."""
    NO_SSH_SERVER = "no-ssh-server"
    """La machine repond mais aucun serveur SSH n'ecoute (« Connection refused »)."""
    AUTHENTICATION = "authentication"
    """Aucune de vos cles n'est acceptee (ou cle protegee sans agent SSH)."""
    UNKNOWN_HOST = "unknown-host"
    """Clef de la machine jamais vue : a confirmer par la personne."""
    CHANGED_HOST = "changed-host"
    """Clef de la machine CHANGEE depuis la derniere fois : refus (possible usurpation)."""
    NO_PYTHON = "no-python"
    """Pas de Python 3 (>= 3.10) sur la machine distante."""
    SCAN_FAILED = "scan-failed"
    """Le scanner a echoue ou a renvoye autre chose que le format attendu."""
    NO_SSH = "no-ssh"
    """Pas de client ssh sur cette machine."""


class HostKey(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    CHANGED = "changed"
    FAILED = "failed"


@dataclass(frozen=True)
class HostCheck:
    """Clef de la machine distante, verifiee AVANT tout scan (§14 de l'etude, point 3)."""

    target: RemoteTarget
    key: HostKey
    fingerprints: tuple[str, ...] = ()
    """Empreintes a montrer a la personne (machine inconnue)."""
    pending: bytes = b""
    """Lignes `known_hosts` a ajouter si la personne fait confiance a la machine."""
    failure: RemoteFailure | None = None
    detail: str = ""


@dataclass(frozen=True)
class RemoteScan:
    hostname: str
    fingerprint: str
    scanned_at: str
    rows: tuple[RegistryRow, ...]
    links: tuple[Link, ...]


# ---- liens <-> dictionnaires (aussi gardes dans le registre du parc) -----------------------------

def links_to_list(links: Iterable[Link]) -> list[dict[str, Any]]:
    return [{"kind": link.kind.value, "instance": link.instance, "root": link.root, "machine": link.machine,
             "peer": link.peer,
             "checks": [{"code": check.code.value, "status": check.status.value, "subject": check.subject,
                         "detail": check.detail, "fix": check.fix, "fix_account": check.fix_account}
                        for check in link.checks]}
            for link in links]


def links_from_list(raw: object, machine: str = "") -> tuple[Link, ...]:
    """Lecture tolerante (un lien ou un controle inconnu, d'une version plus recente, est ignore) ; `machine` :
    machine ou les liens ont ete vus (provenance « Reseau »)."""
    links = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            kind = LinkKind(item.get("kind"))
        except ValueError:
            continue
        checks = []
        for check in item.get("checks") or []:
            if not isinstance(check, dict):
                continue
            try:
                checks.append(Check(CheckCode(check.get("code")), CheckStatus(check.get("status")),
                                    str(check.get("subject", "")), str(check.get("detail", "")),
                                    str(check.get("fix", "")), str(check.get("fix_account", ""))))
            except ValueError:
                continue
        links.append(Link(kind, str(item.get("instance", "")), str(item.get("root", "")), tuple(checks),
                          machine or str(item.get("machine", "")), str(item.get("peer", ""))))
    return tuple(links)


def rows_to_list(rows: Iterable[RegistryRow]) -> list[dict[str, str]]:
    return [{"tool": row.tool, "root": row.root, "instance": row.instance, "service_state": row.service_state,
             "version": row.version, "state": row.state.value} for row in rows]


def rows_from_list(raw: object, machine: str) -> tuple[RegistryRow, ...]:
    rows = []
    for app in raw if isinstance(raw, list) else []:
        try:
            rows.append(RegistryRow(machine, str(app["tool"]), str(app["root"]), str(app.get("instance", "")),
                                    str(app.get("service_state", "")), str(app.get("version", "")),
                                    AppState(app.get("state"))))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return tuple(rows)


def scan_to_dict(scan: RemoteScan) -> dict[str, Any]:
    return {"format": SCAN_FORMAT, "schema_version": SCAN_SCHEMA_VERSION, "hostname": scan.hostname,
            "machine": scan.fingerprint, "scanned_at": scan.scanned_at, "applications": rows_to_list(scan.rows),
            "links": links_to_list(scan.links)}


def scan_from_dict(data: object) -> RemoteScan | None:
    """None : pas le format attendu (ou version future)."""
    if not isinstance(data, dict) or data.get("format") != SCAN_FORMAT:
        return None
    version = data.get("schema_version")
    if not isinstance(version, int) or version > SCAN_SCHEMA_VERSION:
        return None
    hostname = data.get("hostname")
    fingerprint = data.get("machine")
    if not isinstance(hostname, str) or not hostname or not isinstance(fingerprint, str):
        return None
    hostname = hostname[:64]
    return RemoteScan(hostname, fingerprint, str(data.get("scanned_at", "")),
                      rows_from_list(data.get("applications"), hostname),
                      links_from_list(data.get("links"), hostname))


# ---- machines que cet ordinateur sait deja joindre (retour de l'auteur, 2026-11-10) ----------------

class SuggestionSource(str, Enum):
    UNISON = "unison"
    """Profil Unison `root = ssh://utilisateur@machine/...` : ces acces marchent deja."""
    SSH_CONFIG = "ssh-config"
    """`Host` de ~/.ssh/config (alias, utilisateur, port y sont regles)."""
    KNOWN_HOSTS = "known-hosts"
    """Machine dont SSH connait deja la clef (nom lisible, non hache)."""


@dataclass(frozen=True)
class Suggestion:
    target: RemoteTarget
    sources: tuple[SuggestionSource, ...]


_UNISON_ROOT = re.compile(r"^\s*root\s*=\s*ssh://(?:(?P<user>[^@/\s]+)@)?(?P<host>\[[^\]]+\]|[^/:\s]+)", re.MULTILINE)
LOCAL_NAMES = frozenset({"localhost", "127.0.0.1", "::1", "ip6-localhost"})


def unison_targets(text: str) -> tuple[RemoteTarget, ...]:
    found = []
    for match in _UNISON_ROOT.finditer(text):
        target = parse_target(f"{match.group('user')}@{match.group('host')}" if match.group("user")
                              else match.group("host"))
        if target is not None:
            found.append(target)
    return tuple(found)


def ssh_config_hosts(text: str) -> tuple[RemoteTarget, ...]:
    """Noms `Host` sans joker : ssh y applique lui-meme utilisateur, adresse et port."""
    found = []
    for raw in text.splitlines():
        words = raw.strip().split()
        if len(words) < 2 or words[0].lower() != "host":
            continue
        for name in words[1:]:
            if any(char in name for char in "*?!"):
                continue
            target = parse_target(name)
            if target is not None:
                found.append(target)
    return tuple(found)


def known_hosts_names(text: str) -> tuple[RemoteTarget, ...]:
    """Noms et adresses en clair de known_hosts (les lignes hachees `|1|` ne se lisent pas, c'est voulu)."""
    found = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "|", "@")):
            continue
        for name in line.split()[0].split(","):
            host = name[1:].split("]:")[0] if name.startswith("[") else name
            target = parse_target(host)
            if target is not None:
                found.append(target)
    return tuple(found)


def merge_suggestions(sources: Iterable[tuple[SuggestionSource, Iterable[RemoteTarget]]], default_user: str,
                      own_names: Iterable[str] = ()) -> tuple[Suggestion, ...]:
    """Une ligne par machine (par adresse ou nom) ; l'utilisateur d'Unison ou de la saisie prime, sinon le votre ;
    cette machine elle-meme est ecartee."""
    excluded = {name.lower() for name in (*LOCAL_NAMES, *own_names)}
    merged: dict[str, tuple[RemoteTarget, list[SuggestionSource]]] = {}
    for source, targets in sources:
        for target in targets:
            host = target.host.lower()
            if host in excluded or host.startswith("127."):
                continue
            known = merged.get(host)
            if known is None:
                merged[host] = (target, [source])
            else:
                best = known[0] if known[0].user else target
                if source not in known[1]:
                    known[1].append(source)
                merged[host] = (best, known[1])
    result = []
    for target, kinds in merged.values():
        user = target.user if target.user or SuggestionSource.SSH_CONFIG in kinds else default_user
        result.append(Suggestion(RemoteTarget(user, target.host), tuple(kinds)))
    order = {SuggestionSource.UNISON: 0, SuggestionSource.SSH_CONFIG: 1, SuggestionSource.KNOWN_HOSTS: 2}
    return tuple(sorted(result, key=lambda item: (min(order[kind] for kind in item.sources), item.target.host)))
