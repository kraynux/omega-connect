# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Reconnaitre une installation omega a ses fichiers, sans rien executer, et la lire (jeton, proprietaire)."""
from __future__ import annotations

import os
import pwd
from pathlib import Path

from omega_lib.infrastructure.synchro.install_token import read_install_token
from omega_lib.synchro.constants import TOKEN_RELATIVE_PATH, TOOL_LAUNCHERS
from omega_lib.synchro.models import InstallToken, ReadResult

from omega_connect.domain.versions import read_version, version_file

MAX_VERSION_FILE_BYTES = 256 * 1024


def layout_tool(root: Path) -> str:
    """Outil dont le lanceur (`omega-serv.sh`...) ET le paquet (`src/omega_serv`) sont a la racine."""
    for tool, launcher in TOOL_LAUNCHERS.items():
        package = root / "src" / tool.replace("-", "_")
        try:
            if (root / launcher).is_file() and package.is_dir():
                return tool
        except OSError:
            continue
    return ""


def looks_like_installation(root: Path) -> bool:
    try:
        return (root / TOKEN_RELATIVE_PATH).is_file() or bool(layout_tool(root))
    except OSError:
        return False


def owner_name(path: Path) -> str:
    try:
        uid = path.stat().st_uid
    except OSError:
        return ""
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


class FilesystemInspector:
    def read_token(self, root: str) -> ReadResult[InstallToken]:
        return read_install_token(Path(root))

    def layout_tool(self, root: str) -> str:
        return layout_tool(Path(root))

    def owner(self, root: str) -> str:
        return owner_name(Path(root))

    def version(self, root: str, tool: str) -> str:
        return installed_version(Path(root), tool)

    def venv_ready(self, root: str) -> bool:
        venv = Path(root) / ".venv"
        try:
            return not venv.is_symlink() and (venv / "bin" / "activate").is_file() and \
                (venv / "bin" / "python").exists()
        except OSError:
            return False


def installed_version(root: Path, tool: str) -> str:
    """Lecture seule d'un fichier ordinaire de l'outil (jamais un lien), taille bornee."""
    path = root / version_file(tool)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_VERSION_FILE_BYTES:
            return ""
        return read_version(path.read_text(encoding="utf-8", errors="replace"), tool)
    except OSError:
        return ""


def real_directory(path: str | Path) -> str | None:
    """Chemin reel d'un dossier existant, sinon None."""
    try:
        resolved = Path(os.path.expanduser(str(path))).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return str(resolved) if resolved.is_dir() else None
