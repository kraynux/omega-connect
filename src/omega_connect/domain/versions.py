# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Versions des outils (lot R3 ; decision de l'auteur, ETUDE_REFONTE §16).

- la version INSTALLEE se lit dans les fichiers de l'outil (`pyproject.toml`, ou la constante d'omega-fire), sans
  rien executer : une version trop ancienne n'a ni carte d'identite ni fiche, il faut pourtant la reconnaitre ;
- un outil plus ancien que sa premiere version a contrats (`synchro`) n'est jamais repare avec une commande qu'il
  ne connait pas (constate le 2026-11-10 : `omega-jail --apply --update` propose a omega-jail 1.1.0) : il est
  d'abord mis a jour ;
- les mises a jour viennent des Releases GitHub de chaque outil (`kraynux/<outil>`, etiquette `v<version>`), avec
  `sha.txt` attache : l'empreinte est verifiee avant tout envoi et avant toute extraction."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from omega_lib.synchro.models import ReadStatus

from omega_connect.core.constants import SHEET_TOOLS
from omega_connect.domain.detection import DetectedInstallation

CONTRACT_VERSIONS = {"omega-serv": "2.6.1", "omega-fire": "3.6.1", "omega-jail": "1.2.1"}
"""Premiere version de chaque outil qui a une carte d'identite (`synchro`) et les commandes de reparation
qu'omega-connect lance (`service permissions`, `--apply --update`) ; archives construites le 2026-11-10."""

GITHUB_OWNER = "kraynux"
GITHUB_BASE = "https://github.com"
RELEASE_TAG_PREFIX = "v"
SHA_FILE = "sha.txt"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
"""Au-dela, ce n'est pas une archive d'outil omega (omega-serv 2.6.1 : 7,7 Mo)."""

VERSION_FILES = {"omega-fire": ("src/omega_fire/core/constants.py", r'^OMEGA_FIRE_VERSION\s*=\s*"([^"]+)"')}
"""Ou lire la version, outil par outil ; par defaut `pyproject.toml`, ligne `version = "..."`."""
DEFAULT_VERSION_FILE = ("pyproject.toml", r'^version\s*=\s*"([^"]+)"')

