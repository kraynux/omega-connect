# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Updater (2026-11-22, demande de l'auteur : un seul endroit pour mettre a jour les applications, Reparer et le
Registre y renvoient).

- Lignes = ce qui est DEJA scanne (registre du parc) : machine, application, version installee ; rien n'est
  rescanne a l'ouverture.
- « Verifier les versions » : derniere version publiee de chaque outil (GitHub, puis le site), une seule requete
  par outil ; une version non publiee n'est jamais proposee.
- Mise a jour : machine du reseau -> plan calcule sur elle, archives verifiees, envoyees, `install.sh` dans le
  terminal (RemoteMachineScreen, moteur du lot R3) ; CETTE machine -> meme programme, meme dossier d'ordres, lance
  ici dans le terminal (plus de « a la main, README »)."""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Protocol

from omega_connect.domain.fleet import AppState
from omega_connect.domain.parc import MachineEntry
from omega_connect.domain.suite import SUITE_TOOL
from omega_connect.domain.tools import INSTALLABLE_TOOLS
from omega_connect.domain.updates import (
    Purpose,
    ReleaseArchive,
    ReleaseFailure,
    UpdateChoice,
    UpdateOrder,
    choose_update,
    result_from_dict,
    updates_to_dict,
)
from omega_connect.domain.versions import Outdated, archive_name, is_newer, version_key


@dataclass(frozen=True)
class UpdaterTools:
    releases: Releases
    runner: Callable[[list[str]], int]
    """Lance un programme dans le terminal (cette machine)."""


class UpdateState(str, Enum):
    NOT_CHECKED = "not-checked"
    UP_TO_DATE = "up-to-date"
    OUTDATED = "outdated"
    INCOMPLETE = "incomplete"
    """Installation inachevee (install.sh arrete) : a reinstaller."""
    UNKNOWN = "unknown"
    """Aucune version publiee trouvee (GitHub et site), ou version installee illisible."""
    UNREACHABLE = "unreachable"
    TO_INSTALL = "to-install"
    PRESENT = "present"
    """Installer : deja installee sur la machine."""


class Releases(Protocol):
    def latest(self, tool: str) -> str | ReleaseFailure: ...

    def fetch(self, tool: str, version: str) -> ReleaseArchive | ReleaseFailure: ...

    def origin(self, tool: str) -> str: ...


@dataclass(frozen=True)
class AppRow:
    machine: str
    """Nom affiche de la machine."""
    target: str
    """utilisateur@machine ; vide pour cette machine."""
    local: bool
    tool: str
    root: str
    version: str
    incomplete: bool = False
    reachable: bool = True
    latest: str = ""
    origin: str = ""
    failure: ReleaseFailure | None = None
    contains: str = ""
    """omega-suite : les outils embarques vus par le scan (« omega-stress 1.6.0 ») ; elle se met a jour avec eux."""
    install: bool = False
    """Installer : l'outil n'est pas sur la machine ; `root` = dossier a creer (`~/<outil>`)."""
    present: bool = False
    """Installer : l'outil est deja sur la machine (affiche, jamais reinstalle d'ici)."""

    @property
    def key(self) -> str:
        return f"{self.machine}:{self.root}"

    @property
    def state(self) -> UpdateState:
        if not self.reachable:
            return UpdateState.UNREACHABLE
        if self.present:
            return UpdateState.PRESENT
        if self.install:
            if self.failure is not None:
                return UpdateState.UNKNOWN
            return UpdateState.TO_INSTALL if self.latest else UpdateState.NOT_CHECKED
        if self.incomplete:
            return UpdateState.INCOMPLETE
        if self.failure is not None:
            return UpdateState.UNKNOWN
        if not self.latest:
            return UpdateState.NOT_CHECKED
        if version_key(self.version) is None:
            return UpdateState.UNKNOWN
        return UpdateState.OUTDATED if is_newer(self.latest, self.version) else UpdateState.UP_TO_DATE

    @property
    def actionable(self) -> bool:
        return self.state in (UpdateState.OUTDATED, UpdateState.INCOMPLETE, UpdateState.TO_INSTALL) and \
            bool(self.latest)

    def outdated(self) -> Outdated:
        return Outdated(self.tool, self.root, self.version, "", self.incomplete, install=self.install)


def app_rows(machines: Iterable[MachineEntry]) -> list[AppRow]:
    """Ce qui est deja scanne : cette machine d'abord, puis le reseau (meme ordre que le Registre). Une copie
    embarquee par omega-suite devient la ligne d'omega-suite (une par suite) : c'est elle qui se met a jour."""
    rows: list[AppRow] = []
    known: dict[str, int] = {}
    for entry in sorted(machines, key=lambda m: (not m.local, m.label)):
        for row in entry.rows:
            if not row.tool:
                continue
            target = "" if entry.local else entry.target
            incomplete = row.state is AppState.INCOMPLETE
            if row.suite:  # copie embarquee : c'est la ligne de sa suite
                line = AppRow(entry.label, target, entry.local, SUITE_TOOL, row.suite, row.suite_version, incomplete,
                              entry.reachable, contains=f"{row.tool} {row.version or '?'}")
            else:
                line = AppRow(entry.label, target, entry.local, row.tool, row.root, row.version, incomplete,
                              entry.reachable)
            if line.key not in known:
                known[line.key] = len(rows)
                rows.append(line)
                continue
            index = known[line.key]  # omega-suite vue elle-meme ET par ses outils embarques : une seule ligne
            current = rows[index]
            contains = ", ".join(part for part in (current.contains, line.contains) if part)
            rows[index] = replace(current, contains=contains, incomplete=current.incomplete or line.incomplete,
                                  version=current.version or line.version)
    return rows


def install_rows(machines: Iterable[MachineEntry]) -> list[AppRow]:
    """Installer : pour chaque machine joignable, chacun des 14 outils publies, deja la (version lue au dernier
    scan) ou a installer dans `~/<outil>`. Un omega-stress embarque par omega-suite ne compte pas : un omega-stress
    autonome peut s'installer a cote."""
    rows: list[AppRow] = []
    for entry in sorted(machines, key=lambda m: (not m.local, m.label)):
        if not entry.reachable:
            continue
        target = "" if entry.local else entry.target
        installed = {row.tool: row for row in entry.rows if row.tool and not row.suite}
        for tool in INSTALLABLE_TOOLS:
            found = installed.get(tool)
            if found is not None:
                rows.append(AppRow(entry.label, target, entry.local, tool, found.root, found.version, present=True))
            else:
                rows.append(AppRow(entry.label, target, entry.local, tool, f"~/{tool}", "", install=True))
    return rows


