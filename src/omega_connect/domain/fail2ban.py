# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ce qu'omega-jail a pose dans fail2ban, lu comme du texte (spec etape 3, §3.2). Aucune lecture disque ici :
l'infrastructure fournit le texte des fichiers et leurs droits, le domaine les interprete.

Fichiers d'omega-jail (projet ~/DEV/JAIL/omega-jail, render.py et install.py) :
- `jail.d/omega-jail-<jail>.conf` et `filter.d/omega-jail-<jail>.conf`, un par jail du catalogue ;
- `action.d/omega-jail-tailscale-bridge.conf` (instance principale) et
  `action.d/omega-jail-tailscale-bridge-<service>.conf` (autres instances) : le pont vers la liste noire ;
- le script du pont, `/usr/local/lib/omega-jail/omega-jail-tailscale-bridge.py`, lance par fail2ban en root."""
from __future__ import annotations

import configparser
import posixpath
import re
from dataclasses import dataclass
from enum import Enum

from omega_lib.synchro.policies import normalize_network

JAIL_FILE_PREFIX = "omega-jail-"
BRIDGE_ACTION_PREFIX = "omega-jail-tailscale-bridge"

CATALOG_FILE_KEYS: dict[str, str] = {
    "omega-waf-blocklist-sync": "magnet-blocklist-log",
    "omega-waf-magnet-alerts": "magnet-alerts-log",
    "omega-serv-waf-block": "waf-log",
    "omega-serv-active-defense": "active-defense-log",
    "omega-serv-auth-bruteforce": "access-log",
    "omega-serv-scan": "access-log",
}
"""Jail du catalogue d'omega-jail -> journal de la fiche d'omega-serv qu'il lit (`files.<cle>`)."""
RIPOSTE_JAIL = re.compile(r"^(?P<service>.+)-riposte-(?:1h|6h|24h|7d)$")
"""Jails RIPOSTE, un jeu par instance : `<service>-riposte-<duree>` (catalogue, `per_instance`)."""
RIPOSTE_FILE_KEY = "riposte-decisions"
MAGNET_FILE_KEYS = frozenset({"magnet-alerts-log", "magnet-blocklist-log"})
MAGNET_ALERTS_JAIL = "omega-waf-magnet-alerts"
"""Seul jail magnet qui bannit sur une alerte : en mode log-only, il bannit quand meme au niveau reseau."""


class Presence(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    UNKNOWN = "unknown"
    """Impossible a savoir sans root (dossier parent non lisible)."""


@dataclass(frozen=True)
class FileFacts:
    path: str
    presence: Presence
    is_file: bool = False
    owner: str = ""
    group: str = ""
    mode: int = 0
    detail: str = ""
    """Erreur technique (anglais ASCII) quand `presence` vaut UNKNOWN."""
    is_dir: bool = False
    is_symlink: bool = False

    @property
    def writable_by_group_or_others(self) -> bool:
        return bool(self.mode & 0o022)


@dataclass(frozen=True)
class ConfigText:
    facts: FileFacts
    text: str | None
    """None : fichier present mais illisible."""


@dataclass(frozen=True)
class Fail2banSnapshot:
    installed: bool
    """Le dossier de fail2ban existe."""
    readable: bool = True
    """Ses sous-dossiers jail.d / filter.d / action.d ont pu etre listes."""
    detail: str = ""
    jail_files: tuple[ConfigText, ...] = ()
    filter_files: tuple[FileFacts, ...] = ()
    action_files: tuple[ConfigText, ...] = ()


@dataclass(frozen=True)
class JailConfig:
    name: str
    source: str
    enabled: bool
    filter: str
    logpaths: tuple[str, ...]
    ignoreip: tuple[str, ...]
    """Reseaux ecrits dans le jail, normalises ; `%(known/ignoreip)s` (repris du [DEFAULT]) n'en fait pas partie."""
    actions: tuple[str, ...]
    """Actions nommees (le pont) ; `%(action_)s`, l'action par defaut de l'hote, n'en fait pas partie."""

    @property
    def file_key(self) -> str | None:
        return jail_file_key(self.name)


@dataclass(frozen=True)
class BridgeAction:
    name: str
    source: str
    script: str
    """Script lance par fail2ban (en root) a chaque ban."""
    servcli: str
    """`<racine omega-serv>/.venv/bin/omega-serv` ; vide si omega-jail ne l'a pas trouve a l'installation."""
    exempt: tuple[str, ...]

    @property
    def target_root(self) -> str:
        """Racine de l'instance omega-serv visee : trois niveaux au-dessus de `.venv/bin/omega-serv`."""
        if not self.servcli.endswith("/.venv/bin/omega-serv"):
            return ""
        return posixpath.dirname(posixpath.dirname(posixpath.dirname(self.servcli)))


def jail_file_key(name: str) -> str | None:
    if name in CATALOG_FILE_KEYS:
        return CATALOG_FILE_KEYS[name]
    return RIPOSTE_FILE_KEY if RIPOSTE_JAIL.match(name) else None


def riposte_service(name: str) -> str | None:
    match = RIPOSTE_JAIL.match(name)
    return match.group("service") if match else None


def _networks(words: list[str]) -> tuple[str, ...]:
    kept = []
    for word in words:
        if word.startswith("%("):
            continue
        kept.append(normalize_network(word) or word)
    return tuple(kept)


def parse_jail_file(source: str, text: str) -> tuple[tuple[JailConfig, ...], str]:
    """Jails d'un fichier jail.d ; deuxieme valeur : erreur de lecture (fichier abime), vide sinon."""
    parser = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",),
                                       comment_prefixes=("#", ";"))
    try:
        parser.read_string(text, source=source)
    except configparser.Error as exc:
        return (), str(exc).splitlines()[0]
    jails = []
    for name in parser.sections():
        if name == "INCLUDES":
            continue
        section = parser[name]
        try:
            enabled = section.getboolean("enabled", fallback=False)
        except ValueError:
            enabled = False
        actions = tuple(word.split("[", 1)[0] for word in section.get("action", "").split()
                        if not word.startswith("%("))
        jails.append(JailConfig(
            name=name, source=source, enabled=enabled, filter=section.get("filter", "").split("[", 1)[0].strip(),
            logpaths=tuple(section.get("logpath", "").split()),
            ignoreip=_networks(section.get("ignoreip", "").split()), actions=actions,
        ))
    return tuple(jails), ""


_ACTIONBAN = re.compile(r"^\s*actionban\s*=\s*(?P<line>.+)$", re.MULTILINE)
_QUOTED_OPTION = r'--{name}="(?P<value>[^"]*)"'


def parse_bridge_action(source: str, text: str) -> BridgeAction | None:
    """Action du pont rendue par omega-jail ; None si la ligne `actionban` manque (fichier abime ou modifie)."""
    match = _ACTIONBAN.search(text)
    if match is None:
        return None
    line = match.group("line")

    def option(name: str) -> str:
        found = re.search(_QUOTED_OPTION.format(name=name), line)
        return found.group("value") if found else ""

    script = next((word for word in line.split() if word.endswith(".py")), "")
    name = posixpath.splitext(posixpath.basename(source))[0]
    exempt = _networks([item for item in option("exempt").split(",") if item])
    return BridgeAction(name=name, source=source, script=script, servcli=option("servcli"), exempt=exempt)
