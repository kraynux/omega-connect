# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Mise a jour d'un outil SUR la machine distante (lot R3) : execute par le programme envoye par omega-connect,
dans un terminal (ssh -t) ou la personne voit tout et tape elle-meme son mot de passe sudo.

Meme procedure que la section « Mise a jour » du README de chaque outil, sans rien a taper :
1. empreinte de l'archive verifiee de nouveau (deja verifiee avant l'envoi) ;
2. extraction dans le dossier prive de la session, membre par membre : fichiers et dossiers seulement, jamais un
   chemin absolu, un `..`, un lien ou un peripherique, et tout sous `<outil>/` ;
3. « par-dessus » (omega-serv, omega-jail...) : chaque fichier est remplace (fichier temporaire puis `rename`, qui
   remplace un lien sans jamais le suivre) ; l'etat vivant n'est pas dans l'archive, il n'est pas touche ;
   « de cote » (omega-fire, dont var/ appartient a root) : `sudo mv <racine> <racine>.old-AAAAMMJJ`, nouvelle copie a
   la place, et son `install.sh` reprend lui-meme l'etat de l'ancienne. S'il y a d'autres anciennes installations a
   cote, son `install.sh` ne sait pas laquelle reprendre (il refuse de deviner) : omega-connect, qui vient de mettre
   l'ancienne de cote, la designe lui-meme (`sudo ./migrate-state.sh <ancienne> --yes`, ce que conseille son README ;
   constate le 2026-11-11 sur omega-server, avec un vieux `omega-fire.old-20260927`) ;
4. `.venv` casse (creation interrompue : ni `bin/activate` ni Python qui demarre) mis de cote en
   `.venv.casse-AAAAMMJJ-HHMMSS`, jamais supprime : l'`install.sh` des outils garde un `.venv` existant sans le
   verifier et echouait sur `activate` (constate le 2026-11-11 sur omega-server, `.venv` du 29 septembre) ;
5. `./install.sh` de l'outil, dans le terminal (ses questions et son sudo s'affichent a la personne)."""
from __future__ import annotations

import hashlib
import os
import posixpath
import shutil
import stat
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path

from omega_connect.domain.updates import UpdateOrder
from omega_connect.domain.versions import UpdateMode
from omega_connect.shared.i18n import _

MAX_EXTRACTED_BYTES = 512 * 1024 * 1024
STANDARD_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
MIGRATE_SCRIPT = "migrate-state.sh"


class UpdateError(Exception):
    """Mise a jour refusee ou echouee ; le message est montre a la personne."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_members(archive: tarfile.TarFile, tool: str) -> list[tarfile.TarInfo]:
    members = []
    total = 0
    for member in archive.getmembers():
        name = posixpath.normpath(member.name)
        parts = name.split("/")
        if name.startswith("/") or ".." in parts or parts[0] != tool:
            raise UpdateError(_("archive refusée : chemin inattendu {name}").format(name=member.name))
        if not (member.isfile() or member.isdir()):
            raise UpdateError(_("archive refusée : {name} n'est ni un fichier ni un dossier").format(name=member.name))
        total += member.size
        if total > MAX_EXTRACTED_BYTES:
            raise UpdateError(_("archive refusée : trop volumineuse une fois extraite"))
        member.mode &= 0o755 if member.isdir() else 0o775
        members.append(member)
    return members