def check_versions(rows: list[AppRow], releases: Releases, only: set[str] | None = None) -> list[AppRow]:
    """Derniere version publiee de chaque outil (une requete par outil) ; `only` : cles des lignes a verifier."""
    latest: dict[str, str | ReleaseFailure] = {}
    checked = []
    for row in rows:
        if only is not None and row.key not in only:
            checked.append(row)
            continue
        if row.tool not in latest:
            latest[row.tool] = releases.latest(row.tool)
        found = latest[row.tool]
        if isinstance(found, ReleaseFailure):
            checked.append(replace(row, latest="", origin="", failure=found))
        else:
            checked.append(replace(row, latest=found, origin=releases.origin(row.tool), failure=None))
    return checked


# ---- cette machine ------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class LocalPrepared:
    directory: Path
    choices: tuple[UpdateChoice, ...]
    refused: tuple[tuple[UpdateChoice, ReleaseFailure], ...] = ()


def prepare_local(rows: Iterable[AppRow], releases: Releases, purpose: Purpose = Purpose.UPDATE) -> LocalPrepared:
    """Archives prises (GitHub ou site) et verifiees, posees avec le fichier d'ordres dans un dossier prive : le
    meme que celui qu'omega-connect envoie a une machine du reseau. Une archive refusee : rien n'est prepare."""
    choices = tuple(choose_update(row.outdated(), row.latest) for row in rows)
    directory = Path(tempfile.mkdtemp(prefix="omega-connect-maj-"))
    os.chmod(directory, 0o700)
    orders = []
    refused = []
    for choice in choices:
        if not choice.possible:
            refused.append((choice, choice.failure or ReleaseFailure.NO_RELEASE))
            continue
        fetched = releases.fetch(choice.outdated.tool, choice.latest)
        if isinstance(fetched, ReleaseFailure):
            refused.append((choice, fetched))
            continue
        name = archive_name(fetched.tool, fetched.version)
        shutil.move(fetched.path, directory / name)
        shutil.rmtree(Path(fetched.path).parent, ignore_errors=True)
        orders.append(UpdateOrder(choice.outdated.tool, choice.outdated.root, fetched.version, name,
                                  fetched.sha256, choice.mode))
    if refused:
        shutil.rmtree(directory, ignore_errors=True)
        return LocalPrepared(directory, choices, tuple(refused))
    (directory / "updates.json").write_text(json.dumps(updates_to_dict(tuple(orders), purpose)),
                                            encoding="utf-8")
    return LocalPrepared(directory, choices)


def run_local(prepared: LocalPrepared, runner: Callable[[list[str]], int]) -> int:
    """A appeler interface SUSPENDUE : le programme parle a la personne dans son terminal (sudo eventuel des
    `install.sh`), exactement comme sur une machine du reseau. `runner` : lanceur de programmes (infrastructure)."""
    return runner([sys.executable, "-m", "omega_connect.app.remote_agent", "run", str(prepared.directory)])


def finish_local(prepared: LocalPrepared) -> tuple[bool, str]:
    """Resultat relu puis dossier efface : (tout a reussi, texte des etapes)."""
    result = None
    with contextlib.suppress(OSError, ValueError):
        result = result_from_dict(json.loads((prepared.directory / "result.json").read_text(encoding="utf-8")))
    shutil.rmtree(prepared.directory, ignore_errors=True)
    if result is None:
        return False, ""
    lines = [f"{'✓' if step.code == 0 else '✗'} {step.tool or step.name.value} {step.detail}".rstrip()
             for step in result.steps]
    return result.ok, "\n".join(lines)
