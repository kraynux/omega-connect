# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Parcours commun des actions de zone dans l'interface (Synchronisation, Registre) :
lire la zone (fil) -> si la session ne peut pas la lire, sudo sur le vrai terminal puis relecture -> plan ->
ecran du plan (commandes affichees, accord, execution)."""
from __future__ import annotations

from collections.abc import Callable

from textual.screen import Screen

from omega_connect.application.zone_actions import ZoneTools, needs_elevation
from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.zone import ZoneFacts, ZonePlan
from omega_connect.interfaces.tui.screens._base import SUDO_MESSAGE, suspended
from omega_connect.interfaces.tui.screens.zone_plan import ZonePlanScreen
from omega_connect.shared.i18n import _

DetectNow = Callable[[], DetectionReport]
PlanBuilder = Callable[[ZoneFacts, DetectionReport | None, ZoneTools], ZonePlan]
BusyCallback = Callable[[str | None], None]
"""Affiche (texte) ou cache (None) l'indicateur d'attente de l'ecran."""


class ZoneFlow:
    def __init__(self, screen: Screen[None], tools: ZoneTools, detect: DetectNow,
                 on_done: Callable[[bool], None], busy: BusyCallback | None = None) -> None:
        self._screen = screen
        self._busy = busy or (lambda _text: None)
        self._tools = tools
        self._detect = detect
        self._on_done = on_done

    def read_zone(self, then: Callable[[ZoneFacts, bool], None], *, elevate: bool) -> None:
        """Lit la zone dans un fil ; `then(facts, authenticated)` dans le fil de l'interface."""
        app = self._screen.app
        tools = self._tools

        def first() -> None:
            facts = tools.inspector.inspect(elevated=False)
            app.call_from_thread(after_first, facts)

        def after_first(facts: ZoneFacts) -> None:
            if not (elevate and needs_elevation(facts)):
                then(facts, False)
                return
            subject = tools.subject.subject()
            if subject.user and subject.user in facts.group_members:
                # Membre, mais ce processus a ete lance sans le groupe (avant « Etablir », ou pas par
                # omega-connect.sh, qui le prend tout seul) : le dire, plutot que d'envoyer se reconnecter.
                app.notify(_("Vous êtes membre du groupe omega-synchro, mais cet omega-connect a été lancé sans lui. "
                             "Quittez (q) et relancez ./omega-connect.sh : il le prendra tout seul, sans mot de "
                             "passe. Pour cette fois, lecture avec sudo (mot de passe dans le terminal)."),
                           timeout=12)
            else:
                app.notify(_("Votre session n'a pas encore le groupe omega-synchro : la zone est lue avec sudo, mot "
                             "de passe demandé dans le terminal."))
            self._busy(None)
            with suspended(app, SUDO_MESSAGE):
                authenticated = tools.runner.authenticate()
            if not authenticated:
                app.notify(_("Authentification sudo refusée ou annulée : rien n'est fait."), severity="error")
                then(facts, False)
                return
            self._busy(_("Lecture de la zone avec sudo…"))
            self._screen.run_worker(lambda: app.call_from_thread(then, tools.inspector.inspect(elevated=True), True),
                                    thread=True, group="zone-read", exclusive=True)

        self._screen.run_worker(first, thread=True, group="zone-read", exclusive=True)

    def propose(self, build: PlanBuilder, *, with_detection: bool) -> None:
        app = self._screen.app
        tools = self._tools

        def with_facts(facts: ZoneFacts, authenticated: bool) -> None:
            if not with_detection:
                show(facts, None, authenticated)
                return
            self._screen.run_worker(
                lambda: app.call_from_thread(show, facts, self._detect(), authenticated),
                thread=True, group="zone-detect", exclusive=True)

        def show(facts: ZoneFacts, detection: DetectionReport | None, authenticated: bool) -> None:
            self._busy(None)
            plan = build(facts, detection, tools)
            app.push_screen(ZonePlanScreen(plan=plan, facts=facts, tools=tools, authenticated=authenticated),
                            lambda ran: self._on_done(bool(ran)))

        self._busy(_("Préparation des commandes (détection des outils, lecture de la zone)…"))
        self.read_zone(with_facts, elevate=True)
