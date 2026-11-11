# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Zone neutre (spec etape 3, §3.3 et §3.5 ; lot D) : plans de commandes root, regles pures.

Un plan est une liste de commandes systeme ordinaires (groupadd, install, gpasswd, rm, rmdir, groupdel),
affichees avant d'etre lancees une a une avec sudo. Chaque creation est inscrite au registre
(`<zone>/registre.json`, omega-lib `synchro.registry`) ; `retirer --tout` ne defait que ce que le registre
liste, dans l'ordre inverse. Rien ici ne lit ni n'ecrit la machine : l'etat constate arrive dans `ZoneFacts`."""
from __future__ import annotations

import json
import posixpath
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from omega_lib.synchro.codec import sheet_to_dict, token_to_dict
from omega_lib.synchro.constants import (
    TOOL_LAUNCHERS,
    ZONE_BANS_DIR,
    ZONE_DIR_MODE,
    ZONE_FILE_MODE,
    ZONE_GROUP,
    ZONE_LINKS_DIR,
    ZONE_REGISTRY,
    ZONE_SHEETS_DIR,
    ZONE_TOKENS_DIR,
)
from omega_lib.synchro.models import ReadResult, ReadStatus
from omega_lib.synchro.registry import (
    CreatedItem,
    CreatedKind,
    LinkedInstallation,
    ZoneRegistry,
    ZoneState,
    registry_from_dict,
    registry_to_dict,
    sheet_copy_name,
    token_copy_name,
)

from omega_connect.domain.detection import DetectedInstallation, DetectionReport
from omega_connect.domain.fail2ban import FileFacts, Presence

ZONE_SUBDIRS = (ZONE_TOKENS_DIR, ZONE_SHEETS_DIR, ZONE_LINKS_DIR, ZONE_BANS_DIR)
ZONE_DIRECTORIES = ("", *ZONE_SUBDIRS)
"""Dossiers de la zone, relatifs a sa racine (`""` = la zone elle-meme), dans l'ordre de creation."""
CONTENT_PLACEHOLDER = "<contenu>"
"""Remplace, a l'affichage, le fichier temporaire qui porte le contenu prepare d'une copie."""


# ---- etat constate ------------------------------------------------------------------------------

@dataclass(frozen=True)
class ZoneFacts:
    """Ce qui existe sur la machine : zone, entrees (cle = chemin relatif a la zone, `""` = la zone), groupe."""

    path: str
    entries: Mapping[str, FileFacts]
    listing_known: bool
    """Le contenu de la zone a pu etre liste (groupe omega-synchro dans la session, ou lecture avec sudo)."""
    contents: Mapping[str, bytes] = field(default_factory=dict)
    """Contenu lu du registre et des copies (jetons/, fiches/)."""
    group_exists: bool = False
    group_members: tuple[str, ...] = ()
    service_groups: frozenset[str] = frozenset()
    """Services dont le complement systemd donne le groupe de la zone (`<service>.service.d/omega-synchro.conf`),
    lu sans root (lot E)."""

    @property
    def root(self) -> FileFacts:
        return self.entries.get("", FileFacts(self.path, Presence.MISSING))

    def entry(self, relative: str) -> FileFacts:
        return self.entries.get(relative, FileFacts(self.absolute(relative),
                                                    Presence.MISSING if self.listing_known else Presence.UNKNOWN))

    def absolute(self, relative: str) -> str:
        return posixpath.join(self.path, relative) if relative else self.path


@dataclass(frozen=True)
class ZoneSubject:
    """La personne pour qui la zone est etablie (compte qui lance, ou `SUDO_USER`)."""

    user: str
    session_groups: tuple[str, ...] = ()
    """Groupes de la session en cours : un ajout au groupe ne compte qu'apres reconnexion."""


