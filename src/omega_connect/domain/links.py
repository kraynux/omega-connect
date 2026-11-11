# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regles de `verifier` (spec etape 3, §3.2) : etat de chaque lien entre outils, a partir de la detection,
de ce qu'omega-jail a pose dans fail2ban et des droits des fichiers partages. Lecture seule : chaque ecart
porte la commande qui le corrigerait, jamais executee ici.

Etat d'un lien, tire de ses controles : casse (un controle en echec), degrade (un avertissement), non
verifiable (sans root, ou fiche manquante), actif (tout est conforme), absent (rien a relier)."""
from __future__ import annotations

import dataclasses
import posixpath
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from omega_lib.synchro.constants import TOKEN_RELATIVE_PATH, TOOL_LAUNCHERS
from omega_lib.synchro.models import CapabilityState, InstanceSheet, ReadStatus
from omega_lib.synchro.policies import normalize_network
from omega_lib.synchro.rights import expected_right, mode_matches

from omega_connect.domain.detection import DetectedInstallation, DetectionReport
from omega_connect.domain.fail2ban import (
    BRIDGE_ACTION_PREFIX,
    MAGNET_ALERTS_JAIL,
    MAGNET_FILE_KEYS,
    RIPOSTE_FILE_KEY,
    BridgeAction,
    Fail2banSnapshot,
    FileFacts,
    JailConfig,
    Presence,
    parse_bridge_action,
    parse_jail_file,
    riposte_service,
)
from omega_connect.domain.versions import outdated, outdated_roots

SERV_TOOL = "omega-serv"
JAIL_TOOL = "omega-jail"
SERV_LOG_KEYS = ("waf-log", "active-defense-log", "access-log", RIPOSTE_FILE_KEY)
"""Journaux d'omega-serv qu'un jail d'omega-jail sait lire (hors magnet)."""
MAGNET_LOG_KEYS = tuple(sorted(MAGNET_FILE_KEYS))
LOG_ONLY = "log-only"


class LinkKind(str, Enum):
    SERV_LOGS = "serv-logs-to-jails"
    MAGNET_LOGS = "magnet-logs-to-jails"
    BRIDGE = "bridge-to-blocklist"
    PROTECTED_LIST = "protected-list"
    BLOCKLIST = "serv-blocklist"
    FAIL2BAN_FILES = "fail2ban-files"
    TOKENS = "install-tokens"
    ZONE = "neutral-zone"


INSTANCE_LINKS = (LinkKind.SERV_LOGS, LinkKind.MAGNET_LOGS, LinkKind.BRIDGE, LinkKind.PROTECTED_LIST,
                  LinkKind.BLOCKLIST)


