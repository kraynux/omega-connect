# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Aide exportee en HTML (une page autonome, theme d'export d'omega-lib, meme cadre que le rapport)."""
from __future__ import annotations

import html
import re

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES

from omega_connect.interfaces.cli.report_view import _style
from omega_connect.interfaces.tui.help_content import QUICKSTART, SECTIONS, SHORTCUTS
from omega_connect.shared.i18n import _

_BOLD = re.compile(r"\[b\](.*?)\[/b\]", re.DOTALL)


def _paragraphs(text: str) -> str:
    """Texte de l'aide -> HTML : [b] en gras, lignes « - » en liste, le reste en paragraphes."""
    blocks = []
    items: list[str] = []
    for line in text.split("\n"):
        escaped = _BOLD.sub(r"<strong>\1</strong>", html.escape(line, quote=False))
        if line.startswith("- "):
            items.append(f"<li>{escaped[2:]}</li>")
            continue
        if items:
            blocks.append('<ul class="note-list">' + "".join(items) + "</ul>")
            items = []
        if line.strip():
            blocks.append(f"<p>{escaped}</p>")
    if items:
        blocks.append('<ul class="note-list">' + "".join(items) + "</ul>")
    return "\n".join(blocks)


def help_text() -> str:
    """Toute l'aide en texte (ligne de commande, tests)."""
    lines = [_("DÉMARRAGE RAPIDE"), _BOLD.sub(r"\1", _(QUICKSTART)), "", _("RACCOURCIS")]
    lines += [f"  {_(key):<16} {_(what)}" for key, what in SHORTCUTS]
    for title, body in SECTIONS:
        lines += ["", _(title).upper(), _BOLD.sub(r"\1", _(body))]
    return "\n".join(lines) + "\n"


def render_help_html(version: str, theme: str = DEFAULT_EXPORT_THEME) -> str:
    theme = theme if theme in EXPORT_PALETTES else DEFAULT_EXPORT_THEME
    rows = "".join(f"<tr><td>{html.escape(_(key))}</td><td>{html.escape(_(what))}</td></tr>"
                   for key, what in SHORTCUTS)
    body = [f'<h1>{html.escape(_("Aide d’omega-connect"))}<span class="cursor"></span></h1>',
            f'<div class="note-historique"><span class="note-prefix">[OMEGA-CONNECT {html.escape(version)}]</span>'
            f" {html.escape(_('Aide complète : chaque menu, sa fonction et le détail.'))}</div>",
            f"<h2>{html.escape(_('Démarrage rapide'))}</h2>", _paragraphs(_(QUICKSTART)),
            f"<h2>{html.escape(_('Raccourcis'))}</h2>",
            f'<div class="table-wrapper"><table><thead><tr><th>{html.escape(_("Touche"))}</th>'
            f"<th>{html.escape(_('Action'))}</th></tr></thead><tbody>{rows}</tbody></table></div>"]
    for title, text in SECTIONS:
        body.append(f"<h2>{html.escape(_(title))}</h2>")
        body.append(_paragraphs(_(text)))
    footer = _("OMEGA-CONNECT {version} — aide.").format(version=version)
    body.append(f'<div class="footer-note">{html.escape(footer)}</div>')
    css = _style(f"palette_{theme}.css") + "\n" + _style("base.css")
    return ('<!DOCTYPE html>\n<html lang="fr" dir="ltr">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"<title>{html.escape(_('Aide - Omega-Connect'))}</title>\n<style>\n{css}\nh2 {{ margin-top: 1.6rem; }}\n"
            "p { margin: 0.4rem 0; }\n</style>\n</head>\n<body>\n"
            '<div class="container"><div class="terminal-header"><div class="terminal-dots">'
            '<span class="dot dot-close"></span><span class="dot dot-min"></span><span class="dot dot-max"></span>'
            '</div><span class="terminal-title">omega-connect -- aide</span></div>\n'
            '<div class="terminal-body">\n' + "\n".join(body) + "\n</div></div>\n</body>\n</html>\n")