def extract(archive_path: Path, tool: str, destination: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = _safe_members(archive, tool)
        if hasattr(tarfile, "data_filter"):
            archive.extractall(destination, members=members, filter="data")
        else:  # Python 3.10/3.11 sans le filtre : membres deja verifies un par un
            archive.extractall(destination, members=members)  # noqa: S202
    source = destination / tool
    if not source.is_dir() or source.is_symlink():
        raise UpdateError(_("archive refusée : pas de dossier {tool}/").format(tool=tool))
    return source


def copy_over(source: Path, root: Path) -> int:
    """Remplace les fichiers de `root` par ceux de `source` ; jamais un lien suivi ; nombre de fichiers copies."""
    copied = 0
    for directory, dirnames, filenames in os.walk(source):
        relative = Path(directory).relative_to(source)
        target_dir = root / relative
        if target_dir.is_symlink():
            raise UpdateError(_("{path} est un lien : rien n'est copié dedans").format(path=target_dir))
        target_dir.mkdir(mode=0o755, exist_ok=True)
        dirnames.sort()
        for name in sorted(filenames):
            origin = Path(directory) / name
            target = target_dir / name
            temporary = target_dir / f".{name}.omega-connect-maj"
            temporary.unlink(missing_ok=True)
            shutil.copyfile(origin, temporary, follow_symlinks=False)
            os.chmod(temporary, stat.S_IMODE(origin.stat().st_mode))
            os.replace(temporary, target)
            copied += 1
    return copied


def _check_root(root: Path) -> None:
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise UpdateError(_("{root} n'est pas un dossier d'installation").format(root=root))
    if root.stat().st_uid != os.getuid():
        raise UpdateError(_("{root} n'appartient pas à ce compte : mise à jour faite à la main").format(root=root))


def _looks_old(path: Path, tool: str) -> bool:
    """Meme regle que l'install.sh d'omega-fire : `config/<outil>.conf`, ou une base dans var/db."""
    try:
        if (path / "config" / f"{tool}.conf").is_file():
            return True
        return any((path / "var" / "db").iterdir())
    except OSError:
        return False


def _neighbours(root: Path, tool: str) -> list[Path]:
    """Anciennes installations voisines que l'install.sh d'omega-fire pourrait reprendre (il refuse de choisir
    s'il y en a plusieurs)."""
    return [path for path in sorted(root.parent.glob(f"*{tool}*"))
            if path != root and path.is_dir() and not path.is_symlink() and _looks_old(path, tool)]


def _aside_name(root: Path, now: datetime) -> Path:
    candidate = root.with_name(f"{root.name}.old-{now:%Y%m%d}")
    if candidate.exists():
        candidate = root.with_name(f"{root.name}.old-{now:%Y%m%d-%H%M%S}")
    return candidate


def _venv_works(venv: Path) -> bool:
    python = venv / "bin" / "python"
    if not (venv / "bin" / "activate").is_file() or not python.exists():
        return False
    try:
        return subprocess.run([str(python), "-c", "pass"], capture_output=True, check=False,  # noqa: S603
                              timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def set_aside_broken_venv(root: Path, now: datetime) -> str:
    """`.venv` casse renomme (jamais supprime) ; renvoie son nouveau nom, vide s'il n'y avait rien a faire."""
    venv = root / ".venv"
    if not venv.is_dir() or venv.is_symlink() or _venv_works(venv):
        return ""
    target = root / f".venv.casse-{now:%Y%m%d-%H%M%S}"
    venv.rename(target)
    return str(target)


def _run(argv: list[str], cwd: Path | None = None) -> int:
    environment = dict(os.environ)
    environment["PATH"] = STANDARD_PATH + (":" + environment["PATH"] if environment.get("PATH") else "")
    try:
        return subprocess.run(argv, cwd=cwd, env=environment, check=False).returncode  # noqa: S603
    except OSError as error:
        print(error)
        return 127


def run_shell(command: str) -> int:
    """Commande « a la main » annoncee (Reparer, retour de l'auteur : « un bouton Reparer qui lance directement la
    commande distante ») : affichee puis lancee dans le terminal, ou sudo demande lui-meme son mot de passe."""
    print(f"$ {command}", flush=True)
    return _run(["/bin/sh", "-c", command])


def apply_update(order: UpdateOrder, session: Path, *, now: datetime | None = None, sudo: str = "sudo") -> str:
    """Mise a jour complete ; renvoie le dossier mis de cote (mode « de cote »), sinon vide. Leve UpdateError."""
    archive = session / order.archive
    if not archive.is_file() or _sha256(archive) != order.sha256:
        raise UpdateError(_("empreinte de l'archive différente de sha.txt : rien n'est installé"))
    root = Path(order.root)
    _check_root(root)
    work = session / f"extrait-{order.tool}"
    work.mkdir(mode=0o700)
    source = extract(archive, order.tool, work)
    aside = ""
    others: list[Path] = []
    if order.mode is UpdateMode.ASIDE:
        others = _neighbours(root, order.tool)
        target = _aside_name(root, now or datetime.now())
        print(_("Mise de côté de l'ancienne installation : {old} → {new}").format(old=root, new=target), flush=True)
        if _run([sudo, "mv", "--", str(root), str(target)]) != 0:
            raise UpdateError(_("impossible de mettre l'ancienne installation de côté (sudo mv)"))
        root.mkdir(mode=0o755)
        aside = str(target)
    count = copy_over(source, root)
    print(_("{count} fichiers installés dans {root}.").format(count=count, root=root), flush=True)
    installer = root / "install.sh"
    if not installer.is_file() or installer.is_symlink():
        raise UpdateError(_("install.sh introuvable dans {root}").format(root=root))
    installer.chmod(0o755)
    broken = set_aside_broken_venv(root, now or datetime.now())
    if broken:
        print(_("Environnement Python (.venv) incomplet mis de côté : {path} — install.sh en recrée un.").format(
            path=broken), flush=True)
    print(_("Lancement de {path} :").format(path=installer), flush=True)
    code = _run(["./install.sh"], cwd=root)
    if code != 0:
        raise UpdateError(_("install.sh a échoué (code {code})").format(code=code))
    if aside and others:
        # install.sh a vu plusieurs anciennes installations et n'en a repris aucune : omega-connect sait laquelle.
        migrate = root / MIGRATE_SCRIPT
        if not migrate.is_file() or migrate.is_symlink():
            raise UpdateError(_("{script} introuvable : réglages et données restés dans {old}").format(
                script=MIGRATE_SCRIPT, old=aside))
        print(_("Reprise des réglages et données de {old} (autres anciennes installations ignorées : {others})")
              .format(old=aside, others=", ".join(map(str, others))), flush=True)
        if _run([sudo, f"./{MIGRATE_SCRIPT}", aside, "--yes"], cwd=root) != 0:
            raise UpdateError(_("reprise de {old} échouée ({script})").format(old=aside, script=MIGRATE_SCRIPT))
    return aside
