# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Faux systeme pour le lot D : aucune commande root n'est jamais lancee par les tests."""
from __future__ import annotations

import os
import posixpath
from pathlib import Path

from omega_lib.synchro.constants import ZONE_GROUP
from omega_lib.synchro.models import InstallToken, InstanceSheet, ReadStatus, ServiceInfo

from omega_connect.domain.detection import DetectedInstallation, DetectionReport, SheetResult, Source
from omega_connect.domain.fail2ban import FileFacts, Presence
from omega_connect.domain.zone import CommandOutcome, Operation, OperationKind, ZoneFacts, ZoneSubject

AT = "2026-11-10T12:00:00Z"
LATER = "2026-11-11T08:00:00Z"
SERV_ID, FIRE_ID = "a" * 32, "b" * 32
SUBJECT = ZoneSubject("k", ("k", ZONE_GROUP))


def _token(tool: str, identifier: str, root: str, version: str = "1.0.0") -> InstallToken:
    return InstallToken(tool, version, identifier, "m", root, "k", AT, AT)


def _installation(tool: str, identifier: str, root: str, *, version: str = "1.0.0",
                  sheet: bool = False, service: ServiceInfo | None = None) -> DetectedInstallation:
    token = _token(tool, identifier, root, version)
    result = None
    if sheet:
        result = SheetResult(ReadStatus.OK, InstanceSheet(tool, version, identifier, tool, AT, service=service))
    names = (service.unit.removesuffix(".service"),) if service is not None else ()
    return DetectedInstallation(root, tool, (Source.HOME,), "k", ReadStatus.OK, token, sheet=result,
                                service_names=names)


def _detection(*items: DetectedInstallation) -> DetectionReport:
    return DetectionReport("/home/k", tuple(items))


SERV = _installation("omega-serv", SERV_ID, "/home/k/omega-serv", sheet=True)
FIRE = _installation("omega-fire", FIRE_ID, "/home/k/omega-fire")
SERVICE = ServiceInfo("systemd", "omega-serv.service", "omega-serv", "omega-serv", "active")
SERV_SERVICE = _installation("omega-serv", SERV_ID, "/home/k/omega-serv", sheet=True, service=SERVICE)
"""omega-serv dont le service tourne sous le compte dedie omega-serv (lot E : groupe donne au service)."""


class FakeSystem:
    """Faux systeme : un dossier temporaire tient lieu de `/var/lib`, les droits root sont notes a cote
    (jamais appliques : les tests ne tournent pas en root), les groupes sont un dictionnaire."""

    def __init__(self, base: Path) -> None:
        self.base = base
        (base / "var" / "lib").mkdir(parents=True)
        self.zone = str(base / "var" / "lib" / "omega-synchro")
        self.groups: dict[str, set[str]] = {"k": set(), "wheel": {"k"}}
        self.meta: dict[str, tuple[str, str, int]] = {}
        self.ran: list[tuple[str, ...]] = []
        self.fail_on: OperationKind | None = None
        self.service_groups: set[str] = set()
        """Services dont omega-serv a pose le complement systemd (faux /etc/systemd/system)."""

    # ---- PrivilegedRunner ----
    def authenticate(self) -> bool:
        return True

    def run(self, operation: Operation) -> CommandOutcome:
        argv = operation.argv("/tmp/contenu-prepare")
        self.ran.append(argv)
        if operation.kind is self.fail_on:
            return CommandOutcome(1, "simulated failure")
        name, args = argv[0], list(argv[1:])
        try:
            if name == "groupadd":
                if args[-1] in self.groups:
                    return CommandOutcome(9, "group exists")
                self.groups[args[-1]] = set()
            elif name == "groupdel":
                del self.groups[args[-1]]
            elif name == "gpasswd":
                flag, user, group = args
                (self.groups[group].add if flag == "-a" else self.groups[group].discard)(user)
            elif name == "install" and args[0] == "-d":
                path = args[-1]
                os.makedirs(path, exist_ok=True)
                self.meta[path] = (args[2], args[4], int(args[6], 8))
            elif name == "install":
                path = args[-1]
                assert args[-2] == "/tmp/contenu-prepare"
                Path(path).write_bytes(operation.content)
                self.meta[path] = (args[1], args[3], int(args[5], 8))
            elif name == "rm":
                Path(args[-1]).unlink(missing_ok=True)
                self.meta.pop(args[-1], None)
            elif name == "rmdir":
                os.rmdir(args[-1])
                self.meta.pop(args[-1], None)
            elif name.endswith("/omega-serv.sh") and args[:2] == ["synchro", "groupe-service"]:
                # Comme omega-serv : refuse sans le groupe (le service ne demarrerait plus).
                if args[2] == "ajouter":
                    if ZONE_GROUP not in self.groups:
                        return CommandOutcome(1, "group omega-synchro missing")
                    self.service_groups.add(args[-1])
                else:
                    self.service_groups.discard(args[-1])
            else:  # pragma: no cover - commande inconnue = erreur du plan
                return CommandOutcome(127, f"unknown command {name}")
        except (OSError, KeyError) as error:
            return CommandOutcome(1, str(error))
        return CommandOutcome(0)

    # ---- ZoneInspector ----
    @property
    def zone_path(self) -> str:
        return self.zone

    def _facts(self, path: str) -> FileFacts:
        if os.path.islink(path):
            return FileFacts(path, Presence.PRESENT, is_symlink=True, owner="k", group="k", mode=0o777)
        owner, group, mode = self.meta.get(path, ("k", "k", 0o644))
        return FileFacts(path, Presence.PRESENT, is_file=os.path.isfile(path), is_dir=os.path.isdir(path),
                         owner=owner, group=group, mode=mode)

    def inspect(self, *, elevated: bool = True) -> ZoneFacts:
        group = self.groups.get(ZONE_GROUP)
        if not os.path.lexists(self.zone):
            return ZoneFacts(self.zone, {"": FileFacts(self.zone, Presence.MISSING)}, True,
                             group_exists=group is not None, group_members=tuple(sorted(group or ())),
                             service_groups=frozenset(self.service_groups))
        entries = {"": self._facts(self.zone)}
        contents: dict[str, bytes] = {}
        if entries[""].is_dir and not entries[""].is_symlink:
            for name in sorted(os.listdir(self.zone)):
                path = posixpath.join(self.zone, name)
                entries[name] = self._facts(path)
                if entries[name].is_dir:
                    for child in sorted(os.listdir(path)):
                        entries[f"{name}/{child}"] = self._facts(posixpath.join(path, child))
            for relative, entry in entries.items():
                if entry.is_file and relative.endswith(".json"):
                    contents[relative] = Path(entry.path).read_bytes()
        return ZoneFacts(self.zone, entries, True, contents, group is not None, tuple(sorted(group or ())),
                         frozenset(self.service_groups))

    def snapshot(self) -> tuple[object, ...]:
        files = {}
        for directory, _dirs, names in os.walk(self.base):
            files[directory] = "dir"
            for name in names:
                files[posixpath.join(directory, name)] = Path(directory, name).read_bytes()
        return (files, {name: frozenset(members) for name, members in self.groups.items()}, dict(self.meta),
                frozenset(self.service_groups))