class LinkState(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    ABSENT = "absent"
    BROKEN = "broken"
    UNVERIFIABLE = "unverifiable"


class CheckStatus(str, Enum):
    OK = "ok"
    INFO = "info"
    """Explique un lien absent ; ne compte pas dans l'etat."""
    WARNING = "warning"
    FAILURE = "failure"
    UNVERIFIABLE = "unverifiable"


class CheckCode(str, Enum):
    FAIL2BAN_NOT_INSTALLED = "fail2ban-not-installed"
    FAIL2BAN_UNREADABLE = "fail2ban-unreadable"
    JAIL_TOOL_MISSING = "jail-tool-missing"
    NO_JAIL = "no-jail"
    NO_JAIL_FILES = "no-jail-files"
    FUNCTION_OFF = "function-off"
    SHEET_MISSING = "sheet-missing"
    JAIL_DISABLED = "jail-disabled"
    JAIL_FILTER_MISSING = "jail-filter-missing"
    JAIL_LOG_OK = "jail-log-ok"
    JAIL_LOG_MISSING = "jail-log-missing"
    JAIL_LOG_UNKNOWN = "jail-log-unknown"
    JAIL_LOG_ROOT_OWNED = "jail-log-root-owned"
    JAIL_LOG_RIGHTS = "jail-log-rights"
    JAIL_PATH_DIFFERS = "jail-path-differs"
    JAIL_SOURCE_OFF = "jail-source-off"
    JAIL_NO_INSTANCE = "jail-no-instance"
    FUNCTION_NOT_COVERED = "function-not-covered"
    MAGNET_LOG_ONLY = "magnet-log-only"
    BRIDGE_ACTION_OK = "bridge-action-ok"
    BRIDGE_ACTION_MISSING = "bridge-action-missing"
    BRIDGE_NO_SERVCLI = "bridge-no-servcli"
    BRIDGE_UNKNOWN_ACTION = "bridge-unknown-action"
    BRIDGE_WRONG_TARGET = "bridge-wrong-target"
    BRIDGE_TARGET_MISSING = "bridge-target-missing"
    BRIDGE_TARGET_NOT_DETECTED = "bridge-target-not-detected"
    JAIL_WITHOUT_BRIDGE = "jail-without-bridge"
    BRIDGE_SCRIPT_OK = "bridge-script-ok"
    BRIDGE_SCRIPT_MISSING = "bridge-script-missing"
    BRIDGE_SCRIPT_UNKNOWN = "bridge-script-unknown"
    BRIDGE_SCRIPT_UNSAFE = "bridge-script-unsafe"
    BRIDGE_SCRIPT_RIGHTS = "bridge-script-rights"
    PROTECTED_LIST_UNKNOWN = "protected-list-unknown"
    PROTECTED_JAIL_OK = "protected-jail-ok"
    PROTECTED_JAIL_DIFFERS = "protected-jail-differs"
    PROTECTED_BRIDGE_OK = "protected-bridge-ok"
    PROTECTED_BRIDGE_DIFFERS = "protected-bridge-differs"
    BLOCKLIST_OFF = "blocklist-off"
    BLOCKLIST_NOT_CREATED = "blocklist-not-created"
    BLOCKLIST_OK = "blocklist-ok"
    BLOCKLIST_UNKNOWN = "blocklist-unknown"
    BLOCKLIST_ROOT_OWNED = "blocklist-root-owned"
    BLOCKLIST_GROUP = "blocklist-group"
    BLOCKLIST_MODE = "blocklist-mode"
    BLOCKLIST_OWNER = "blocklist-owner"
    FILES_OK = "files-ok"
    FILE_UNREADABLE = "file-unreadable"
    FILE_UNSAFE = "file-unsafe"
    FILE_RIGHTS = "file-rights"
    JAIL_FILE_DAMAGED = "jail-file-damaged"
    BRIDGE_ACTION_DAMAGED = "bridge-action-damaged"
    TOKEN_OK = "token-ok"
    TOKEN_MISSING = "token-missing"
    TOKEN_TOOL_TOO_OLD = "token-tool-too-old"
    TOKEN_INSTALL_INCOMPLETE = "token-install-incomplete"
    TOKEN_UNREADABLE = "token-unreadable"
    TOKEN_DAMAGED = "token-damaged"
    TOKEN_NEWER = "token-newer"
    TOKEN_RIGHTS = "token-rights"
    TOKEN_DUPLICATE = "token-duplicate"
    ZONE_ABSENT = "zone-absent"
    ZONE_UNSAFE = "zone-unsafe"
    ZONE_FOREIGN = "zone-foreign"
    ZONE_UNREADABLE = "zone-unreadable"
    ZONE_REGISTRY_DAMAGED = "zone-registry-damaged"
    ZONE_FROZEN = "zone-frozen"
    ZONE_DIRECTORY_OK = "zone-directory-ok"
    ZONE_DIRECTORY_MISSING = "zone-directory-missing"
    ZONE_DIRECTORY_RIGHTS = "zone-directory-rights"
    ZONE_GROUP_MISSING = "zone-group-missing"
    ZONE_MEMBER_OK = "zone-member-ok"
    ZONE_MEMBER_MISSING = "zone-member-missing"
    ZONE_RELOGIN = "zone-relogin"
    ZONE_AWAITING_RELOGIN = "zone-awaiting-relogin"
    ZONE_NOT_MEMBER_UNREADABLE = "zone-not-member-unreadable"
    ZONE_COPY_OK = "zone-copy-ok"
    ZONE_COPY_MISSING = "zone-copy-missing"
    ZONE_COPY_STALE = "zone-copy-stale"
    ZONE_COPY_RIGHTS = "zone-copy-rights"
    ZONE_NOT_LINKED = "zone-not-linked"
    ZONE_TOOL_GONE = "zone-tool-gone"
    ZONE_SERVICE_GROUP_OK = "zone-service-group-ok"
    ZONE_SERVICE_GROUP_MISSING = "zone-service-group-missing"


class RepairKind(str, Enum):
    """Qui sait corriger un ecart (spec §3.4, lot E) : toujours la commande de l'outil proprietaire, jamais
    omega-connect a sa place ; sauf la zone, qu'omega-connect a creee lui-meme (registre)."""

    TOKEN = "token"
    """`<outil> synchro jeton`, sous le compte proprietaire, sans root."""
    SERV_PERMISSIONS = "serv-permissions"
    """`omega-serv.sh service permissions`, en root (fichiers de var/ rendus et partages avec le service)."""
    JAIL_APPLY = "jail-apply"
    """`omega-jail.sh --apply --update`, en root (contenu ET droits de tout ce qu'omega-jail pose)."""
    ZONE = "zone"
    """`omega-connect etablir` : seulement ce que le registre dit avoir cree."""


@dataclass(frozen=True)
class Repair:
    kind: RepairKind
    root: str = ""
    """Racine de l'outil proprietaire (lanceur `<racine>/<lanceur>`) ; vide pour la zone."""
    tool: str = ""
    service: str = ""
    """Service omega-serv concerne (`service permissions --service-name`)."""


@dataclass(frozen=True)
class Check:
    code: CheckCode
    status: CheckStatus
    subject: str = ""
    """Chemin, jail ou fonction concerne (jamais traduit)."""
    detail: str = ""
    """Precision technique (jamais traduite) : droits constates, chemin attendu, reseaux en trop (+) ou en moins (-)."""
    fix: str = ""
    """Commande qui corrigerait l'ecart ; affichee, jamais lancee par `verifier`."""
    fix_account: str = ""
    """Compte sous lequel lancer `fix` (vide : la commande porte deja `sudo` si besoin)."""
    repair: Repair | None = None
    """Ce que `reparer` lance pour corriger l'ecart ; None : correction a faire a la main (ou decision)."""


def link_state(checks: Iterable[Check]) -> LinkState:
    statuses = {check.status for check in checks}
    if CheckStatus.FAILURE in statuses:
        return LinkState.BROKEN
    if CheckStatus.WARNING in statuses:
        return LinkState.DEGRADED
    if CheckStatus.UNVERIFIABLE in statuses:
        return LinkState.UNVERIFIABLE
    if CheckStatus.OK in statuses:
        return LinkState.ACTIVE
    return LinkState.ABSENT


class Provenance(str, Enum):
    """D'ou vient une liaison (demande de l'auteur, 2026-11-10) : cette machine, ou le reseau (machine distante
    scannee par SSH au lot R2 ; liaison entre deux machines au lot R4)."""

    LOCAL = "local"
    NETWORK = "network"


@dataclass(frozen=True)
class Link:
    kind: LinkKind
    instance: str
    """Nom de l'instance omega-serv (son service) ; vide pour un controle de la machine entiere."""
    root: str
    checks: tuple[Check, ...]
    machine: str = ""
    """Machine ou la liaison a ete vue (vide : cette machine)."""
    peer: str = ""
    """Autre machine pour une liaison entre deux machines (lot R4) ; vide sinon."""

    @property
    def state(self) -> LinkState:
        return link_state(self.checks)

    @property
    def provenance(self) -> Provenance:
        return Provenance.NETWORK if self.machine or self.peer else Provenance.LOCAL


@dataclass(frozen=True)
class VerificationReport:
    detection: DetectionReport
    links: tuple[Link, ...]

    @property
    def has_problems(self) -> bool:
        return any(link.state in (LinkState.BROKEN, LinkState.DEGRADED) for link in self.links)


@dataclass(frozen=True)
class Fail2banConfig:
    """Lecture des fichiers d'omega-jail dans fail2ban."""

    snapshot: Fail2banSnapshot
    jails: tuple[JailConfig, ...]
    actions: Mapping[str, BridgeAction]
    damaged: tuple[Check, ...]
    """Fichiers abimes ou illisibles (lien « fichiers d'omega-jail dans fail2ban »)."""

    @property
    def filter_names(self) -> frozenset[str]:
        return frozenset(posixpath.basename(item.path) for item in self.snapshot.filter_files)


def read_fail2ban(snapshot: Fail2banSnapshot) -> Fail2banConfig:
    jails: list[JailConfig] = []
    actions: dict[str, BridgeAction] = {}
    damaged: list[Check] = []
    for item in snapshot.jail_files:
        if item.text is None:
            damaged.append(Check(CheckCode.FILE_UNREADABLE, CheckStatus.UNVERIFIABLE, item.facts.path))
            continue
        found, error = parse_jail_file(item.facts.path, item.text)
        if error:
            damaged.append(Check(CheckCode.JAIL_FILE_DAMAGED, CheckStatus.FAILURE, item.facts.path, error))
        jails.extend(found)
    for item in snapshot.action_files:
        if item.text is None:
            damaged.append(Check(CheckCode.FILE_UNREADABLE, CheckStatus.UNVERIFIABLE, item.facts.path))
            continue
        action = parse_bridge_action(item.facts.path, item.text)
        if action is None or not action.script:
            damaged.append(Check(CheckCode.BRIDGE_ACTION_DAMAGED, CheckStatus.FAILURE, item.facts.path))
            continue
        actions[action.name] = action
    return Fail2banConfig(snapshot, tuple(jails), actions, tuple(damaged))


@dataclass(frozen=True)
class ServInstance:
    root: str
    name: str
    owner: str
    names: frozenset[str]
    """Noms de service connus (fiche et detection) : rattache les jails RIPOSTE `<service>-riposte-*`."""
    sheet: InstanceSheet | None

    @property
    def service(self) -> str:
        """Nom du service (sans `.service`) : celui de la fiche, sinon le nom de l'instance."""
        info = self.sheet.service if self.sheet is not None else None
        if info is not None and info.unit:
            return info.unit.removesuffix(".service")
        return self.name

    @property
    def service_group(self) -> str:
        """Groupe du service dedie, s'il tourne sous un autre compte que le proprietaire du dossier."""
        service = self.sheet.service if self.sheet is not None else None
        if service is None or not service.group or service.user in ("", self.owner):
            return ""
        return service.group


def serv_instances(detection: DetectionReport) -> tuple[ServInstance, ...]:
    instances = []
    for item in detection.installations:
        if item.tool != SERV_TOOL:
            continue
        sheet = item.sheet.sheet if item.sheet is not None else None
        names = set(item.service_names)
        if sheet is not None and sheet.instance:
            names.add(sheet.instance)
        name = sheet.instance if sheet is not None and sheet.instance else (
            item.service_names[0] if item.service_names else posixpath.basename(item.root))
        instances.append(ServInstance(item.root, name, item.owner, frozenset(names), sheet))
    return tuple(instances)


def _under(path: str, root: str) -> bool:
    path, root = posixpath.normpath(path), posixpath.normpath(root)
    return path == root or path.startswith(root.rstrip("/") + "/")


def _same(first: str, second: str) -> bool:
    return bool(first) and posixpath.normpath(first) == posixpath.normpath(second)


def jail_instance(jail: JailConfig, instances: Sequence[ServInstance]) -> ServInstance | None:
    """Instance a laquelle un jail appartient : nom de service (RIPOSTE), puis journal de sa fiche, puis dossier."""
    service = riposte_service(jail.name)
    if service is not None:
        for instance in instances:
            if service in instance.names:
                return instance
    for instance in instances:
        if instance.sheet is not None and any(
                _same(path, shared.path) for path in jail.logpaths for shared in instance.sheet.files.values()):
            return instance
    for instance in instances:
        if any(_under(path, instance.root) for path in jail.logpaths):
            return instance
    return None


def paths_to_probe(detection: DetectionReport, fail2ban: Fail2banConfig) -> list[str]:
    """Fichiers dont `verifier` lit les droits (stat seulement, jamais le contenu)."""
    paths: set[str] = set()
    for jail in fail2ban.jails:
        paths.update(jail.logpaths)
    for action in fail2ban.actions.values():
        paths.add(action.script)
        if action.servcli:
            paths.add(action.servcli)
    for instance in serv_instances(detection):
        if instance.sheet is not None and "blocklist" in instance.sheet.files:
            paths.add(instance.sheet.files["blocklist"].path)
    for item in detection.installations:
        if item.token_status is ReadStatus.OK:
            paths.add(_token_path(item.root))
    return sorted(path for path in paths if path)


def _token_path(root: str) -> str:
    return posixpath.join(root, TOKEN_RELATIVE_PATH)


@dataclass(frozen=True)
class _Context:
    fail2ban: Fail2banConfig
    facts: Mapping[str, FileFacts]
    instances: tuple[ServInstance, ...]
    jail_fix: str
    jail_installed: bool
    jail_repair: Repair | None = None

    def file(self, path: str) -> FileFacts:
        return self.facts.get(path, FileFacts(path, Presence.UNKNOWN, detail="not examined"))

    def fail2ban_blocked(self) -> tuple[Check, ...]:
        snapshot = self.fail2ban.snapshot
        if not snapshot.installed:
            return (Check(CheckCode.FAIL2BAN_NOT_INSTALLED, CheckStatus.INFO),)
        if not snapshot.readable:
            return (Check(CheckCode.FAIL2BAN_UNREADABLE, CheckStatus.UNVERIFIABLE, detail=snapshot.detail),)
        return ()

    def no_jail(self) -> Check:
        if not self.jail_installed:
            return Check(CheckCode.JAIL_TOOL_MISSING, CheckStatus.INFO)
        return Check(CheckCode.NO_JAIL, CheckStatus.INFO, fix=self.jail_fix)

    def jail(self, code: CheckCode, status: CheckStatus, subject: str = "", detail: str = "") -> Check:
        """Ecart corrige par omega-jail (`--apply --update`)."""
        return Check(code, status, subject, detail, fix=self.jail_fix, repair=self.jail_repair)


JAIL_APPLY_ARGUMENTS = ("--apply", "--update")
SERV_PERMISSIONS_ARGUMENTS = ("service", "permissions", "--service-name")
TOKEN_ARGUMENTS = ("synchro", "jeton")


def jail_fix_command(detection: DetectionReport) -> tuple[str, bool]:
    """Commande d'omega-jail qui recree ou met a jour ses jails, et si omega-jail est installe."""
    jails = [item for item in detection.installations if item.tool == JAIL_TOOL]
    roots = [item.root for item in jails]
    launcher = TOOL_LAUNCHERS[JAIL_TOOL]
    if len(jails) == 1 and outdated(jails[0]) is not None:
        return "", True  # trop ancien : `--update` inconnu, mise a jour d'abord (lot R3)
    if len(roots) == 1:
        return f"{roots[0]}/{launcher} {' '.join(JAIL_APPLY_ARGUMENTS)}", True
    return f"{launcher} {' '.join(JAIL_APPLY_ARGUMENTS)}", bool(roots)


def jail_repair(detection: DetectionReport) -> Repair | None:
    """Une seule installation d'omega-jail : `reparer` sait laquelle lancer ; plusieurs : a choisir a la main."""
    roots = [item.root for item in detection.installations if item.tool == JAIL_TOOL]
    return Repair(RepairKind.JAIL_APPLY, roots[0], JAIL_TOOL) if len(roots) == 1 else None


def serv_permissions_command(instance: ServInstance) -> str:
    return f"{instance.root}/{TOOL_LAUNCHERS[SERV_TOOL]} {' '.join(SERV_PERMISSIONS_ARGUMENTS)} {instance.service}"


def _serv_permissions(instance: ServInstance | None, path: str) -> tuple[str, Repair | None]:
    """Fichier de var/ d'une instance : corrige par `omega-serv service permissions` ; ailleurs : None."""
    if instance is None or not _under(path, posixpath.join(instance.root, "var")):
        return "", None
    return serv_permissions_command(instance), Repair(RepairKind.SERV_PERMISSIONS, instance.root, SERV_TOOL,
                                                      instance.service)


def _log_rights(path: str, facts: FileFacts, instance: ServInstance | None) -> Check:
    owner = instance.owner if instance is not None else ""
    group = instance.service_group if instance is not None else ""
    found = f"{facts.owner}:{facts.group} {facts.mode & 0o7777:04o}"
    command, repair = _serv_permissions(instance, path)
    if facts.owner == "root":
        target = f"{owner}:{group or owner}" if owner else "<owner>:<group>"
        return Check(CheckCode.JAIL_LOG_ROOT_OWNED, CheckStatus.FAILURE, path, found,
                     fix=command or f"sudo chown {target} {path} && sudo chmod 664 {path}", repair=repair)
    if group and (facts.group != group or not mode_matches(facts.mode, expected_right("serv-jail-logs"))):
        return Check(CheckCode.JAIL_LOG_RIGHTS, CheckStatus.WARNING, path, f"{found}, expected group {group} rw",
                     fix=command or f"sudo chgrp {group} {path} && sudo chmod g+rw {path}", repair=repair)
    return Check(CheckCode.JAIL_LOG_OK, CheckStatus.OK, path, found)


def _jail_checks(jail: JailConfig, instance: ServInstance | None, context: _Context) -> list[Check]:
    if not jail.enabled:
        return [Check(CheckCode.JAIL_DISABLED, CheckStatus.INFO, jail.name)]
    checks = []
    if f"{jail.filter}.conf" not in context.fail2ban.filter_names:
        checks.append(context.jail(CheckCode.JAIL_FILTER_MISSING, CheckStatus.FAILURE, jail.name, jail.filter))
    for path in jail.logpaths:
        facts = context.file(path)
        if facts.presence is Presence.MISSING:
            checks.append(context.jail(CheckCode.JAIL_LOG_MISSING, CheckStatus.FAILURE, path, jail.name))
        elif facts.presence is Presence.UNKNOWN:
            checks.append(Check(CheckCode.JAIL_LOG_UNKNOWN, CheckStatus.UNVERIFIABLE, path, facts.detail))
        else:
            checks.append(_log_rights(path, facts, instance))
    sheet = instance.sheet if instance is not None else None
    key = jail.file_key
    if sheet is not None and key is not None:
        shared = sheet.files.get(key)
        if shared is None:
            checks.append(Check(CheckCode.JAIL_SOURCE_OFF, CheckStatus.WARNING, jail.name, key))
        elif not any(_same(path, shared.path) for path in jail.logpaths):
            checks.append(context.jail(CheckCode.JAIL_PATH_DIFFERS, CheckStatus.FAILURE, jail.name, shared.path))
    return checks


def _log_link(kind: LinkKind, instance: ServInstance, jails: Sequence[JailConfig], context: _Context) -> Link:
    blocked = context.fail2ban_blocked()
    if blocked:
        return Link(kind, instance.name, instance.root, blocked)
    keys = MAGNET_LOG_KEYS if kind is LinkKind.MAGNET_LOGS else SERV_LOG_KEYS
    relevant = [jail for jail in jails if jail.file_key in keys]
    sheet = instance.sheet
    checks: list[Check] = []
    if not relevant:
        if kind is LinkKind.MAGNET_LOGS and sheet is not None and \
                sheet.capabilities.get("magnet") is not CapabilityState.ACTIVE:
            off = Check(CheckCode.FUNCTION_OFF, CheckStatus.INFO, "magnet")
            return Link(kind, instance.name, instance.root, (off,))
        return Link(kind, instance.name, instance.root, (context.no_jail(),))
    for jail in relevant:
        checks.extend(_jail_checks(jail, instance, context))
    if sheet is None:
        checks.append(Check(CheckCode.SHEET_MISSING, CheckStatus.UNVERIFIABLE, instance.root))
    else:
        covered = {jail.file_key for jail in relevant if jail.enabled}
        for key in keys:
            if key in sheet.files and key not in covered:
                checks.append(context.jail(CheckCode.FUNCTION_NOT_COVERED, CheckStatus.WARNING, key,
                                           sheet.files[key].path))
        if kind is LinkKind.MAGNET_LOGS and sheet.extra.get("waf_mode") == LOG_ONLY and any(
                jail.name == MAGNET_ALERTS_JAIL and jail.enabled for jail in relevant):
            checks.append(Check(CheckCode.MAGNET_LOG_ONLY, CheckStatus.WARNING, MAGNET_ALERTS_JAIL))
    return Link(kind, instance.name, instance.root, tuple(checks))


def _script_checks(scripts: Iterable[str], context: _Context) -> list[Check]:
    right = expected_right("jail-bridge")
    checks = []
    for script in sorted(set(scripts)):
        facts = context.file(script)
        found = f"{facts.owner}:{facts.group} {facts.mode & 0o7777:04o}"
        if facts.presence is Presence.MISSING:
            checks.append(context.jail(CheckCode.BRIDGE_SCRIPT_MISSING, CheckStatus.FAILURE, script))
        elif facts.presence is Presence.UNKNOWN:
            checks.append(Check(CheckCode.BRIDGE_SCRIPT_UNKNOWN, CheckStatus.UNVERIFIABLE, script, facts.detail))
        elif facts.owner != right.owner or facts.writable_by_group_or_others:
            checks.append(context.jail(CheckCode.BRIDGE_SCRIPT_UNSAFE, CheckStatus.FAILURE, script, found))
        elif not mode_matches(facts.mode, right):
            checks.append(context.jail(CheckCode.BRIDGE_SCRIPT_RIGHTS, CheckStatus.WARNING, script, found))
        else:
            checks.append(Check(CheckCode.BRIDGE_SCRIPT_OK, CheckStatus.OK, script, found))
    return checks


def _bridge_link(instance: ServInstance, jails: Sequence[JailConfig], context: _Context) -> Link:
    blocked = context.fail2ban_blocked()
    if blocked:
        return Link(LinkKind.BRIDGE, instance.name, instance.root, blocked)
    actions = context.fail2ban.actions
    own = [action for action in actions.values() if _same(action.target_root, instance.root)]
    active = [jail for jail in jails if jail.enabled]
    if not active and not own:
        return Link(LinkKind.BRIDGE, instance.name, instance.root, (context.no_jail(),))
    checks = [Check(CheckCode.BRIDGE_ACTION_OK, CheckStatus.OK, action.name, action.source) for action in own]
    if active and not own:
        checks.append(context.jail(CheckCode.BRIDGE_ACTION_MISSING, CheckStatus.WARNING, instance.root))
    scripts = [action.script for action in own]
    for jail in active:
        names = [name for name in jail.actions if name.startswith(BRIDGE_ACTION_PREFIX)]
        if not names:
            checks.append(context.jail(CheckCode.JAIL_WITHOUT_BRIDGE, CheckStatus.WARNING, jail.name))
        for name in names:
            action = actions.get(name)
            if action is None:
                checks.append(context.jail(CheckCode.BRIDGE_UNKNOWN_ACTION, CheckStatus.FAILURE, jail.name, name))
            elif not action.servcli:
                checks.append(context.jail(CheckCode.BRIDGE_NO_SERVCLI, CheckStatus.FAILURE, name, action.source))
            elif not _same(action.target_root, instance.root):
                checks.append(context.jail(CheckCode.BRIDGE_WRONG_TARGET, CheckStatus.FAILURE, jail.name,
                                           action.target_root))
            else:
                scripts.append(action.script)
    checks.extend(_script_checks(scripts, context))
    return Link(LinkKind.BRIDGE, instance.name, instance.root, tuple(checks))


def _difference(found: Iterable[str], expected: set[str]) -> str:
    found_set = set(found)
    return " ".join([f"+{item}" for item in sorted(found_set - expected)]
                    + [f"-{item}" for item in sorted(expected - found_set)])


def _protected_link(instance: ServInstance, jails: Sequence[JailConfig], context: _Context) -> Link:
    blocked = context.fail2ban_blocked()
    if blocked:
        return Link(LinkKind.PROTECTED_LIST, instance.name, instance.root, blocked)
    active = [jail for jail in jails if jail.enabled]
    own = [action for action in context.fail2ban.actions.values() if _same(action.target_root, instance.root)]
    if not active and not own:
        return Link(LinkKind.PROTECTED_LIST, instance.name, instance.root, (context.no_jail(),))
    raw = instance.sheet.extra.get("never_auto_block") if instance.sheet is not None else None
    if not isinstance(raw, list):
        detail = "sheet" if instance.sheet is None else "omega-serv < 2.6.1"
        return Link(LinkKind.PROTECTED_LIST, instance.name, instance.root,
                    (Check(CheckCode.PROTECTED_LIST_UNKNOWN, CheckStatus.UNVERIFIABLE, instance.root, detail),))
    expected = {normalize_network(item) or str(item) for item in raw}
    checks = []
    for jail in active:
        difference = _difference(jail.ignoreip, expected)
        checks.append(context.jail(CheckCode.PROTECTED_JAIL_DIFFERS, CheckStatus.WARNING, jail.name, difference)
                      if difference else
                      Check(CheckCode.PROTECTED_JAIL_OK, CheckStatus.OK, jail.name))
    for action in own:
        difference = _difference(action.exempt, expected)
        checks.append(context.jail(CheckCode.PROTECTED_BRIDGE_DIFFERS, CheckStatus.WARNING, action.name, difference)
                      if difference else
                      Check(CheckCode.PROTECTED_BRIDGE_OK, CheckStatus.OK, action.name))
    return Link(LinkKind.PROTECTED_LIST, instance.name, instance.root, tuple(checks))


def _blocklist_link(instance: ServInstance, context: _Context) -> Link:
    def link(*checks: Check) -> Link:
        return Link(LinkKind.BLOCKLIST, instance.name, instance.root, checks)

    if instance.sheet is None:
        return link(Check(CheckCode.SHEET_MISSING, CheckStatus.UNVERIFIABLE, instance.root))
    shared = instance.sheet.files.get("blocklist")
    if shared is None:
        return link(Check(CheckCode.BLOCKLIST_OFF, CheckStatus.INFO))
    path = shared.path
    facts = context.file(path)
    if facts.presence is Presence.MISSING:
        return link(Check(CheckCode.BLOCKLIST_NOT_CREATED, CheckStatus.OK, path))
    if facts.presence is Presence.UNKNOWN:
        return link(Check(CheckCode.BLOCKLIST_UNKNOWN, CheckStatus.UNVERIFIABLE, path, facts.detail))
    found = f"{facts.owner}:{facts.group} {facts.mode & 0o7777:04o}"
    group = instance.service_group
    owner = instance.owner
    command, repair = _serv_permissions(instance, path)
    if facts.owner == "root":
        return link(Check(CheckCode.BLOCKLIST_ROOT_OWNED, CheckStatus.FAILURE, path, found,
                          fix=command or f"sudo chown {owner}:{group or owner} {path} && sudo chmod 660 {path}",
                          repair=repair))
    checks = []
    if group and facts.group != group:
        checks.append(Check(CheckCode.BLOCKLIST_GROUP, CheckStatus.FAILURE, path, f"{found}, expected group {group}",
                            fix=command or f"sudo chgrp {group} {path}", repair=repair))
    if group and not mode_matches(facts.mode, expected_right("serv-blocklist")):
        checks.append(Check(CheckCode.BLOCKLIST_MODE, CheckStatus.FAILURE, path, found,
                            fix=command or f"chmod ug+rw {path}", fix_account="" if command else owner,
                            repair=repair))
    if owner and facts.owner != owner:
        checks.append(Check(CheckCode.BLOCKLIST_OWNER, CheckStatus.WARNING, path, f"{found}, expected owner {owner}",
                            fix=f"sudo chown {owner} {path}"))
    return link(*(checks or [Check(CheckCode.BLOCKLIST_OK, CheckStatus.OK, path, found)]))


def _orphan_links(orphans: Sequence[JailConfig], instances: Sequence[ServInstance], context: _Context) -> list[Link]:
    links = []
    if orphans:
        checks: list[Check] = []
        for jail in orphans:
            checks.append(Check(CheckCode.JAIL_NO_INSTANCE, CheckStatus.WARNING, jail.name, " ".join(jail.logpaths)))
            checks.extend(_jail_checks(jail, None, context))
        links.append(Link(LinkKind.SERV_LOGS, "", "", tuple(checks)))
    stray = []
    for action in context.fail2ban.actions.values():
        if not action.servcli:
            stray.append(context.jail(CheckCode.BRIDGE_NO_SERVCLI, CheckStatus.FAILURE, action.name, action.source))
        elif not any(_same(action.target_root, instance.root) for instance in instances):
            missing = context.file(action.servcli).presence is Presence.MISSING
            if missing:
                stray.append(context.jail(CheckCode.BRIDGE_TARGET_MISSING, CheckStatus.FAILURE, action.name,
                                          action.target_root))
            else:
                stray.append(Check(CheckCode.BRIDGE_TARGET_NOT_DETECTED, CheckStatus.WARNING, action.name,
                                   action.target_root))
    if stray:
        links.append(Link(LinkKind.BRIDGE, "", "", tuple(stray)))
    return links


def _fail2ban_files_link(context: _Context) -> Link:
    blocked = context.fail2ban_blocked()
    if blocked:
        return Link(LinkKind.FAIL2BAN_FILES, "", "", blocked)
    snapshot = context.fail2ban.snapshot
    files = [item.facts for item in snapshot.jail_files] + list(snapshot.filter_files) + [
        item.facts for item in snapshot.action_files]
    if not files:
        if not context.jail_installed:
            return Link(LinkKind.FAIL2BAN_FILES, "", "", (Check(CheckCode.JAIL_TOOL_MISSING, CheckStatus.INFO),))
        return Link(LinkKind.FAIL2BAN_FILES, "", "",
                    (Check(CheckCode.NO_JAIL_FILES, CheckStatus.INFO, fix=context.jail_fix),))
    right = expected_right("fail2ban-omega-files")
    checks = list(context.fail2ban.damaged)
    conforming = 0
    for facts in files:
        found = f"{facts.owner}:{facts.group} {facts.mode & 0o7777:04o}"
        if facts.presence is not Presence.PRESENT:
            checks.append(Check(CheckCode.FILE_UNREADABLE, CheckStatus.UNVERIFIABLE, facts.path, facts.detail))
        elif facts.owner != right.owner or facts.writable_by_group_or_others:
            checks.append(context.jail(CheckCode.FILE_UNSAFE, CheckStatus.FAILURE, facts.path, found))
        elif not mode_matches(facts.mode, right):
            checks.append(context.jail(CheckCode.FILE_RIGHTS, CheckStatus.WARNING, facts.path, found))
        else:
            conforming += 1
    if conforming:
        checks.insert(0, Check(CheckCode.FILES_OK, CheckStatus.OK, str(conforming)))
    return Link(LinkKind.FAIL2BAN_FILES, "", "", tuple(checks))


TOKEN_GROUP_WRITE = 0o020


def token_mode_ok(mode: int) -> bool:
    """0644, ou 0664 : lisible par tous, jamais modifiable par les autres comptes. Le groupe de l'outil peut y
    ecrire : omega-serv partage tout son var/ avec le groupe de son service (`service permissions`, g+rw) ; la
    regle exacte 0644 faisait de chaque partage un ecart que `reparer` ne pouvait pas tenir (constate le
    2026-11-11 sur craftdark : « toujours degrade apres Reparer »)."""
    return (mode & 0o7777 & ~TOKEN_GROUP_WRITE) == expected_right("install-token").mode


def _token_check(item: DetectedInstallation, context: _Context) -> Check | None:
    launcher = TOOL_LAUNCHERS.get(item.tool)
    command = f"{item.root}/{launcher} {' '.join(TOKEN_ARGUMENTS)}" if launcher else ""
    repair = Repair(RepairKind.TOKEN, item.root, item.tool) if launcher else None
    path = _token_path(item.root)
    status = item.token_status
    if status is ReadStatus.OK:
        facts = context.file(path)
        found = f"{facts.owner}:{facts.group} {facts.mode & 0o7777:04o}"
        wrong_owner = bool(item.owner) and facts.owner != item.owner
        if facts.presence is Presence.PRESENT and (wrong_owner or not token_mode_ok(facts.mode)):
            return Check(CheckCode.TOKEN_RIGHTS, CheckStatus.WARNING, path, found, fix=command, fix_account=item.owner,
                         repair=repair)
        return Check(CheckCode.TOKEN_OK, CheckStatus.OK, item.root, item.installation_id[:8])
    if not item.tool:
        return None
    if status is ReadStatus.ABSENT:
        old = outdated(item)
        if old is not None:
            code = CheckCode.TOKEN_INSTALL_INCOMPLETE if old.incomplete else CheckCode.TOKEN_TOOL_TOO_OLD
            return Check(code, CheckStatus.INFO, item.root, item.tool)
        return Check(CheckCode.TOKEN_MISSING, CheckStatus.WARNING, item.root, item.tool, fix=command,
                     fix_account=item.owner, repair=repair)
    if status is ReadStatus.UNREADABLE:
        return Check(CheckCode.TOKEN_UNREADABLE, CheckStatus.UNVERIFIABLE, path, item.token_detail)
    if status is ReadStatus.INCOMPATIBLE:
        return Check(CheckCode.TOKEN_NEWER, CheckStatus.WARNING, path, item.token_detail)
    return Check(CheckCode.TOKEN_DAMAGED, CheckStatus.WARNING, path, item.token_detail, fix=command,
                 fix_account=item.owner, repair=repair)


def _tokens_link(detection: DetectionReport, context: _Context) -> Link:
    checks = [check for item in detection.installations if (check := _token_check(item, context)) is not None]
    checks.extend(Check(CheckCode.TOKEN_DUPLICATE, CheckStatus.WARNING, duplicate.installation_id[:8],
                        " ".join(duplicate.roots)) for duplicate in detection.duplicates)
    return Link(LinkKind.TOKENS, "", "", tuple(checks))


def evaluate_links(detection: DetectionReport, fail2ban: Fail2banConfig,
                   facts: Mapping[str, FileFacts]) -> tuple[Link, ...]:
    instances = serv_instances(detection)
    jail_fix, jail_installed = jail_fix_command(detection)
    context = _Context(fail2ban, facts, instances, jail_fix, jail_installed, jail_repair(detection))
    by_instance: dict[str, list[JailConfig]] = {instance.root: [] for instance in instances}
    orphans: list[JailConfig] = []
    for jail in fail2ban.jails:
        owner = jail_instance(jail, instances)
        if owner is None:
            orphans.append(jail)
        else:
            by_instance[owner.root].append(jail)
    links: list[Link] = []
    for instance in sorted(instances, key=lambda item: item.root):
        jails = by_instance[instance.root]
        links.append(_log_link(LinkKind.SERV_LOGS, instance, jails, context))
        links.append(_log_link(LinkKind.MAGNET_LOGS, instance, jails, context))
        links.append(_bridge_link(instance, jails, context))
        links.append(_protected_link(instance, jails, context))
        links.append(_blocklist_link(instance, context))
    if not context.fail2ban_blocked():
        links.extend(_orphan_links(orphans, instances, context))
    links.append(_fail2ban_files_link(context))
    links.append(_tokens_link(detection, context))
    return without_outdated_repairs(links, outdated_roots(detection.installations))


def without_outdated_repairs(links: Iterable[Link], old: Mapping[str, object]) -> tuple[Link, ...]:
    """Jamais une commande que la version installee ne connait pas (lot R3 ; constate le 2026-11-10 :
    `omega-jail --apply --update` propose a omega-jail 1.1.0) : la correction d'un outil trop ancien passe par sa
    mise a jour, signalee au registre (« Ancienne version ») et faite par la Synchronisation."""
    if not old:
        return tuple(links)
    cleaned = []
    for link in links:
        checks = tuple(dataclasses.replace(check, fix="", fix_account="", repair=None)
                       if check.repair is not None and check.repair.root in old else check
                       for check in link.checks)
        cleaned.append(dataclasses.replace(link, checks=checks))
    return tuple(cleaned)
