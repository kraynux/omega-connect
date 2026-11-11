# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Reglages (lot F ; demande de l'auteur, 2026-11-11) : theme de l'interface et des exports, dossiers des exports et
des captures d'ecran (par defaut `var/exports/` et `var/screenshots/` du dossier du projet, comme les autres outils),
purge de ces deux dossiers. Meme regle de purge que le reste de la suite (correctif 2026-10-27) : le dossier
CONFIGURE, son contenu seulement, jamais un lien suivi, jamais un dossier systeme, personnel, ou le projet lui-meme,
jamais sudo."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from omega_lib.ports.settings_store import SettingsStore
from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, DEFAULT_TUI_THEME, EXPORT_PALETTES, TUI_THEMES

KEY_THEME = "theme"
KEY_EXPORT_THEME = "export_theme"
KEY_EXPORTS_DIR = "exports_dir_override"
KEY_SCREENSHOTS_DIR = "screenshots_dir_override"


class UnsafeDirectoryError(Exception):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path} : {reason}")
        self.path = path
        self.reason = reason


@dataclass(frozen=True)
class ClearResult:
    directory: Path
    removed: int
    failed: tuple[str, ...]


@dataclass(frozen=True)
class SettingsTools:
    store: SettingsStore
    default_exports: Path
    default_screenshots: Path
    clear: Callable[[Path], ClearResult]
    """Vide un dossier (garde-fous ; leve UnsafeDirectoryError) ; a appeler hors du fil de l'interface."""
    root: Path | None = None
    """Dossier d'omega-connect : un chemin sous ce dossier s'affiche et s'ecrit relatif (`var/exports/`), jamais
    le chemin complet de la machine ou il est installe (retour utilisateur 2026-11-11)."""

    def _resolve(self, value: str) -> Path:
        path = Path(value).expanduser()
        return self.root / path if self.root is not None and not path.is_absolute() else path

    def _directory(self, key: str, default: Path) -> Path:
        value = (self.store.get(key) or "").strip()
        return self._resolve(value) if value else default

    def shown(self, path: Path) -> str:
        """`var/exports/` pour un dossier sous celui d'omega-connect ; le chemin complet sinon."""
        if self.root is not None:
            try:
                return f"{path.relative_to(self.root).as_posix()}/"
            except ValueError:
                pass
        return str(path)

    def exports_dir(self) -> Path:
        return self._directory(KEY_EXPORTS_DIR, self.default_exports)

    def screenshots_dir(self) -> Path:
        return self._directory(KEY_SCREENSHOTS_DIR, self.default_screenshots)

    def theme(self) -> str:
        value = self.store.get(KEY_THEME) or ""
        return value if value in TUI_THEMES else DEFAULT_TUI_THEME

    def export_theme(self) -> str:
        value = self.store.get(KEY_EXPORT_THEME) or ""
        return value if value in EXPORT_PALETTES else DEFAULT_EXPORT_THEME

    def set_directory(self, key: str, text: str) -> Path | None:
        """Enregistre un dossier (vide : celui par defaut). Un chemin relatif part du dossier d'omega-connect et
        reste enregistre relatif ; None si le chemin est relatif sans dossier d'omega-connect connu."""
        value = text.strip()
        if not value:
            self.store.set(key, "")
            return self.exports_dir() if key == KEY_EXPORTS_DIR else self.screenshots_dir()
        path = self._resolve(value)
        if not path.is_absolute():
            return None
        default = self.default_exports if key == KEY_EXPORTS_DIR else self.default_screenshots
        if path == default:
            self.store.set(key, "")
            return path
        self.store.set(key, self.shown(path).rstrip("/"))
        return path
