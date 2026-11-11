# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Aide -> Contact et support : ecrans partages d'omega-lib (D-016), comme omega-check. omega-connect n'a pas de
service permanent : declaration « une seule fois »."""
from __future__ import annotations

from typing import Any

from omega_lib.interfaces.tui.contact_support import ContactSupportKit
from omega_lib.ports.declaration import ContactSupportServices
from textual.screen import Screen

from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.shared.i18n import STATE, _


def contact_support_screen(services: ContactSupportServices) -> Screen[Any]:
    kit = ContactSupportKit(services=services, translate=_, language_code=lambda: STATE.language.code,
                            base_screen=OmegaScreen)
    return kit.screen()