_VERSION = re.compile(r"^\d+(?:\.\d+){0,3}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def version_key(version: str) -> tuple[int, ...] | None:
    """« 2.6.1 » -> (2, 6, 1) ; « 3.6 » -> (3, 6, 0) ; None si ce n'est pas une version numerique."""
    text = version.strip()
    if not _VERSION.match(text):
        return None
    numbers = [int(part) for part in text.split(".")]
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def read_version(text: str, tool: str) -> str:
    """Version tiree du contenu du fichier de version de l'outil ; vide si absente ou illisible."""
    _path, pattern = VERSION_FILES.get(tool, DEFAULT_VERSION_FILE)
    match = re.search(pattern, text, re.MULTILINE)
    if match is None or version_key(match.group(1)) is None:
        return ""
    return match.group(1)


def version_file(tool: str) -> str:
    return VERSION_FILES.get(tool, DEFAULT_VERSION_FILE)[0]


def minimum_version(tool: str) -> str:
    return CONTRACT_VERSIONS.get(tool, "")


def too_old(tool: str, version: str) -> bool:
    """Vrai seulement si la version est connue ET plus ancienne que la premiere version a contrats."""
    minimum = version_key(CONTRACT_VERSIONS.get(tool, ""))
    installed = version_key(version)
    return minimum is not None and installed is not None and installed < minimum


def is_newer(candidate: str, installed: str) -> bool:
    new = version_key(candidate)
    old = version_key(installed)
    return new is not None and (old is None or new > old)


# ---- Releases GitHub ----------------------------------------------------------------------------

def releases_url(tool: str) -> str:
    return f"{GITHUB_BASE}/{GITHUB_OWNER}/{tool}/releases"


def latest_url(tool: str) -> str:
    """GitHub redirige vers `.../releases/tag/v<version>` de la derniere Release publiee."""
    return f"{releases_url(tool)}/latest"


def version_from_tag_url(url: str) -> str:
    """Version lue dans l'adresse finale de `latest` ; vide si ce n'est pas une etiquette `v<version>`."""
    match = re.search(r"/releases/tag/v?(\d+(?:\.\d+){0,3})/?$", url)
    return match.group(1) if match else ""


def archive_name(tool: str, version: str) -> str:
    return f"{tool}-{version}.tar.gz"


def asset_url(tool: str, version: str, name: str) -> str:
    return f"{releases_url(tool)}/download/{RELEASE_TAG_PREFIX}{version}/{name}"


def expected_sha(sha_list: str, name: str) -> str:
    """Empreinte de `name` dans un `sha.txt` (`<empreinte>  <fichier>`) ; vide si absente ou mal formee."""
    for line in sha_list.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name and _SHA.match(parts[0].lower()):
            return parts[0].lower()
    return ""


class UpdateMode(str, Enum):
    OVER = "over"
    """Extraction par-dessus l'installation (l'archive ne contient aucun etat vivant) puis `install.sh`."""
    ASIDE = "aside"
    """omega-fire : son var/ appartient a root ; l'ancienne installation est mise de cote (`sudo mv`), la nouvelle
    extraite a sa place, et son `install.sh` reprend lui-meme l'etat de l'ancienne (README, « Mise a jour »)."""


UPDATE_MODES = {"omega-fire": UpdateMode.ASIDE}



def update_mode(tool: str) -> UpdateMode:
    return UPDATE_MODES.get(tool, UpdateMode.OVER)


@dataclass(frozen=True)
class Outdated:
    """Outil installe trop ancien : mis a jour avant toute reparation ou synchronisation."""

    tool: str
    root: str
    version: str
    minimum: str
    incomplete: bool = False
    """Version a jour mais installation inachevee (install.sh arrete : ni carte d'identite ni environnement Python
    utilisable) ; constate le 2026-11-11 sur omega-server. Reinstallee comme une mise a jour."""


def may_ask_sheet(tool: str, token_status: ReadStatus, version: str) -> bool:
    """Lancer l'outil pour lui demander sa fiche ? Seulement s'il sait repondre : il a une carte d'identite (seules
    les versions a contrats en ecrivent), ou sa version, lue dans ses fichiers, est assez recente.

    Constate le 2026-11-11 sur omega-server : un tres vieil omega-fire se relance lui-meme avec sudo ; sans
    terminal, sudo echoue sans rien demander, mais `pam_faillock` compte l'echec — trois scans, et le compte est
    verrouille 10 minutes : le vrai mot de passe tape ensuite est refuse."""
    if token_status is ReadStatus.OK:
        return True
    minimum = version_key(CONTRACT_VERSIONS.get(tool, ""))
    installed = version_key(version)
    return minimum is None or (installed is not None and installed >= minimum)


def outdated(item: DetectedInstallation) -> Outdated | None:
    """Outil trop ancien : version lue plus ancienne que sa premiere version a contrats ; ou, pour un outil a
    contrats, ni carte d'identite ni version lisible (une version a contrats a toujours les deux) ; ou ni carte ni
    fiche (regle du lot R1)."""
    minimum = minimum_version(item.tool)
    if too_old(item.tool, item.version):
        return Outdated(item.tool, item.root, item.version, minimum)
    unknown = version_key(item.version) is None and item.token_status is ReadStatus.ABSENT
    never_asked = bool(minimum) and item.sheet is None and item.tool in SHEET_TOOLS
    if unknown and (never_asked or (item.sheet is not None and item.sheet.status is ReadStatus.ABSENT)):
        return Outdated(item.tool, item.root, item.version, minimum)
    if minimum and version_key(item.version) is not None and item.token_status is ReadStatus.ABSENT \
            and item.venv_ready is False:
        return Outdated(item.tool, item.root, item.version, minimum, incomplete=True)
    return None


def outdated_roots(installations: Iterable[DetectedInstallation]) -> dict[str, Outdated]:
    return {item.root: found for item in installations if item.tool and (found := outdated(item)) is not None}