def read_registry(facts: ZoneFacts) -> ReadResult[ZoneRegistry]:
    if facts.root.presence is Presence.MISSING:
        return ReadResult(ReadStatus.ABSENT)
    raw = facts.contents.get(ZONE_REGISTRY)
    if raw is None:
        entry = facts.entry(ZONE_REGISTRY)
        if entry.presence is Presence.MISSING:
            return ReadResult(ReadStatus.ABSENT)
        return ReadResult(ReadStatus.UNREADABLE, detail=entry.detail or "permission denied")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        return ReadResult(ReadStatus.INVALID, detail=f"not JSON: {error}")
    return registry_from_dict(data)


def right_directory(entry: FileFacts) -> bool:
    return (entry.is_dir and not entry.is_symlink and entry.owner == "root" and entry.group == ZONE_GROUP
            and entry.mode & 0o7777 == ZONE_DIR_MODE)


def right_file(entry: FileFacts) -> bool:
    return (entry.is_file and not entry.is_symlink and entry.owner == "root" and entry.group == ZONE_GROUP
            and entry.mode & 0o7777 == ZONE_FILE_MODE)


SERV_TOOL = "omega-serv"
SERVICE_GROUP_ARGUMENTS = ("synchro", "groupe-service")


@dataclass(frozen=True)
class ZoneService:
    """Service systemd d'une instance omega-serv qui tourne sous un compte dedie : il ne lit la zone que si
    omega-serv lui donne le groupe (spec §5, lot E). Le compte proprietaire, lui, est membre du groupe."""

    service: str
    root: str


def zone_services(detection: DetectionReport) -> tuple[ZoneService, ...]:
    services: dict[str, ZoneService] = {}
    for item in detection.installations:
        sheet = item.sheet.sheet if item.sheet is not None and item.sheet.status is ReadStatus.OK else None
        info = sheet.service if sheet is not None else None
        if item.tool != SERV_TOOL or info is None or info.manager != "systemd" or not info.unit:
            continue
        if not info.user or info.user == item.owner:
            continue
        name = info.unit.removesuffix(".service")
        services.setdefault(name, ZoneService(name, item.root))
    return tuple(sorted(services.values(), key=lambda service: service.service))


# ---- operations ---------------------------------------------------------------------------------

class OperationKind(str, Enum):
    CREATE_GROUP = "create-group"
    CREATE_DIRECTORY = "create-directory"
    ADD_MEMBER = "add-member"
    WRITE_FILE = "write-file"
    REMOVE_FILE = "remove-file"
    REMOVE_DIRECTORY = "remove-directory"
    REMOVE_MEMBER = "remove-member"
    DELETE_GROUP = "delete-group"
    GRANT_SERVICE_GROUP = "grant-service-group"
    """omega-serv donne le groupe a son service (complement systemd) : commande de l'outil, lancee en root."""
    REVOKE_SERVICE_GROUP = "revoke-service-group"


class FileRole(str, Enum):
    REGISTRY = "registry"
    TOKEN_COPY = "token-copy"
    SHEET_COPY = "sheet-copy"


