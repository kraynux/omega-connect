# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lien « zone neutre » de `verifier` (spec etape 3, §3.2, derniere ligne) : dossiers, groupe, membre, registre
et copies, compares a la table des droits d'omega-lib. Lecture seule, sans root : une zone que la session ne
peut pas lire (ajout au groupe pas encore pris en compte) est « non verifiable », jamais « cassee »."""
from __future__ import annotations

from omega_lib.synchro.codec import token_to_dict
from omega_lib.synchro.constants import ZONE_GROUP
from omega_lib.synchro.models import ReadStatus
from omega_lib.synchro.registry import ZoneState

from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.fail2ban import FileFacts, Presence
from omega_connect.domain.links import Check, CheckCode, CheckStatus, Link, LinkKind, Repair, RepairKind
from omega_connect.domain.zone import (
    TOKEN_DATE_KEY,
    ZONE_DIRECTORIES,
    ZoneFacts,
    ZoneSubject,
    encode,
    read_registry,
    right_directory,
    right_file,
    same_document,
    zone_services,
)

ZONE_REPAIR = Repair(RepairKind.ZONE)


def _found(entry: FileFacts) -> str:
    return f"{entry.owner}:{entry.group} {entry.mode & 0o7777:04o}"


def zone_link(facts: ZoneFacts, detection: DetectionReport, subject: ZoneSubject, command: str) -> Link:
    """`command` : commande d'omega-connect a proposer (`<racine>/omega-connect.sh`)."""
    establish = f"{command} etablir"
    root = facts.root

    def link(*checks: Check) -> Link:
        return Link(LinkKind.ZONE, "", "", tuple(checks))

    def fixed(code: CheckCode, status: CheckStatus, subject: str = "", detail: str = "") -> Check:
        """Ecart corrige par `etablir` (ce que le registre dit avoir cree) : propose aussi par `reparer`."""
        return Check(code, status, subject, detail, fix=establish, repair=ZONE_REPAIR)

    if root.presence is Presence.MISSING:
        return link(Check(CheckCode.ZONE_ABSENT, CheckStatus.INFO, facts.path, fix=establish))
    if root.presence is Presence.UNKNOWN:
        return link(Check(CheckCode.ZONE_UNREADABLE, CheckStatus.UNVERIFIABLE, facts.path, root.detail))
    if root.is_symlink or not root.is_dir:
        return link(Check(CheckCode.ZONE_UNSAFE, CheckStatus.FAILURE, facts.path))

    checks: list[Check] = []
    if not facts.group_exists:
        checks.append(fixed(CheckCode.ZONE_GROUP_MISSING, CheckStatus.FAILURE, ZONE_GROUP))
    member = bool(subject.user) and subject.user in facts.group_members
    awaiting_relogin = member and ZONE_GROUP not in subject.session_groups
    if subject.user:
        if not member:
            checks.append(fixed(CheckCode.ZONE_MEMBER_MISSING, CheckStatus.WARNING, subject.user))
        elif awaiting_relogin and facts.listing_known:
            checks.append(Check(CheckCode.ZONE_RELOGIN, CheckStatus.INFO, subject.user))
        elif not awaiting_relogin:
            checks.append(Check(CheckCode.ZONE_MEMBER_OK, CheckStatus.OK, subject.user))
    if not right_directory(root):
        checks.append(Check(CheckCode.ZONE_DIRECTORY_RIGHTS, CheckStatus.WARNING, facts.path, _found(root),
                            fix=establish, repair=ZONE_REPAIR))
    if not facts.listing_known:
        # Non verifiable, et dit pourquoi (decision de l'auteur, 2026-11-10) : en attente de reconnexion, ou pas
        # membre du groupe, ou illisible pour une autre raison.
        if awaiting_relogin:
            checks.append(Check(CheckCode.ZONE_AWAITING_RELOGIN, CheckStatus.UNVERIFIABLE, subject.user,
                                facts.path))
        elif subject.user and not member:
            checks.append(fixed(CheckCode.ZONE_NOT_MEMBER_UNREADABLE, CheckStatus.UNVERIFIABLE, facts.path,
                                subject.user))
        else:
            checks.append(Check(CheckCode.ZONE_UNREADABLE, CheckStatus.UNVERIFIABLE, facts.path, root.detail))
        return link(*checks)

    result = read_registry(facts)
    if result.status is ReadStatus.ABSENT:
        checks.append(Check(CheckCode.ZONE_FOREIGN, CheckStatus.WARNING, facts.path))
        return link(*checks)
    if result.status is ReadStatus.UNREADABLE:
        checks.append(Check(CheckCode.ZONE_UNREADABLE, CheckStatus.UNVERIFIABLE, facts.path, result.detail))
        return link(*checks)
    registry = result.value
    if registry is None:
        checks.append(Check(CheckCode.ZONE_REGISTRY_DAMAGED, CheckStatus.FAILURE, facts.absolute("registre.json"),
                            result.detail))
        return link(*checks)
    if registry.state is ZoneState.FROZEN:
        checks.append(fixed(CheckCode.ZONE_FROZEN, CheckStatus.WARNING, facts.path))

    conforming = 0
    for relative in ZONE_DIRECTORIES[1:]:
        entry = facts.entry(relative)
        if entry.presence is not Presence.PRESENT:
            checks.append(fixed(CheckCode.ZONE_DIRECTORY_MISSING, CheckStatus.WARNING, entry.path))
        elif not right_directory(entry):
            checks.append(Check(CheckCode.ZONE_DIRECTORY_RIGHTS, CheckStatus.WARNING, entry.path, _found(entry),
                                fix=establish, repair=ZONE_REPAIR))
        else:
            conforming += 1
    if conforming and right_directory(root):
        checks.append(Check(CheckCode.ZONE_DIRECTORY_OK, CheckStatus.OK, facts.path, str(conforming + 1)))

    installed = {item.installation_id: item for item in detection.installations
                 if item.token is not None and item.token_status is ReadStatus.OK}
    duplicated = {duplicate.installation_id for duplicate in detection.duplicates}
    for linked in registry.installations:
        current = installed.get(linked.installation_id)
        short = linked.installation_id[:8]
        if current is None or current.token is None:
            checks.append(Check(CheckCode.ZONE_TOOL_GONE, CheckStatus.WARNING, linked.root, short,
                                fix=f"{command} retirer {short}"))
            continue
        entry = facts.entry(linked.token_file)
        if entry.presence is not Presence.PRESENT:
            checks.append(fixed(CheckCode.ZONE_COPY_MISSING, CheckStatus.WARNING, entry.path))
        elif not right_file(entry):
            checks.append(Check(CheckCode.ZONE_COPY_RIGHTS, CheckStatus.WARNING, entry.path, _found(entry),
                                fix=establish, repair=ZONE_REPAIR))
        elif not same_document(facts.contents.get(linked.token_file, b""), encode(token_to_dict(current.token)),
                               TOKEN_DATE_KEY):
            checks.append(fixed(CheckCode.ZONE_COPY_STALE, CheckStatus.WARNING, linked.root, short))
        else:
            checks.append(Check(CheckCode.ZONE_COPY_OK, CheckStatus.OK, linked.root, short))
    for service in zone_services(detection):
        if service.service in facts.service_groups:
            checks.append(Check(CheckCode.ZONE_SERVICE_GROUP_OK, CheckStatus.OK, service.service, service.root))
        else:
            checks.append(fixed(CheckCode.ZONE_SERVICE_GROUP_MISSING, CheckStatus.WARNING, service.service,
                                service.root))
    registered = {item.installation_id for item in registry.installations}
    checks.extend(fixed(CheckCode.ZONE_NOT_LINKED, CheckStatus.WARNING, item.root, item.tool)
                  for identifier, item in sorted(installed.items(), key=lambda pair: pair[1].root)
                  if identifier not in registered and identifier not in duplicated)
    return link(*checks)
