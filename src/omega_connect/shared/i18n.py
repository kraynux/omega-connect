# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Traduction de l'interface - seul point d'acces aux phrases traduites d'omega-connect (meme interface
que omega_stress/shared/i18n.py).

    from omega_connect.shared.i18n import _, N_, ngettext

Le francais est la langue de reference (decision de l'auteur, etape 3 Q8) : les 16 autres langues
arrivent au lot F. Catalogues : locale/<langue>/LC_MESSAGES/omega-connect.mo, chaines au catalogue
partage omega-lib."""
from __future__ import annotations

from pathlib import Path

from omega_lib.i18n.service import mark
from omega_lib.i18n.translator import ToolTranslator
from omega_lib.infrastructure.i18n.tool_language import ToolLanguage

DOMAIN = "omega-connect"
TRANSLATOR = ToolTranslator(DOMAIN)
STATE = TRANSLATOR.state
LANGUAGE = ToolLanguage(TRANSLATOR, Path(__file__).resolve().parents[1] / "locale", "OMEGA_CONNECT_LANG")

N_ = mark
lazy = TRANSLATOR.lazy


def _(message: str) -> str:
    return TRANSLATOR.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    return TRANSLATOR.ngettext(singular, plural, n)
