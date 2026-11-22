# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Archives publiees sur le SITE de l'outil (Updater, 2026-11-22 ; decision de l'auteur : « GitHub, puis le
site ») : dossier `download/` (STRUCTURE_PUBLICATION_OMEGA.md), liste `sha.txt` ; meme telechargement, memes
limites et meme verification d'empreinte que les Releases GitHub. Seule une version publiee sur le site est
proposee (jamais une archive de travail)."""
from __future__ import annotations

from omega_lib.declaration.models import SITE_URL
from omega_lib.declaration.policies import download_base_url, published_versions, sha_list_url

from omega_connect.domain.updates import ReleaseFailure
from omega_connect.infrastructure.updates.github_releases import MAX_SHA_BYTES, GithubReleases


class SiteReleases(GithubReleases):
    """Un site (kraynux, ou craftdark : meme structure `<outil>/download/`)."""

    def __init__(self, site: str = SITE_URL, label: str = "kraynux", **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._site = site
        self.label = label

    def _sha_url(self, tool: str, version: str) -> str:
        return sha_list_url(tool, self._site)

    def _archive_url(self, tool: str, version: str, name: str) -> str:
        return download_base_url(tool, self._site) + name

    def latest(self, tool: str) -> str | ReleaseFailure:
        sha_list = self._get(sha_list_url(tool, self._site), MAX_SHA_BYTES)
        if isinstance(sha_list, ReleaseFailure):
            return sha_list
        versions = published_versions(tool, sha_list.decode("utf-8", errors="replace"))
        return versions[0] if versions else ReleaseFailure.NO_RELEASE


class ChainedReleases:
    """Procedure de l'auteur (2026-11-22) : GitHub ; si absent ou injoignable, le site kraynux ; si absent ou
    injoignable, le site craftdark. La premiere source qui publie l'outil donne sa version ; l'archive est prise la,
    puis ailleurs si besoin (meme empreinte verifiee). `origin(tool)` dit d'ou vient la version proposee."""

    def __init__(self, *sources: GithubReleases) -> None:
        self._sources = sources
        self._origin: dict[str, GithubReleases] = {}

    def latest(self, tool: str) -> str | ReleaseFailure:
        failure: ReleaseFailure = ReleaseFailure.NO_RELEASE
        for source in self._sources:
            found = source.latest(tool)
            if isinstance(found, ReleaseFailure):
                if found is ReleaseFailure.NETWORK:
                    failure = found
                continue
            self._origin[tool] = source
            return found
        return failure

    def origin(self, tool: str) -> str:
        source = self._origin.get(tool)
        return source.label if source is not None else ""

    def fetch(self, tool: str, version: str):  # type: ignore[no-untyped-def]
        first = self._origin.get(tool)
        order = [first, *[s for s in self._sources if s is not first]] if first else list(self._sources)
        result: object = ReleaseFailure.NO_RELEASE
        for source in order:
            if source is None:
                continue
            result = source.fetch(tool, version)
            if not isinstance(result, ReleaseFailure):
                return result
        return result
