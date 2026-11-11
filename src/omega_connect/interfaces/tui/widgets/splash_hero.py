# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Composition ASCII de l'ecran de demarrage : logo fourni par l'auteur dans ~/DEV/CONNECT/ascii.txt (premier
modele, avec l'interrupteur), caracteres non modifies. ascii.txt n'est PAS lu au demarrage : une retouche de ce
fichier doit etre reportee ici.

Placement RECALCULE (demande de l'auteur, 2026-11-10) : les blocs sont ecrits sans retrait, et chacun est centre
sur un axe unique, le milieu du cadre CONNECT (59 colonnes, colonne 29). La ligne ou le cadre OMEGA se pose sur
le cadre CONNECT, avec le trait d'union, est calculee depuis la place du cadre OMEGA. Bloc de largeur paire
(barre de version, trait d'union, interrupteur) : la demi-colonne en trop part a gauche, pour tous les memes.

Couleurs (regles ecrites en tete d'ascii.txt) :
- cadres (« container ») : clair ($foreground) ;
- texte OMEGA-CONNECT : ligne 1 vif ($accent), ligne 2 clair, ligne 3 vif ; le trait d'union « ══ » vif ;
- « OMEGA TOOLS CONNECTOR » vif dans son cadre clair (meme patron que le reste de la suite) ;
- blocs : █ clair, ▓ moins clair, ▒ et ░ chacun une nuance en dessous. Les quatre nuances sont rendues par
  transparence du ton clair (`$foreground 75 %`...) : elles suivent donc le theme, sans couleur ecrite en dur ;
- interrupteur sur OFF : voyant « OFF » vif (allume), « ON » clair ;
- ligne du bas : « | » vifs, mots clairs.

Le texte est construit en `Content` + `Span` plutot qu'en balisage : les « \\ » de l'interrupteur ne peuvent pas
echapper une balise, et aucun espace de bord ne se deplace (piege constate chez omega-log)."""
from __future__ import annotations

from textual.content import Content, Span
from textual.widgets import Static

WIDTH = 59
"""Largeur du cadre CONNECT, le plus large : son milieu (colonne 29) est l'axe de tout le logo."""
AXIS = (WIDTH - 1) // 2
CLEAR = "$foreground"
BRIGHT = "$accent"
SHADES = {"█": CLEAR, "▄": CLEAR, "▀": CLEAR, "▓": "$foreground 75%", "▒": "$foreground 55%",
          "░": "$foreground 35%"}

TITLE_BOX = (
    "┌───────────────────────┐",
    "│ OMEGA TOOLS CONNECTOR │",
    "└───────────────────────┘",
)
OMEGA_BOX = (
    "┌─────────────────────────────────────────┐",
    "│ ┌╦═══╦┐ ┌╦═╦═╦┐ ┌╦═══╦┐ ┌╦═══╦┐ ┌╦═══╦┐ │",
    "│ │║   ║│ │║ ║ ║│ ├╬══    │║  ═╦┐ ├╬═══╬┤ │",
    "│ └╩═══╩┘ └╩   ╩┘ └╩═══╩┘ └╩═══╩┘ └╩   ╩┘ │",
)
CONNECT_BOX = (
    "│ ┌╦═══╦┐ ┌╦═══╦┐ ┌╦═╗ ╦┐ ┌╦═╗ ╦┐ ┌╦═══╦┐ ┌╦═══╦┐ ┌═╤╦╤═┐ │",
    "│ │║      │║   ║│ │║ ║ ║│ │║ ║ ║│ ├╬══    │║        │║│   │",
    "│ └╩═══╩┘ └╩═══╩┘ └╩ ╚═╩┘ └╩ ╚═╩┘ └╩═══╩┘ └╩═══╩┘   ╧╩╧   │",
    "└─────────────────────────────────────────────────────────┘",
)
HYPHEN = "══"
WORDMARK_ROWS = {1: BRIGHT, 2: CLEAR, 3: BRIGHT, 5: BRIGHT, 6: CLEAR, 7: BRIGHT}
"""Ligne du logo -> couleur du texte qu'elle porte (le cadre « │ » de bord reste clair)."""
HYPHEN_ROW = 4
SWITCH_BOX_COLUMN = 13
"""Colonne du bord gauche de l'interrupteur dans les lignes ci-dessous (les noms d'outils le precedent)."""
SWITCH = (
    "             ┌▄▄▄▄▄▄▄▄▄▄┐",
    "             │████ON████│",
    "             │██┌────┐██│",
    "OMEGA-SERV───│██│┌──┐│██│───OMEGA-FIRE",
    "             │██││  ││██│",
    "OMEGA-JAIL───│██││__││██│────OMEGA-WAF",
    "             │██││\\ \\│██│",
    "OMEGA-STRESS─│██│\\ \\_\\██│────OMEGA-LOG",
    "             │██└─\\│_│██│",
    "             │██████████│",
    "             │████OFF███│",
    "             └▀▀▀▀▀▀▀▀▀▀┘",
)
SWITCH_WIDTH = 12
TAGLINE = "SYNCHRONISATION | RULES | PERMISSION | TOOLS | NETWORKS"


def start_on_axis(width: int) -> int:
    """Colonne de depart d'un bloc de `width` colonnes centre sur l'axe. Largeur paire : le demi-colonne en
    trop part a gauche (meme regle pour tous les blocs pairs : barre de version, trait d'union, interrupteur)."""
    return AXIS - width // 2


def on_axis(text: str) -> str:
    return " " * start_on_axis(len(text)) + text


def version_bar(version: str) -> str:
    """« █▓▒░V0.1.0░▒▓█ » : version lue dans pyproject.toml (seule source), centree sur l'axe des cadres."""
    return on_axis(f"█▓▒░V{version}░▒▓█")


def junction_line() -> str:
    """Ligne ou le cadre OMEGA se pose sur le cadre CONNECT, trait d'union au milieu : calculee depuis la place
    du cadre OMEGA, jamais ecrite a la main."""
    left = start_on_axis(len(OMEGA_BOX[0]))
    right = left + len(OMEGA_BOX[0]) - 1
    cells = [" "] * WIDTH
    cells[0], cells[WIDTH - 1] = "┌", "┐"
    for column in (*range(1, left), *range(right + 1, WIDTH - 1)):
        cells[column] = "─"
    cells[left], cells[right] = "┘", "└"
    hyphen = start_on_axis(len(HYPHEN))
    cells[hyphen:hyphen + len(HYPHEN)] = HYPHEN
    return "".join(cells)


def logo_lines() -> tuple[str, ...]:
    return (*(on_axis(line) for line in OMEGA_BOX), junction_line(), *CONNECT_BOX)


def switch_lines() -> tuple[str, ...]:
    shift = start_on_axis(SWITCH_WIDTH) - SWITCH_BOX_COLUMN
    return tuple(" " * shift + line for line in SWITCH)


class _Builder:
    def __init__(self) -> None:
        self.text: list[str] = []
        self.spans: list[Span] = []
        self.offset = 0

    def line(self, text: str, style_of: dict[int, str]) -> None:
        """Ajoute une ligne ; `style_of` : position -> style (les espaces ne sont jamais colores)."""
        start = None
        current = ""
        for index, char in enumerate([*text, "\0"]):
            style = style_of.get(index, "") if char not in (" ", "\0") else ""
            if style != current:
                if current and start is not None:
                    self.spans.append(Span(self.offset + start, self.offset + index, current))
                start, current = index, style
        self.text.append(text)
        self.offset += len(text) + 1

    def content(self) -> Content:
        return Content("\n".join(self.text), self.spans)


def _plain(text: str, color: str = CLEAR) -> dict[int, str]:
    return {index: SHADES.get(char, color) for index, char in enumerate(text)}


def _framed(text: str, inner: str) -> dict[int, str]:
    """Cadre clair aux deux bords, texte interieur dans la couleur `inner`."""
    styles = _plain(text)
    first, last = text.index("│"), text.rindex("│")
    styles.update({index: inner for index in range(first + 1, last)})
    return styles


def _logo_row(row: int, text: str) -> dict[int, str]:
    if row in WORDMARK_ROWS:
        return _framed(text, WORDMARK_ROWS[row])
    styles = _plain(text)
    if row == HYPHEN_ROW:
        start = text.index("══")
        styles.update({start: BRIGHT, start + 1: BRIGHT})
    return styles


def _switch_row(text: str) -> dict[int, str]:
    """L'interrupteur est sur OFF : c'est le voyant OFF qui est allume (vif), ON reste clair."""
    styles = _plain(text)
    position = text.find("OFF")
    if position >= 0:
        styles.update({position + offset: BRIGHT for offset in range(3)})
    return styles


def _tagline(text: str) -> dict[int, str]:
    return {index: BRIGHT if char == "|" else CLEAR for index, char in enumerate(text)}


def splash_content(version: str) -> Content:
    builder = _Builder()
    title = [on_axis(line) for line in TITLE_BOX]
    builder.line(title[0], _plain(title[0]))
    builder.line(title[1], _framed(title[1], BRIGHT))
    builder.line(title[2], _plain(title[2]))
    bar = version_bar(version)
    builder.line(bar, _plain(bar))
    for row, text in enumerate(logo_lines()):
        builder.line(text, _logo_row(row, text))
    for text in switch_lines():
        builder.line(text, _switch_row(text))
    builder.line("", {})
    tagline = on_axis(TAGLINE)
    builder.line(tagline, _tagline(tagline))
    return builder.content()


class SplashHero(Static):
    def __init__(self, version: str) -> None:
        super().__init__(splash_content(version), classes="omega-splash-hero")
