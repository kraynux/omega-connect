# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Detail de l'espace partage (ouvert depuis le Registre ; lot D, refonte R1) : ce qu'omega-connect a cree sur la
machine et quand, les applications reliees, et les retraits (« Retirer cet outil », « Tout retirer »). Lisible par
root et le groupe omega-synchro (pris tout seul au lancement) ; sinon « Lire avec sudo » (lecture seule)."""
from __future__ import annotations

import contextlib

from omega_lib.synchro.models import ReadStatus
from omega_lib.synchro.policies import parse_utc
from omega_lib.synchro.registry import LinkedInstallation, ZoneState
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_connect.application.zone_actions import ZoneTools, remove_all_plan, remove_tool_plan
from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.fail2ban import Presence
from omega_connect.domain.zone import ZoneFacts, ZonePlan, read_registry
from omega_connect.interfaces.cli.report_view import KIND_LABELS
from omega_connect.interfaces.tui.screens._base import OmegaScreen
from omega_connect.interfaces.tui.screens._zone_flow import DetectNow, ZoneFlow
from omega_connect.interfaces.tui.screens.keep_or_erase import KeepOrEraseScreen
from omega_connect.interfaces.tui.widgets.busy import Busy
from omega_connect.interfaces.tui.widgets.tables import WideTable
from omega_connect.shared.i18n import N_, _

STATE_LABELS = {ZoneState.ACTIVE: N_("active (synchronisée)"), ZoneState.FROZEN: N_("figée (plus synchronisée)")}


def local_time(text: str) -> str:
    moment = parse_utc(text)
    return moment.astimezone().strftime("%d/%m/%Y %H:%M") if moment is not None else text


class ZoneDetailScreen(OmegaScreen):
    def __init__(self, *, tools: ZoneTools, detect: DetectNow) -> None:
        super().__init__()
        self._tools = tools
        self._flow = ZoneFlow(self, tools, detect, self._after_action, self._busy)
        self._linked: tuple[LinkedInstallation, ...] = ()

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("DÉTAIL DE L'ESPACE PARTAGÉ"), classes="omega-title")
            yield Static(_("Ce qu'omega-connect a créé sur cette machine, et quand (registre de l'espace partagé "
                           "{zone}). « Tout retirer » défait exactement cette liste ; un fichier qu'elle ne connaît "
                           "pas n'est jamais supprimé.").format(zone=self._tools.inspector.zone_path),
                         classes="omega-hint")
            yield Busy(id="busy")
            yield Static("", id="registry-state")
            yield Static(_("CRÉATIONS"), classes="omega-subtitle")
            yield WideTable(id="created-table")
            yield Static(_("OUTILS RELIÉS"), classes="omega-subtitle", id="linked-title")
            yield WideTable(id="linked-table")
        with Horizontal(classes="omega-actions omega-fixed-actions"):
            with Container(classes="omega-btn-frame", id="read-sudo-frame"):
                yield Button(_("Lire avec sudo"), id="read-sudo")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retirer cet outil"), id="remove-tool", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Tout retirer…"), id="remove-all", variant="error", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        created = self.query_one("#created-table", DataTable)
        created.cursor_type = "row"
        created.add_columns(_("Type"), _("Élément"), _("Créé le"))
        linked = self.query_one("#linked-table", DataTable)
        linked.cursor_type = "row"
        linked.add_columns(_("Outil"), _("Dossier"), _("Identifiant"), _("Version"), _("Relié le"))
        self.query_one("#read-sudo-frame").display = False
        self._read(elevate=False)

    def _busy(self, text: str | None) -> None:
        with contextlib.suppress(NoMatches):
            busy = self.query_one(Busy)
            busy.show(text) if text is not None else busy.hide()

    def _read(self, *, elevate: bool) -> None:
        self.query_one("#registry-state", Static).update("")
        self._busy(_("Initialisation du registre : lecture de la zone en cours…"))
        self._flow.read_zone(self._show, elevate=elevate)

    def _show(self, facts: ZoneFacts, _authenticated: bool) -> None:
        self._busy(None)
        try:
            state = self.query_one("#registry-state", Static)
            created = self.query_one("#created-table", DataTable)
            linked = self.query_one("#linked-table", DataTable)
        except NoMatches:
            return
        created.clear()
        linked.clear()
        self._linked = ()
        result = read_registry(facts)
        unreadable = result.status is ReadStatus.UNREADABLE or not facts.listing_known
        self.query_one("#read-sudo-frame").display = unreadable and facts.root.presence is not Presence.MISSING
        self.query_one("#remove-all", Button).disabled = result.value is None
        self.query_one("#remove-tool", Button).disabled = True
        if result.value is None:
            if facts.root.presence is Presence.MISSING:
                state.update(_("Aucune zone en {zone} : rien n'a été créé (menu Synchronisation pour l'établir).")
                             .format(zone=facts.path))
            elif unreadable:
                state.update(_("Registre lisible par root et le groupe omega-synchro seulement : reconnectez-vous si "
                               "vous venez d'y être ajouté, ou « Lire avec sudo »."))
            else:
                state.update(_("Registre {status} ({detail}) : rien ne sera retiré tant qu'il n'est pas réparé.")
                             .format(status=result.status.value, detail=result.detail or "?"))
            return
        registry = result.value
        state.update(_("Zone {zone} — {state} — mise à jour le {date}.").format(
            zone=registry.zone, state=_(STATE_LABELS[registry.state]), date=local_time(registry.updated_at)))
        for item in registry.created:
            created.add_row(_(KIND_LABELS[item.kind]), item.target, local_time(item.at))
        self._linked = registry.installations
        for entry in registry.installations:
            linked.add_row(entry.instance if entry.instance != entry.tool else entry.tool, entry.root,
                           entry.installation_id[:8], entry.version, local_time(entry.linked_at))
        self.query_one("#remove-tool", Button).disabled = not self._linked
        if not self._linked:
            linked.add_row(_("aucune application reliée pour l'instant"), "", "", "", "")
        created.refresh(layout=True)
        linked.refresh(layout=True)

    def _selected(self) -> LinkedInstallation | None:
        row = self.query_one("#linked-table", DataTable).cursor_row
        return self._linked[row] if 0 <= row < len(self._linked) else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "read-sudo":
            self._read(elevate=True)
        elif button == "remove-tool":
            item = self._selected()
            if item is not None:
                identifier = item.installation_id

                def build(facts: ZoneFacts, detection: DetectionReport | None, tools: ZoneTools) -> ZonePlan:
                    assert detection is not None
                    return remove_tool_plan(facts, detection, identifier, tools.now())

                self._flow.propose(build, with_detection=True)
        elif button == "remove-all":
            self.app.push_screen(KeepOrEraseScreen(), self._remove_all)
        elif button == "back":
            self.action_back()

    def _remove_all(self, keep: bool | None) -> None:
        if keep is None:
            return

        def build(facts: ZoneFacts, detection: DetectionReport | None, tools: ZoneTools) -> ZonePlan:
            return remove_all_plan(facts, tools.now(), keep_zone=keep, detection=detection)

        # Detection : omega-serv retire lui-meme le groupe de son service avant le groupe (lot E).
        self._flow.propose(build, with_detection=not keep)

    def _after_action(self, ran: bool) -> None:
        if ran:
            self._read(elevate=True)