@dataclass(frozen=True)
class Operation:
    kind: OperationKind
    target: str
    """Nom du groupe, chemin absolu, nom du compte (ajout / retrait du groupe) ou nom du service."""
    content: bytes = b""
    role: FileRole | None = None
    subject: str = ""
    """Ce que concerne l'operation (racine d'un outil : affichage, et lanceur d'omega-serv) ; jamais traduit."""
    record: CreatedItem | None = None
    """Creation a inscrire au registre une fois la commande reussie."""
    undoes: CreatedItem | None = None
    """Creation du registre que cette commande defait."""
    links: LinkedInstallation | None = None
    unlinks: str = ""
    """Identifiant d'installation dont la copie est retiree."""

    def argv(self, source: str = CONTENT_PLACEHOLDER) -> tuple[str, ...]:
        """Commande lancee en root ; `source` = fichier temporaire du contenu (ecriture seulement)."""
        group, directory_mode, file_mode = ZONE_GROUP, f"{ZONE_DIR_MODE:04o}", f"{ZONE_FILE_MODE:04o}"
        launcher = posixpath.join(self.subject, TOOL_LAUNCHERS[SERV_TOOL])
        commands: dict[OperationKind, tuple[str, ...]] = {
            OperationKind.CREATE_GROUP: ("groupadd", "--system", self.target),
            OperationKind.CREATE_DIRECTORY: ("install", "-d", "-o", "root", "-g", group, "-m", directory_mode,
                                             self.target),
            OperationKind.ADD_MEMBER: ("gpasswd", "-a", self.target, group),
            OperationKind.WRITE_FILE: ("install", "-o", "root", "-g", group, "-m", file_mode, source, self.target),
            OperationKind.REMOVE_FILE: ("rm", "-f", "--", self.target),
            OperationKind.REMOVE_DIRECTORY: ("rmdir", "--", self.target),
            OperationKind.REMOVE_MEMBER: ("gpasswd", "-d", self.target, group),
            OperationKind.DELETE_GROUP: ("groupdel", self.target),
            OperationKind.GRANT_SERVICE_GROUP: (launcher, *SERVICE_GROUP_ARGUMENTS, "ajouter", "--service-name",
                                                self.target),
            OperationKind.REVOKE_SERVICE_GROUP: (launcher, *SERVICE_GROUP_ARGUMENTS, "retirer", "--service-name",
                                                 self.target),
        }
        return commands[self.kind]


# ---- plans --------------------------------------------------------------------------------------

class PlanAction(str, Enum):
    ESTABLISH = "establish"
    REMOVE_ALL = "remove-all"
    FREEZE = "freeze"
    REMOVE_TOOL = "remove-tool"


class NoteCode(str, Enum):
    ZONE_UNSAFE = "zone-unsafe"
    ZONE_FOREIGN = "zone-foreign"
    ZONE_UNREADABLE = "zone-unreadable"
    REGISTRY_DAMAGED = "registry-damaged"
    NOT_ESTABLISHED = "not-established"
    TARGET_NOT_FOUND = "target-not-found"
    TARGET_STILL_INSTALLED = "target-still-installed"
    STILL_INSTALLED_SKIPPED = "still-installed-skipped"
    NOT_LINKED = "not-linked"
    DUPLICATE_SKIPPED = "duplicate-skipped"
    TOOL_GONE = "tool-gone"
    RELOGIN = "relogin"
    NOTHING_TO_DO = "nothing-to-do"
    UNKNOWN_FILES_KEPT = "unknown-files-kept"
    GROUP_KEPT = "group-kept"
    SERVICE_GROUP_KEPT = "service-group-kept"
    """Complement systemd present mais omega-serv introuvable : le groupe reste (sinon le service ne demarre plus)."""
    SERVICE_RESTART = "service-restart"
    """Le groupe donne (ou retire) au service compte a son prochain redemarrage."""
    FOREIGN_DIRECTORY_IGNORED = "foreign-directory-ignored"
    ALREADY_FROZEN = "already-frozen"


REFUSALS = frozenset({
    NoteCode.ZONE_UNSAFE, NoteCode.ZONE_FOREIGN, NoteCode.ZONE_UNREADABLE, NoteCode.REGISTRY_DAMAGED,
    NoteCode.NOT_ESTABLISHED, NoteCode.TARGET_NOT_FOUND, NoteCode.TARGET_STILL_INSTALLED,
})
"""Remarques qui empechent le plan : aucune commande n'est proposee."""


@dataclass(frozen=True)
class PlanNote:
    code: NoteCode
    subject: str = ""
    detail: str = ""


@dataclass(frozen=True)
class ZonePlan:
    action: PlanAction
    zone: str
    now: str
    base: ZoneRegistry | None
    operations: tuple[Operation, ...] = ()
    notes: tuple[PlanNote, ...] = ()
    state: ZoneState = ZoneState.ACTIVE
    relinks: tuple[LinkedInstallation, ...] = ()
    """Installations deja reliees dont seules les informations changent (version...) : registre seulement."""
    forgets: tuple[str, ...] = ()
    """Installations que le registre oublie sans commande (leurs copies n'existent deja plus)."""
    released: tuple[CreatedItem, ...] = ()
    """Creations que le registre oublie sans commande (deja defaites a la main ou par l'outil)."""

    @property
    def refused(self) -> bool:
        return any(note.code in REFUSALS for note in self.notes)


