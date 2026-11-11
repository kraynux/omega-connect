# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Etats du registre en couleur (couleurs du theme actif, comme les tableaux d'etat des autres outils de la suite) :
Reliee en vert, Inscrite en bleu, Detectee en orange, A corriger en rouge, Ancienne version en gris."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping

from rich.text import Text
from textual.app import App

from omega_connect.domain.fleet import AppState, RegistryRow
from omega_connect.interfaces.cli.enroll_view import STATE_LABELS, STATE_MARKS
from omega_connect.shared.i18n import _

STATE_STYLE_KEYS = {
    AppState.LINKED: "success", AppState.ENROLLED: "secondary", AppState.DETECTED: "warning",
    AppState.TO_FIX: "error", AppState.OLD_VERSION: "dim", AppState.INCOMPLETE: "warning",
    AppState.UNREACHABLE: "error",
}
SUMMARY_ORDER = (AppState.LINKED, AppState.ENROLLED, AppState.DETECTED, AppState.TO_FIX, AppState.OLD_VERSION,
                 AppState.INCOMPLETE, AppState.UNREACHABLE)


def theme_styles(app: App[object]) -> dict[str, str]:
    variables = app.get_css_variables()
    styles = {key: variables.get(key, key) for key in ("success", "secondary", "warning", "error")}
    styles["dim"] = "dim"
    return styles


def _style(state: AppState, styles: Mapping[str, str]) -> str:
    key = STATE_STYLE_KEYS[state]
    return styles.get(key, key) if key != "dim" else "dim"


def state_cell(state: AppState, styles: Mapping[str, str]) -> Text:
    return Text(f"{STATE_MARKS[state]} {_(STATE_LABELS[state])}", style=f"bold {_style(state, styles)}")


def state_summary(rows: Iterable[RegistryRow], styles: Mapping[str, str]) -> Text:
    counts = Counter(row.state for row in rows)
    summary = Text()
    for state in SUMMARY_ORDER:
        if counts[state]:
            if summary:
                summary.append("   ")
            summary.append(f"{STATE_MARKS[state]} {counts[state]} {_(STATE_LABELS[state])}",
                           style=f"bold {_style(state, styles)}")
    return summary
