# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage `detecter` (spec etape 3, §3.1) : lecture seule, sans root.

Candidats de toutes les sources -> une entree par racine -> jeton lu -> outil reconnu -> fiche demandee
a l'outil (omega-serv, omega-fire) -> identifiants en double signales. Jamais d'exception pour une
installation illisible : elle apparait avec son etat."""
from __future__ import annotations

from collections.abc import Sequence

from omega_connect.core.constants import SHEET_TOOLS
from omega_connect.domain.detection import (
    DetectedInstallation,
    DetectionReport,
    find_duplicate_ids,
    merge_candidates,
    tool_for,
)
from omega_connect.domain.versions import CONTRACT_VERSIONS, may_ask_sheet
from omega_connect.ports.detection import CandidateLocator, InstallationInspector, SheetFetcher


def detect_installations(
    home: str,
    locators: Sequence[CandidateLocator],
    inspector: InstallationInspector,
    sheet_fetcher: SheetFetcher | None,
) -> DetectionReport:
    candidates = [candidate for locator in locators for candidate in locator.candidates()]
    notes = tuple(note for locator in locators for note in locator.notes())
    installations = []
    for merged in merge_candidates(candidates):
        token_result = inspector.read_token(merged.root)
        token = token_result.value if token_result.ok else None
        tool = tool_for(token, inspector.layout_tool(merged.root), merged.tool_hint)
        version = inspector.version(merged.root, tool) if tool else ""
        sheet = None
        if sheet_fetcher is not None and tool in SHEET_TOOLS and may_ask_sheet(tool, token_result.status, version):
            sheet = sheet_fetcher.fetch(merged.root, tool)
        installations.append(DetectedInstallation(
            root=merged.root, tool=tool, sources=merged.sources, owner=inspector.owner(merged.root),
            token_status=token_result.status, token=token, token_detail=token_result.detail, sheet=sheet,
            service_names=merged.service_names, version=version,
            venv_ready=inspector.venv_ready(merged.root) if tool in CONTRACT_VERSIONS else None,
        ))
    installations.sort(key=lambda item: (item.tool or "~", item.root))
    return DetectionReport(home=home, installations=tuple(installations),
                           duplicates=find_duplicate_ids(installations), scan_notes=notes)
