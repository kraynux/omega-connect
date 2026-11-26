# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Bandeau de scan (decision 2026-11-26, etude ETUDE_PARCOURS_SCAN_REPARER) : le meme en haut de chaque ecran qui
montre le parc.

- Avant le premier scan : etat vide, le scan est propose (« Scanner tout le parc »), jamais lance tout seul.
- Pendant un scan : « Scan : 23/50 machines — craftdark, omega-server… » et « Arreter le scan ». On peut naviguer :
  le scan tourne en arriere-plan, et l'ecran se remet a jour a chaque machine terminee (`scan_changed()` de l'ecran,
  s'il existe).
- Ensuite : l'heure du scan de cette machine et l'age du plus ancien scan du reseau, signale « ancien » au-dela de
  24 h (decision 2026-11-26 : affiche attenue, jamais rescanne tout seul).

Menu principal (`boxed=True`, demande 2026-11-26 : « pas en mode sauvage sur une ligne la totalite de l'ecran ») :
un cadre « États du scan » sous les deux colonnes, de la meme largeur, texte centre ; le bouton encadre et centre,
le meme que ceux des colonnes du menu."""
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Container
from textual.css.query import NoMatches
from textual.widgets import Button, Static

from omega_connect.interfaces.tui.widgets.states import theme_styles
from omega_connect.shared.i18n import _

OLD_SCAN = timedelta(hours=24)
POLL_SECONDS = 0.5


def parse_moment(text: str) -> datetime | None:
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def age_text(moment: datetime, now: datetime) -> str:
    seconds = max(0, int((now - moment).total_seconds()))
    if seconds < 60:
        return _("à l'instant")
    if seconds < 3600:
        return _("il y a {count} min").format(count=seconds // 60)
    if seconds < 86400:
        return _("il y a {count} h").format(count=seconds // 3600)
    return _("il y a {count} j").format(count=seconds // 86400)


def scan_age(text: str, styles: dict[str, str], now: datetime | None = None) -> Text:
    """Cellule « Dernier scan » d'un tableau : age, attenue et marque « ancien » au-dela de 24 h."""
    moment = parse_moment(text)
    if moment is None:
        return Text(_("jamais"), style="dim")
    now = now or datetime.now(timezone.utc)
    if now - moment > OLD_SCAN:
        return Text(f"{age_text(moment, now)} · {_('ancien')}", style=f"dim {styles.get('warning', 'yellow')}")
    return Text(age_text(moment, now))


class ScanBanner(Container):
    DEFAULT_CLASSES = "omega-scan-banner"

    def __init__(self, *, boxed: bool = False) -> None:
        super().__init__(classes="omega-scan-banner " + ("omega-scan-box" if boxed else "omega-scan-line"))
        self._boxed = boxed
        self._generation = -1
        self._running = False
        if boxed:
            self.border_title = _("États du scan")

    def compose(self) -> ComposeResult:
        yield Static("", classes="omega-scan-text")
        if not self._boxed:
            yield Button(_("Scanner tout le parc"), id="scan-all", variant="primary", compact=True)
            yield Button(_("Arrêter le scan"), id="scan-stop", variant="warning", compact=True)
            return
        with Center(classes="omega-scan-buttons"):  # meme bouton que ceux des colonnes du menu (majuscules, cadre)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Scanner tout le parc").upper(), id="scan-all")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Arrêter le scan").upper(), id="scan-stop")

    def on_mount(self) -> None:
        if getattr(self.app, "scans", None) is None:  # ecran monte hors de l'application (tests)
            self.display = False
            return
        self._tick()
        self.set_interval(POLL_SECONDS, self._tick)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan-all":
            event.stop()
            count = self.app.scan_everything()  # type: ignore[attr-defined]
            if not count:
                self.app.notify(_("Un scan est déjà en cours."), severity="information")
            self._tick()
        elif event.button.id == "scan-stop":
            event.stop()
            self.app.stop_scan()  # type: ignore[attr-defined]
            self._tick()

    def _tick(self) -> None:
        scans = getattr(self.app, "scans", None)
        if scans is None:
            return
        progress = scans.progress()
        with contextlib.suppress(NoMatches):
            self.query_one(".omega-scan-text", Static).update(self._text(progress))
            for button, shown in (("#scan-stop", progress.running), ("#scan-all", not progress.running)):
                widget = self.query_one(button)
                (widget.parent if self._boxed else widget).display = shown  # cadre compris : jamais de cadre vide
        if progress.generation != self._generation:
            first = self._generation < 0
            self._generation = progress.generation
            changed = getattr(self.screen, "scan_changed", None)
            if not first and callable(changed):
                changed()  # une machine vient d'etre scannee : l'ecran se remet a jour, sans rien rescanner
        if self._running and not progress.running and not progress.stopped:
            self.app.notify(_("Scan terminé : {count} machine(s).").format(count=progress.done), title=_("Scan"))
        self._running = progress.running

    def _text(self, progress: object) -> Text:
        styles = theme_styles(self.app)
        text = Text()
        if progress.running:  # type: ignore[attr-defined]
            current = ", ".join(progress.current[:3])  # type: ignore[attr-defined]
            text.append("⟳ ", style=f"bold {styles.get('accent', 'cyan')}")
            text.append(_("Scan en cours : {done}/{total} machine(s)").format(
                done=progress.done, total=progress.total), style="bold")  # type: ignore[attr-defined]
            if current:
                text.append(f" — {current}…", style="dim")
            return text
        if progress.stopped:  # type: ignore[attr-defined]
            text.append(_("Scan arrêté : {done}/{total} machine(s) scannée(s) ; les autres gardent leur dernier "
                          "scan.").format(done=progress.done, total=progress.total),  # type: ignore[attr-defined]
                        style=f"bold {styles.get('warning', 'yellow')}")
            return text
        local = getattr(self.app, "local_scanned_at", lambda: None)()
        network = getattr(self.app, "network_scanned_at", lambda: ())()
        if local is None and not network:
            # dans le cadre du menu principal, le bouton est juste dessous : une ligne suffit (le menu tient
            # en 44 lignes de terminal sans defiler)
            message = _("Pas encore de scan depuis le lancement.") if self._boxed else _(
                "Pas encore de scan depuis le lancement : « Scanner tout le parc » pour remplir les listes.")
            text.append(message, style=f"bold {styles.get('warning', 'yellow')}")
            return text
        now = datetime.now(timezone.utc)
        if local is None:
            text.append(_("Cette machine : pas encore scannée."), style=f"bold {styles.get('warning', 'yellow')}")
        else:
            text.append(_("Cette machine scannée {age}.").format(age=age_text(local, now)))
        if network:
            oldest = min(network)
            text.append("  ·  ")
            text.append(_("Réseau : {count} machine(s), plus ancien scan {age}").format(
                count=len(network), age=age_text(oldest, now)))
            if now - oldest > OLD_SCAN:
                text.append(f" ({_('ancien')})", style=f"bold {styles.get('warning', 'yellow')}")
            text.append(".")
        return text
