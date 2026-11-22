# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lance le programme de mise a jour sur CETTE machine (Updater, 2026-11-22), dans le terminal : la personne voit
tout et tape elle-meme le mot de passe que demandent les `install.sh`."""
from __future__ import annotations

import subprocess
from collections.abc import Sequence


def run_in_terminal(argv: Sequence[str]) -> int:
    try:
        return subprocess.run(list(argv), check=False).returncode  # noqa: S603 - notre propre programme
    except OSError:
        return 127
