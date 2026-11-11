# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fabrique de fausses installations omega dans un dossier temporaire (jamais le vrai systeme)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

LAUNCHERS = {"omega-serv": "omega-serv.sh", "omega-fire": "omega-fire.sh", "omega-jail": "omega-jail.sh"}


def make_installation(root: Path, tool: str, *, token_id: str | None = None,
                      sheet: dict | None = None, exit_code: int = 0) -> Path:
    """Dossier avec le lanceur et le paquet de l'outil ; jeton facultatif ; le lanceur imprime `sheet`."""
    (root / "src" / tool.replace("-", "_")).mkdir(parents=True, exist_ok=True)
    launcher = root / LAUNCHERS[tool]
    payload = json.dumps(sheet) if sheet is not None else "{}"
    launcher.write_text(f"#!/bin/sh\ncat <<'EOF'\n{payload}\nEOF\nexit {exit_code}\n", encoding="utf-8")
    launcher.chmod(0o755)
    if token_id is not None:
        (root / "var").mkdir(exist_ok=True)
        (root / "var" / "omega-jeton.json").write_text(json.dumps({
            "format": "omega-jeton", "schema_version": 1, "tool": tool, "version": "1.0",
            "installation_id": token_id, "machine": "m1", "root": str(root), "owner": "x",
            "installed_at": "2026-11-10T14:03:00Z", "updated_at": "2026-11-10T14:03:00Z",
            "contracts": {}, "offers": [], "wants": [],
        }), encoding="utf-8")
    return root


def sheet_for(tool: str, instance: str) -> dict:
    return {"format": "omega-fiche", "schema_version": 1, "tool": tool, "version": "1.0",
            "installation_id": "", "instance": instance, "generated_at": "2026-11-10T14:05:00Z",
            "capabilities": {"waf": "active"}, "service": None, "files": {}, "partial": False}


@pytest.fixture
def fake_system(tmp_path: Path) -> dict[str, Path]:
    """HOME, /srv, /etc/systemd/system, /etc/init.d, /etc/sv et /proc/self/mounts factices."""
    paths = {name: tmp_path / name for name in ("home", "srv", "systemd", "openrc", "runit")}
    for path in paths.values():
        path.mkdir()
    mounts = tmp_path / "mounts"
    mounts.write_text("", encoding="utf-8")
    paths["mounts"] = mounts
    return paths


@pytest.fixture(autouse=True)
def _never_real_zone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OMEGA_SYNCHRO_DIR", str(tmp_path / "zone"))
    assert os.environ["OMEGA_SYNCHRO_DIR"].startswith(str(tmp_path))
