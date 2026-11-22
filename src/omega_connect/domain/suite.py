# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""omega-suite (decision de l'auteur, 2026-11-22) : omega-stress fait partie d'omega-suite.

omega-suite embarque ses outils dans `<suite>/vendor/<outil>/` et les installe dans SON environnement Python (mode
modifiable : le code de `vendor/` est celui qui tourne). Une copie embarquee :
- est reconnue comme telle (« fait partie d'omega-suite <version> »), jamais comme une installation inachevee
  (elle n'a ni `.venv` ni carte d'identite a elle : ceux de la suite comptent) ;
- se met a jour AVEC omega-suite (son archive apporte les outils qui vont avec, testes ensemble), jamais seule ;
- sert a la charge distribuee comme un omega-stress autonome (son lanceur prend le `.venv` et le `var/stress` de la
  suite), l'omega-stress autonome restant prefere s'il y en a un sur la machine."""
from __future__ import annotations

from pathlib import PurePosixPath

SUITE_TOOL = "omega-suite"
SUITE_LAUNCHER = "omega-suite.sh"
SUITE_PACKAGE = "src/omega_suite"
EMBEDDED_DIRECTORY = "vendor"


def suite_candidate(root: str) -> str:
    """Dossier d'omega-suite si `root` est de la forme `<suite>/vendor/<outil>` (a confirmer sur le disque :
    lanceur et paquet de la suite presents) ; vide sinon."""
    path = PurePosixPath(root)
    if len(path.parts) >= 3 and path.parent.name == EMBEDDED_DIRECTORY:
        return str(path.parent.parent)
    return ""
