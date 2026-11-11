# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Archives des outils prises sur les Releases GitHub (lot R3 ; decision de l'auteur, ETUDE_REFONTE §16).

- derniere version : `https://github.com/kraynux/<outil>/releases/latest` redirige vers `.../tag/v<version>` ; la
  redirection est lue sans la suivre (rien d'autre n'est telecharge) ;
- archive et `sha.txt` : pieces jointes de la Release `v<version>` ; l'archive est telechargee dans un dossier prive
  (0700), taille bornee, et son empreinte comparee a celle de `sha.txt` AVANT d'etre gardee ;
- HTTPS seulement, certificat verifie (contexte par defaut), delai borne ; aucune donnee de la personne n'est
  envoyee (nom de client generique)."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from omega_connect.domain.updates import ReleaseArchive, ReleaseFailure
from omega_connect.domain.versions import (
    MAX_ARCHIVE_BYTES,
    SHA_FILE,
    archive_name,
    asset_url,
    expected_sha,
    latest_url,
    version_from_tag_url,
)

USER_AGENT = "omega-connect"
TIMEOUT_SECONDS = 30
MAX_SHA_BYTES = 256 * 1024
CHUNK = 256 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _request(url: str) -> urllib.request.Request:
    if not url.startswith("https://"):
        raise ValueError(url)
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 - https seulement


class GithubReleases:
    def __init__(self, *, timeout: float = TIMEOUT_SECONDS, directory: Path | None = None) -> None:
        self._timeout = timeout
        self._directory = directory

    def latest(self, tool: str) -> str | ReleaseFailure:
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(_request(latest_url(tool)), timeout=self._timeout) as answer:
                location = answer.geturl()
        except urllib.error.HTTPError as error:
            if error.code in (301, 302, 303, 307, 308):
                location = error.headers.get("Location", "")
            elif error.code == 404:
                return ReleaseFailure.NO_RELEASE
            else:
                return ReleaseFailure.NETWORK
        except (urllib.error.URLError, OSError, ValueError):
            return ReleaseFailure.NETWORK
        version = version_from_tag_url(location or "")
        return version or ReleaseFailure.NO_RELEASE

    def _get(self, url: str, limit: int) -> bytes | ReleaseFailure:
        try:
            with urllib.request.urlopen(_request(url), timeout=self._timeout) as answer:  # noqa: S310
                data = answer.read(limit + 1)
        except urllib.error.HTTPError as error:
            return ReleaseFailure.NO_RELEASE if error.code == 404 else ReleaseFailure.NETWORK
        except (urllib.error.URLError, OSError, ValueError):
            return ReleaseFailure.NETWORK
        return ReleaseFailure.TOO_LARGE if len(data) > limit else data

    def fetch(self, tool: str, version: str) -> ReleaseArchive | ReleaseFailure:
        name = archive_name(tool, version)
        sha_list = self._get(asset_url(tool, version, SHA_FILE), MAX_SHA_BYTES)
        if isinstance(sha_list, ReleaseFailure):
            return sha_list
        expected = expected_sha(sha_list.decode("utf-8", errors="replace"), name)
        if not expected:
            return ReleaseFailure.NO_SHA
        directory = Path(tempfile.mkdtemp(prefix="omega-connect-maj-", dir=self._directory))
        result = self._download(tool, version, name, expected, directory)
        if isinstance(result, ReleaseFailure):
            shutil.rmtree(directory, ignore_errors=True)  # jamais un dossier vide laisse derriere
        return result

    def _download(self, tool: str, version: str, name: str, expected: str,
                  directory: Path) -> ReleaseArchive | ReleaseFailure:
        target = directory / name
        digest = hashlib.sha256()
        size = 0
        try:
            with urllib.request.urlopen(_request(asset_url(tool, version, name)),  # noqa: S310
                                        timeout=self._timeout) as answer, \
                    open(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
                while chunk := answer.read(CHUNK):
                    size += len(chunk)
                    if size > MAX_ARCHIVE_BYTES:
                        target.unlink(missing_ok=True)
                        return ReleaseFailure.TOO_LARGE
                    digest.update(chunk)
                    handle.write(chunk)
        except urllib.error.HTTPError as error:
            target.unlink(missing_ok=True)
            return ReleaseFailure.NO_RELEASE if error.code == 404 else ReleaseFailure.NETWORK
        except (urllib.error.URLError, OSError, ValueError):
            target.unlink(missing_ok=True)
            return ReleaseFailure.NETWORK
        if digest.hexdigest() != expected:
            target.unlink(missing_ok=True)
            return ReleaseFailure.BAD_SHA
        return ReleaseArchive(tool, version, str(target), expected)
