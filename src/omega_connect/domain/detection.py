# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Detection des installations omega (spec etape 3, §3.1 et §9) : modeles et regles pures.

Tout est identifie par la RACINE reelle (candidats) puis par l'IDENTIFIANT d'installation (jeton) :
plusieurs instances d'omega-serv sur la meme machine ont chacune leur dossier, leur `var/`, leur jeton
et leur identifiant (decision Q6). Deux racines qui portent le meme identifiant (dossier copie a la main
avant sa premiere ouverture) sont SIGNALEES, jamais fusionnees."""
from __future__ import annotations

import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from omega_lib.synchro.models import InstallToken, InstanceSheet, ReadStatus


class Source(str, Enum):
    """Ou une installation a ete trouvee (ordre d'affichage = ordre de priorite, plan §7.4)."""

    SERV_REGISTRY = "serv-registry"
    SYSTEMD = "systemd"
    OPENRC = "openrc"
    RUNIT = "runit"
    HOME = "home"
    SRV = "srv"
    MANUAL = "manual"


SOURCE_ORDER = tuple(Source)


@dataclass(frozen=True)
class Candidate:
    root: str
    """Chemin reel (resolu), absolu."""
    source: Source
    tool_hint: str = ""
    """Outil suppose par la source (omega-serv pour un service ou le registre), vide sinon."""
    service_name: str = ""


@dataclass(frozen=True)
class MergedCandidate:
    root: str
    sources: tuple[Source, ...]
    tool_hint: str = ""
    service_names: tuple[str, ...] = ()


def merge_candidates(candidates: Iterable[Candidate]) -> list[MergedCandidate]:
    """Une entree par racine, sources reunies (dans l'ordre de priorite), noms de service reunis."""
    by_root: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_root.setdefault(candidate.root, []).append(candidate)
    merged = []
    for root, items in by_root.items():
        sources = tuple(s for s in SOURCE_ORDER if any(c.source is s for c in items))
        hint = next((c.tool_hint for c in items if c.tool_hint), "")
        services = tuple(sorted({c.service_name for c in items if c.service_name}))
        merged.append(MergedCandidate(root, sources, hint, services))
    return sorted(merged, key=lambda m: m.root)


_CONFIG_ARG = re.compile(r"--config[= ]\s*['\"]?([^'\"\s]+)/config/omega-serve\.json")
_WORKING_DIRECTORY = re.compile(r"^\s*WorkingDirectory\s*=\s*(\S+)\s*$", re.MULTILINE)
_OPENRC_DIRECTORY = re.compile(r"^\s*directory\s*=\s*['\"]?([^'\"\s]+)['\"]?\s*$", re.MULTILINE)


_SERVE_COMMAND = re.compile(r"(omega_serv|omega-serv)\S*(\s+--config\s+\S+)?\s+serve\b")


def is_server_service(text: str) -> bool:
    """Le service lance-t-il le serveur (`... omega_serv ... serve`) ? Ecarte les taches annexes
    (`omega-serv-log-rotation`, timers) qui ne sont pas des instances."""
    return bool(_SERVE_COMMAND.search(text))


def parse_service_root(text: str) -> str | None:
    """Racine d'omega-serv lue dans une unite systemd, un script OpenRC ou un `run` runit :
    `--config <racine>/config/omega-serve.json` d'abord (le plus sur), sinon le dossier de travail
    (`WorkingDirectory=`, `directory=`, `cd <dossier>`). Chemin absolu uniquement."""
    candidates: list[str] = []
    match = _CONFIG_ARG.search(text)
    if match:
        candidates.append(match.group(1))
    for pattern in (_WORKING_DIRECTORY, _OPENRC_DIRECTORY):
        found = pattern.search(text)
        if found:
            candidates.append(found.group(1))
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("cd "):
            try:
                parts = shlex.split(stripped)
            except ValueError:
                continue
            if len(parts) >= 2:
                candidates.append(parts[1])
    for candidate in candidates:
        if candidate.startswith("/") and ".." not in candidate.split("/") and "$" not in candidate:
            return candidate.rstrip("/") or "/"
    return None


@dataclass(frozen=True)
class SheetResult:
    status: ReadStatus
    sheet: InstanceSheet | None = None
    detail: str = ""
    """Raison courte (anglais ASCII, technique) si la fiche n'a pas pu etre obtenue."""


@dataclass(frozen=True)
class DetectedInstallation:
    root: str
    tool: str
    """Outil reconnu (jeton, sinon lanceur present a la racine) ; vide si inconnu."""
    sources: tuple[Source, ...]
    owner: str
    token_status: ReadStatus
    token: InstallToken | None = None
    token_detail: str = ""
    sheet: SheetResult | None = None
    """None : fiche non demandee (outil sans fiche, ou --sans-fiche)."""
    service_names: tuple[str, ...] = ()
    version: str = ""
    """Version lue dans les fichiers de l'outil (lot R3) ; vide si illisible. Connue meme sans carte ni fiche."""
    venv_ready: bool | None = None
    """`.venv/bin/activate` et `.venv/bin/python` presents (install.sh alle au bout) ; None : pas regarde."""

    @property
    def installation_id(self) -> str:
        return self.token.installation_id if self.token is not None else ""


@dataclass(frozen=True)
class DuplicateId:
    installation_id: str
    roots: tuple[str, ...]


class NoteKind(str, Enum):
    REGISTRY_UNREADABLE = "registry-unreadable"
    REGISTERED_INSTANCE_MISSING = "registered-instance-missing"
    SERVICE_FILE_UNREADABLE = "service-file-unreadable"
    SERVICE_ROOT_MISSING = "service-root-missing"
    SEARCH_STOPPED = "search-stopped"
    NETWORK_MOUNT_SKIPPED = "network-mount-skipped"
    MANUAL_NOT_FOUND = "manual-not-found"
    MANUAL_NOT_OMEGA = "manual-not-omega"


@dataclass(frozen=True)
class ScanNote:
    kind: NoteKind
    detail: str
    """Chemin ou nom concerne (jamais traduit)."""


@dataclass(frozen=True)
class DetectionReport:
    home: str
    installations: tuple[DetectedInstallation, ...]
    duplicates: tuple[DuplicateId, ...] = ()
    scan_notes: tuple[ScanNote, ...] = field(default_factory=tuple)
    """Remarques sur la recherche : montage reseau ignore, recherche interrompue..."""


def find_duplicate_ids(installations: Iterable[DetectedInstallation]) -> tuple[DuplicateId, ...]:
    roots_by_id: dict[str, list[str]] = {}
    for installation in installations:
        if installation.installation_id:
            roots_by_id.setdefault(installation.installation_id, []).append(installation.root)
    return tuple(
        DuplicateId(identifier, tuple(sorted(roots)))
        for identifier, roots in sorted(roots_by_id.items()) if len(roots) > 1
    )


def tool_for(token: InstallToken | None, layout_tool: str, hint: str) -> str:
    """Le jeton fait foi ; sinon la disposition des fichiers ; sinon ce que la source suppose."""
    if token is not None:
        return token.tool
    return layout_tool or hint
