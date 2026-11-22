# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Archives publiees sur le SITE de l'outil (Updater, 2026-11-22 ; decision de l'auteur : « GitHub, puis le
site ») : dossier `download/` (STRUCTURE_PUBLICATION_OMEGA.md), liste `sha.txt` ; meme telechargement, memes
limites et meme verification d'empreinte que les Releases GitHub. Seule une version publiee sur le site est
proposee (jamais une archive de travail)."""
from __future__ import annotations

from omega_lib.declaration.policies import download_base_url, published_versions, sha_list_url

from omega_connect.domain.updates import ReleaseFailure
from omega_connect.infrastructure.updates.github_releases import MAX_SHA_BYTES, GithubReleases


class SiteReleases(GithubReleases):
    label = "site"

    def _sha_url(self, tool: str, version: str) -> str:
        return sha_list_url(tool)

    def _archive_url(self, tool: str, version: str, name: str) -> str:
        return download_base_url(tool) + name

    def latest(self, tool: str) -> str | ReleaseFailure:
        sha_list = self._get(sha_list_url(tool), MAX_SHA_BYTES)
        if isinstance(sha_list, ReleaseFailure):
            return sha_list
        versions = published_versions(tool, sha_list.decode("utf-8", errors="replace"))
        return versions[0] if versions else ReleaseFailure.NO_RELEASE


class ChainedReleases:
    """GitHub puis le site : la plus haute version publiee (GitHub a egalite) ; chaque archive est prise la ou sa
    version a ete trouvee, puis ailleurs si besoin. `origin(tool)` dit d'ou vient la version proposee."""

    def __init__(self, *sources: GithubReleases) -> None:
        self._sources = sources
        self._origin: dict[str, GithubReleases] = {}

    def latest(self, tool: str) -> str | ReleaseFailure:
        from omega_connect.domain.versions import version_key

        best: tuple[tuple[int, ...], str, GithubReleases] | None = None
        failure: ReleaseFailure = ReleaseFailure.NO_RELEASE
        for source in self._sources:
            found = source.latest(tool)
            if isinstance(found, ReleaseFailure):
                if found is ReleaseFailure.NETWORK:
                    failure = found
                continue
            key = version_key(found) or ()
            if best is None or key > best[0]:
                best = (key, found, source)
        if best is None:
            return failure
        self._origin[tool] = best[2]
        return best[1]

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
