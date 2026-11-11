# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage `verifier` (spec etape 3, §3.2) : lecture seule, sans root.

Detection (avec les fiches) -> fichiers d'omega-jail dans fail2ban -> droits des fichiers partages -> zone
neutre (lot D) -> etat de chaque lien. Rien n'est ecrit, aucune commande de correction n'est lancee, et la zone
n'est jamais relue avec sudo ici."""
from __future__ import annotations

from omega_connect.domain.detection import DetectionReport
from omega_connect.domain.links import VerificationReport, evaluate_links, paths_to_probe, read_fail2ban
from omega_connect.domain.zone_checks import zone_link
from omega_connect.ports.verification import Fail2banReader, FileProbe
from omega_connect.ports.zone import SubjectProvider, ZoneInspector


def verify_links(detection: DetectionReport, reader: Fail2banReader, probe: FileProbe,
                 zone: ZoneInspector | None = None, subject: SubjectProvider | None = None,
                 command: str = "omega-connect") -> VerificationReport:
    fail2ban = read_fail2ban(reader.read())
    facts = {path: probe.facts(path) for path in paths_to_probe(detection, fail2ban)}
    links = evaluate_links(detection, fail2ban, facts)
    if zone is not None and subject is not None:
        links = (*links, zone_link(zone.inspect(elevated=False), detection, subject.subject(), command))
    return VerificationReport(detection, links)