def encode(data: Mapping[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _refuse(action: PlanAction, facts: ZoneFacts, now: str, note: PlanNote) -> ZonePlan:
    return ZonePlan(action, facts.path, now, None, notes=(note,))


def _registry_or_refusal(action: PlanAction, facts: ZoneFacts, now: str, *,
                         absent_ok: bool) -> ZoneRegistry | ZonePlan | None:
    root = facts.root
    if root.presence is Presence.MISSING:
        return None if absent_ok else _refuse(action, facts, now, PlanNote(NoteCode.NOT_ESTABLISHED, facts.path))
    if root.is_symlink or not root.is_dir:
        return _refuse(action, facts, now, PlanNote(NoteCode.ZONE_UNSAFE, facts.path))
    result = read_registry(facts)
    if result.status is ReadStatus.ABSENT:
        return _refuse(action, facts, now, PlanNote(NoteCode.ZONE_FOREIGN, facts.path))
    if result.status is ReadStatus.UNREADABLE or root.presence is Presence.UNKNOWN:
        return _refuse(action, facts, now, PlanNote(NoteCode.ZONE_UNREADABLE, facts.path, result.detail))
    if result.value is None:
        return _refuse(action, facts, now, PlanNote(NoteCode.REGISTRY_DAMAGED, facts.absolute(ZONE_REGISTRY),
                                                    result.detail))
    return result.value


def registry_after(plan: ZonePlan, done: Iterable[Operation]) -> ZoneRegistry:
    """Registre une fois `done` executees (toutes : registre final ; une partie : reprise apres un echec)."""
    base = plan.base or ZoneRegistry(plan.zone, plan.state, plan.now)
    created = list(base.created)
    installations = {item.installation_id: item for item in base.installations}
    for item in plan.relinks:
        if item.installation_id in installations:
            installations[item.installation_id] = item
    for identifier in plan.forgets:
        installations.pop(identifier, None)
    released = {(item.kind, item.target) for item in plan.released}
    created = [item for item in created if (item.kind, item.target) not in released]
    for operation in done:
        if operation.record is not None:
            created.append(operation.record)
        if operation.undoes is not None:
            created = [item for item in created
                       if (item.kind, item.target) != (operation.undoes.kind, operation.undoes.target)]
        if operation.links is not None:
            installations[operation.links.installation_id] = operation.links
        if operation.unlinks:
            installations.pop(operation.unlinks, None)
    return ZoneRegistry(plan.zone, plan.state, plan.now, tuple(created),
                        tuple(sorted(installations.values(), key=lambda item: (item.root, item.installation_id))))


def zone_exists_after(plan: ZonePlan, facts: ZoneFacts, done: Iterable[Operation]) -> bool:
    exists = facts.root.presence is not Presence.MISSING
    for operation in done:
        if operation.target == plan.zone and operation.kind is OperationKind.CREATE_DIRECTORY:
            exists = True
        elif operation.target == plan.zone and operation.kind is OperationKind.REMOVE_DIRECTORY:
            exists = False
    return exists


def registry_operation(plan: ZonePlan, done: Iterable[Operation]) -> Operation:
    content = encode(registry_to_dict(registry_after(plan, done)))
    return Operation(OperationKind.WRITE_FILE, posixpath.join(plan.zone, ZONE_REGISTRY), content,
                     role=FileRole.REGISTRY)


def _comparable(registry: ZoneRegistry | None) -> dict[str, Any] | None:
    if registry is None:
        return None
    data = registry_to_dict(registry)
    data.pop("updated_at")
    return data


def _with_registry(plan: ZonePlan, *, force: bool = False) -> ZonePlan:
    """Ajoute l'ecriture du registre si quelque chose change (ou `force`) ; sinon « rien a faire »."""
    final = registry_after(plan, plan.operations)
    if force or plan.operations or _comparable(final) != _comparable(plan.base):
        return replace(plan, operations=(*plan.operations, registry_operation(plan, plan.operations)))
    return replace(plan, notes=(*plan.notes, PlanNote(NoteCode.NOTHING_TO_DO, plan.zone)))


TOKEN_DATE_KEY = "updated_at"
SHEET_DATE_KEY = "generated_at"


def _without(raw: bytes, key: str) -> object:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if isinstance(data, dict):
        data.pop(key, None)
    return data


def same_document(current: bytes, wanted: bytes, date_key: str) -> bool:
    """Meme contenu a la date pres : un jeton rafraichi (updated_at) ou une fiche regeneree (generated_at)
    ne rend pas la copie perimee ; une version, une racine ou une capacite changee, si."""
    first = _without(current, date_key)
    return first is not None and first == _without(wanted, date_key)


def _needs_write(facts: ZoneFacts, relative: str, content: bytes, date_key: str) -> bool:
    if not right_file(facts.entry(relative)):
        return True
    current = facts.contents.get(relative)
    return current is None or not same_document(current, content, date_key)


def _linkable(detection: DetectionReport, notes: list[PlanNote]) -> list[DetectedInstallation]:
    duplicated = {duplicate.installation_id for duplicate in detection.duplicates}
    result = []
    for item in detection.installations:
        if item.token is None or item.token_status is not ReadStatus.OK:
            if item.tool:
                notes.append(PlanNote(NoteCode.NOT_LINKED, item.root, item.token_status.value))
            continue
        if item.installation_id in duplicated:
            notes.append(PlanNote(NoteCode.DUPLICATE_SKIPPED, item.root, item.installation_id[:8]))
            continue
        result.append(item)
    return result


def plan_establish(facts: ZoneFacts, detection: DetectionReport, subject: ZoneSubject, now: str) -> ZonePlan:
    """`etablir` : cree ce qui manque (groupe, dossiers, membre), recopie jetons et fiches, ecrit le registre.
    Relance sur une zone deja etablie : actualise les copies, remet les droits, rien d'autre."""
    found = _registry_or_refusal(PlanAction.ESTABLISH, facts, now, absent_ok=True)
    if isinstance(found, ZonePlan):
        return found
    base = found
    operations: list[Operation] = []
    notes: list[PlanNote] = []
    if not facts.group_exists:
        operations.append(Operation(OperationKind.CREATE_GROUP, ZONE_GROUP,
                                    record=CreatedItem(CreatedKind.GROUP, ZONE_GROUP, now)))
    zone_missing = facts.root.presence is Presence.MISSING
    for relative in ZONE_DIRECTORIES:
        entry = FileFacts(facts.absolute(relative), Presence.MISSING) if zone_missing else facts.entry(relative)
        path = facts.absolute(relative)
        if entry.presence is Presence.PRESENT and (entry.is_symlink or not entry.is_dir):
            return _refuse(PlanAction.ESTABLISH, facts, now, PlanNote(NoteCode.ZONE_UNSAFE, path))
        if entry.presence is not Presence.PRESENT:
            operations.append(Operation(OperationKind.CREATE_DIRECTORY, path,
                                        record=CreatedItem(CreatedKind.DIRECTORY, path, now)))
        elif not right_directory(entry):
            operations.append(Operation(OperationKind.CREATE_DIRECTORY, path))
    if subject.user and subject.user not in facts.group_members:
        operations.append(Operation(OperationKind.ADD_MEMBER, subject.user,
                                    record=CreatedItem(CreatedKind.MEMBER, subject.user, now)))
    if subject.user and ZONE_GROUP not in subject.session_groups:
        notes.append(PlanNote(NoteCode.RELOGIN, subject.user))
    granted = {item.target for item in base.created_items(CreatedKind.SERVICE_GROUP)} if base is not None else set()
    for service in zone_services(detection):
        if service.service not in facts.service_groups:
            record = None if service.service in granted else CreatedItem(CreatedKind.SERVICE_GROUP, service.service,
                                                                         now)
            operations.append(Operation(OperationKind.GRANT_SERVICE_GROUP, service.service, subject=service.root,
                                        record=record))
            notes.append(PlanNote(NoteCode.SERVICE_RESTART, service.service, service.root))

    relinks: list[LinkedInstallation] = []
    linked_ids: set[str] = set()
    for item in _linkable(detection, notes):
        token = item.token
        assert token is not None  # garanti par _linkable
        sheet = item.sheet.sheet if item.sheet is not None and item.sheet.status is ReadStatus.OK else None
        previous = base.installation(token.installation_id) if base is not None else None
        linked = LinkedInstallation(
            installation_id=token.installation_id, tool=token.tool,
            instance=sheet.instance if sheet is not None else token.tool, root=item.root,
            owner=token.owner or item.owner, version=token.version,
            linked_at=previous.linked_at if previous is not None else now,
            has_sheet=sheet is not None or (previous is not None and previous.has_sheet))
        linked_ids.add(token.installation_id)
        token_relative = token_copy_name(token.installation_id)
        token_content = encode(token_to_dict(token))
        if previous is None or _needs_write(facts, token_relative, token_content, TOKEN_DATE_KEY):
            operations.append(Operation(OperationKind.WRITE_FILE, facts.absolute(token_relative), token_content,
                                        role=FileRole.TOKEN_COPY, subject=item.root, links=linked))
        else:
            relinks.append(linked)
        if sheet is not None:
            sheet_relative = sheet_copy_name(token.installation_id)
            sheet_content = encode(sheet_to_dict(sheet))
            if _needs_write(facts, sheet_relative, sheet_content, SHEET_DATE_KEY):
                operations.append(Operation(OperationKind.WRITE_FILE, facts.absolute(sheet_relative), sheet_content,
                                            role=FileRole.SHEET_COPY, subject=item.root))
    if base is not None:
        notes.extend(PlanNote(NoteCode.TOOL_GONE, item.root, item.installation_id[:8])
                     for item in base.installations if item.installation_id not in linked_ids)
    plan = ZonePlan(PlanAction.ESTABLISH, facts.path, now, base, tuple(operations), tuple(notes),
                    ZoneState.ACTIVE, tuple(relinks))
    return _with_registry(plan, force=base is not None and base.state is not ZoneState.ACTIVE)


def _remove_copies(facts: ZoneFacts, items: Iterable[LinkedInstallation]) -> tuple[list[Operation], list[str]]:
    """Commandes qui suppriment les copies existantes ; identifiants a oublier sans commande (copie deja absente)."""
    operations: list[Operation] = []
    forgets: list[str] = []
    for item in items:
        token_present = facts.entry(item.token_file).presence is not Presence.MISSING
        if token_present:
            operations.append(Operation(OperationKind.REMOVE_FILE, facts.absolute(item.token_file),
                                        role=FileRole.TOKEN_COPY, subject=item.root, unlinks=item.installation_id))
        else:
            forgets.append(item.installation_id)
        if item.sheet_file and facts.entry(item.sheet_file).presence is not Presence.MISSING:
            operations.append(Operation(OperationKind.REMOVE_FILE, facts.absolute(item.sheet_file),
                                        role=FileRole.SHEET_COPY, subject=item.root))
    return operations, forgets


def _unknown_entries(facts: ZoneFacts, registry: ZoneRegistry) -> list[str]:
    known = {*ZONE_DIRECTORIES, ZONE_REGISTRY}
    for item in registry.installations:
        known.update(name for name in (item.token_file, item.sheet_file) if name)
    return sorted(relative for relative, entry in facts.entries.items()
                  if relative not in known and entry.presence is Presence.PRESENT)


def _revoke_services(facts: ZoneFacts, registry: ZoneRegistry, detection: DetectionReport | None,
                     notes: list[PlanNote]) -> tuple[list[Operation], list[CreatedItem], bool]:
    """Groupe retire des services AVANT le groupe lui-meme. Complement deja absent : oublie sans commande.
    omega-serv introuvable (lanceur inconnu) : le groupe est garde, sinon le service ne demarrerait plus."""
    roots: dict[str, str] = {}
    if detection is not None:
        roots = {service.service: service.root for service in zone_services(detection)}
        for installation in detection.installations:
            if installation.tool == SERV_TOOL:
                for name in installation.service_names:
                    roots.setdefault(name, installation.root)
    operations: list[Operation] = []
    released: list[CreatedItem] = []
    blocked = False
    for item in registry.created_items(CreatedKind.SERVICE_GROUP):
        if item.target not in facts.service_groups:
            released.append(item)
        elif item.target in roots:
            operations.append(Operation(OperationKind.REVOKE_SERVICE_GROUP, item.target, subject=roots[item.target],
                                        undoes=item))
            notes.append(PlanNote(NoteCode.SERVICE_RESTART, item.target, roots[item.target]))
        else:
            notes.append(PlanNote(NoteCode.SERVICE_GROUP_KEPT, item.target))
            blocked = True
    return operations, released, blocked


def plan_remove_all(facts: ZoneFacts, now: str, detection: DetectionReport | None = None) -> ZonePlan:
    """`retirer --tout` : defait exactement ce que le registre liste, dans l'ordre inverse. Un fichier que le
    registre ne connait pas n'est jamais supprime : son dossier (et la zone, et le groupe) restent."""
    found = _registry_or_refusal(PlanAction.REMOVE_ALL, facts, now, absent_ok=False)
    if isinstance(found, ZonePlan):
        return found
    assert found is not None
    registry = found
    if not facts.listing_known:
        return _refuse(PlanAction.REMOVE_ALL, facts, now, PlanNote(NoteCode.ZONE_UNREADABLE, facts.path))
    notes: list[PlanNote] = []
    operations, released, service_blocked = _revoke_services(facts, registry, detection, notes)
    copies, forgets = _remove_copies(facts, registry.installations)
    operations.extend(copies)
    for item in registry.created_items(CreatedKind.MEMBER):
        if item.target in facts.group_members:
            operations.append(Operation(OperationKind.REMOVE_MEMBER, item.target, undoes=item))

    unknown = _unknown_entries(facts, registry)
    blocked_dirs = {relative.split("/", 1)[0] if "/" in relative else "" for relative in unknown}
    notes.extend(PlanNote(NoteCode.UNKNOWN_FILES_KEPT, facts.absolute(relative)) for relative in unknown)
    allowed = {facts.absolute(relative): relative for relative in ZONE_DIRECTORIES}
    created_dirs = {item.target: item for item in registry.created_items(CreatedKind.DIRECTORY)}
    for target in created_dirs:
        if target not in allowed:
            notes.append(PlanNote(NoteCode.FOREIGN_DIRECTORY_IGNORED, target))
    zone_removable = facts.path in created_dirs and not blocked_dirs
    for relative in reversed(ZONE_SUBDIRS):
        path = facts.absolute(relative)
        if path in created_dirs and relative not in blocked_dirs:
            if facts.entry(relative).presence is not Presence.MISSING:
                operations.append(Operation(OperationKind.REMOVE_DIRECTORY, path, undoes=created_dirs[path]))
        elif facts.entry(relative).presence is Presence.PRESENT:
            zone_removable = False
    plan = ZonePlan(PlanAction.REMOVE_ALL, facts.path, now, registry, tuple(operations), tuple(notes),
                    registry.state, forgets=tuple(forgets), released=tuple(released))
    if zone_removable and not service_blocked:
        tail = [Operation(OperationKind.REMOVE_FILE, facts.absolute(ZONE_REGISTRY), role=FileRole.REGISTRY),
                Operation(OperationKind.REMOVE_DIRECTORY, facts.path, undoes=created_dirs[facts.path])]
        group_items = registry.created_items(CreatedKind.GROUP)
        if group_items and facts.group_exists:
            tail.append(Operation(OperationKind.DELETE_GROUP, group_items[0].target, undoes=group_items[0]))
        elif not group_items:
            notes.append(PlanNote(NoteCode.GROUP_KEPT, ZONE_GROUP))
        return replace(plan, operations=(*operations, *tail), notes=tuple(notes))
    notes.append(PlanNote(NoteCode.GROUP_KEPT, ZONE_GROUP))
    return _with_registry(replace(plan, notes=tuple(notes)), force=True)


def plan_freeze(facts: ZoneFacts, now: str) -> ZonePlan:
    """« Garder la zone (liens figes) » : rien n'est retire, le registre passe a l'etat fige."""
    found = _registry_or_refusal(PlanAction.FREEZE, facts, now, absent_ok=False)
    if isinstance(found, ZonePlan):
        return found
    assert found is not None
    if found.state is ZoneState.FROZEN:
        return ZonePlan(PlanAction.FREEZE, facts.path, now, found, notes=(PlanNote(NoteCode.ALREADY_FROZEN),),
                        state=ZoneState.FROZEN)
    return _with_registry(ZonePlan(PlanAction.FREEZE, facts.path, now, found, state=ZoneState.FROZEN), force=True)


def _matches(item: LinkedInstallation, target: str) -> bool:
    cleaned = target.rstrip("/") or target
    return cleaned in (item.tool, item.instance, item.root) or (
        len(cleaned) >= 8 and item.installation_id.startswith(cleaned))


def plan_remove_tool(facts: ZoneFacts, detection: DetectionReport, target: str, now: str) -> ZonePlan:
    """`retirer <outil>` : un outil desinstalle (racine disparue ou identifiant change) ; ses copies sont
    retirees et le registre l'oublie. Un outil toujours installe n'est pas retire (il reviendrait a la
    prochaine actualisation)."""
    found = _registry_or_refusal(PlanAction.REMOVE_TOOL, facts, now, absent_ok=False)
    if isinstance(found, ZonePlan):
        return found
    assert found is not None
    matches = [item for item in found.installations if _matches(item, target)]
    if not matches:
        return ZonePlan(PlanAction.REMOVE_TOOL, facts.path, now, found,
                        notes=(PlanNote(NoteCode.TARGET_NOT_FOUND, target),), state=found.state)
    installed = {item.installation_id for item in detection.installations
                 if item.token is not None and item.token_status is ReadStatus.OK}
    gone = [item for item in matches if item.installation_id not in installed]
    still = [item for item in matches if item.installation_id in installed]
    if not gone:
        return ZonePlan(PlanAction.REMOVE_TOOL, facts.path, now, found, state=found.state, notes=tuple(
            PlanNote(NoteCode.TARGET_STILL_INSTALLED, item.root, item.installation_id[:8]) for item in still))
    operations, forgets = _remove_copies(facts, gone)
    notes = tuple(PlanNote(NoteCode.STILL_INSTALLED_SKIPPED, item.root, item.installation_id[:8]) for item in still)
    plan = ZonePlan(PlanAction.REMOVE_TOOL, facts.path, now, found, tuple(operations), notes, found.state,
                    forgets=tuple(forgets))
    return _with_registry(plan, force=True)


def recovery_operation(plan: ZonePlan, facts: ZoneFacts, done: Sequence[Operation]) -> Operation | None:
    """Apres un echec au milieu d'un plan : registre a reecrire pour qu'il dise ce qui existe vraiment
    (sinon une creation reussie serait oubliee, et `retirer --tout` ne pourrait plus la defaire)."""
    if not done or not zone_exists_after(plan, facts, done):
        return None
    last = done[-1]
    if last.role is FileRole.REGISTRY and last.kind is OperationKind.WRITE_FILE:
        return None
    return registry_operation(plan, done)


@dataclass(frozen=True)
class CommandOutcome:
    code: int
    error: str = ""
    """Derniere ligne d'erreur de la commande (texte du systeme, jamais traduit)."""

    @property
    def ok(self) -> bool:
        return self.code == 0
