# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""omega-connect. La version est lue dans pyproject.toml, seule source (procedure de verification de l'auteur,
etape B, 2026-11-22) : splash, barre de titre, rapport et « Contact et support » affichent le meme numero."""
from pathlib import Path

from omega_lib.infrastructure.declaration.app_version import project_version

__version__ = project_version(Path(__file__).resolve().parents[2], "omega-connect")
