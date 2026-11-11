<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="512">
</div>

# 🔗 OMEGA-CONNECT

**Relie entre elles les applications de la suite omega, sur une machine et sur tout le réseau**

> Élaboré par [kraynux](https://github.com/kraynux) pour [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Page officielle : [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/) &nbsp; Aperçu : [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Interface disponible en **17 langues** — voir [Langues de l'interface](#langues-de-linterface).  
**Langues :**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](docs/translation/en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](docs/translation/es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](docs/translation/pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](docs/translation/it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](docs/translation/de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](docs/translation/nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](docs/translation/pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](docs/translation/ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](docs/translation/zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](docs/translation/vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](docs/translation/th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](docs/translation/id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](docs/translation/ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](docs/translation/ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](docs/translation/hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](docs/translation/ar/README.md)

---

**Omega-connect** est l'interconnecteur de la suite `omega-` : il trouve les applications omega installées (omega-serv, omega-fire, omega-jail…) sur cette machine et sur les machines de votre réseau, montre ce qui est relié entre elles ou pas, et remet en place ce qui manque — toujours en montrant d'abord ce qu'il va faire. Une fois reliées, les applications se trouvent entre elles sans qu'omega-connect soit lancé.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect/D.png" width="24%" />
</p>

## 1. Vision et périmètre

Les applications omega sont faites pour travailler ensemble : les journaux d'omega-serv sont lus par les jails d'omega-jail, les bannissements de fail2ban rejoignent la liste noire d'omega-serv, omega-fire affiche tout cela. Encore faut-il que les fichiers soient au bon endroit, avec les bons droits, et que chaque application sache où sont les autres. Omega-connect s'en charge.

### Ce que fait Omega-connect

- Trouve les applications omega de cette machine (dossier personnel, services systemd, OpenRC ou runit, `/srv`, registre des instances d'omega-serv) et celles des autres machines, jointes par SSH avec vos clés.
- Tient un **registre** de toutes les applications de toutes les machines, avec leur version et leur état.
- Vérifie chaque **liaison** entre applications (journaux lus par les jails, pont vers la liste noire, liste protégée, fichiers d'omega-jail dans fail2ban, cartes d'identité, espace partagé) et dit ce qui ne va pas.
- **Synchronise** : crée les cartes d'identité qui manquent et prépare l'**espace partagé** où les applications se trouvent entre elles.
- **Répare** : fait corriger chaque écart par l'application qui possède le fichier ; jamais omega-connect à sa place.
- **Met à jour ou réinstalle** une application trop ancienne ou mal installée d'une machine du réseau, depuis sa Release GitHub (empreinte vérifiée).
- Agit sur une machine du réseau **depuis votre poste** : rien à taper là-bas, son mot de passe demandé une fois, par elle-même.
- Produit un **rapport** complet (texte, JSON ou page HTML).

### Ce qu'Omega-connect ne fait pas

- Il ne remplace aucune application : fail2ban, omega-fire, omega-jail et omega-serv gardent chacun leur rôle.
- Il ne réécrit jamais le fichier d'une autre application.
- Il n'installe rien de permanent sur une machine du réseau pour la scanner, et ne laisse pas de service tourner.
- Il ne demande jamais le mot de passe SSH, et ne voit jamais votre mot de passe administrateur.

## 2. Installation

### Prérequis

- Linux, Python 3.10+.
- Pour les machines du réseau : un accès SSH par clé, et Python 3.10+ sur ces machines.
- Connexion Internet pour les dépendances (et pour les mises à jour depuis GitHub).

### Installation

Depuis le dossier où se trouve l'archive :

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh` :

1. Crée l'environnement virtuel `.venv` (un `.venv` incomplet est mis de côté et recréé).
2. Installe omega-lib (bibliothèque de la suite, fournie dans l'archive) et omega-connect.
3. Rend `omega-connect.sh` et `install.sh` exécutables.
4. Ajoute l'alias `connect` à `~/.bashrc` et `~/.zshrc` (sans doublon).

Aucune étape ne demande de privilège administrateur.

### Mise à jour

Depuis le dossier qui CONTIENT `omega-connect/` (jamais depuis l'intérieur : `tar` créerait un dossier imbriqué), extrayez la nouvelle archive par-dessus, puis relancez `install.sh`. L'archive ne contient aucune donnée locale (`var/` : registre des machines, réglages, exports) : rien de ce qui existe n'est écrasé.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Utilisation

### Mode interactif (TUI)

```bash
./omega-connect.sh
```

ou, si l'alias est créé, `connect`.

Le menu principal a deux colonnes :

| Gestion | Maintenance |
|---|---|
| **Registre** — toutes les applications de toutes les machines, leur version et leur état | **Réparer** — la liste de tout ce qui ne va pas, et on choisit |
| **Scanner** — cette machine, et l'ajout des machines du réseau | **Rapport** — un document complet, à exporter |
| **Liaisons** — ce qui est relié ou pas, avec son état | **Réglages** — langue, thèmes, dossiers, purge |
| **Synchronisation** — relier les applications, sur toutes les machines | **Aide** — chaque menu, sa fonction et le détail |
| **Dashboard** — la vue d'ensemble | **Quitter** |

Parcours type : **Scanner** (cette machine, puis vos autres machines, proposées d'après vos profils Unison, `~/.ssh/config` et `known_hosts`) → **Registre** (mettre à jour ou réinstaller une application ancienne) → **Synchronisation** (cocher, puis synchroniser) → **Liaisons** et **Dashboard** pour voir le résultat → **Réparer** s'il reste un écart.

Chaque action affiche d'abord son plan ; rien n'est lancé avant votre accord. Pour une machine du réseau, l'interface laisse la place au terminal le temps de l'action : la machine demande elle-même son mot de passe, une fois.

#### Raccourcis clavier

| Touche | Action |
|---|---|
| `↑` / `↓` | Passer d'un élément à l'autre |
| `Tab` / `Maj+Tab` | Passer d'une zone de l'écran à l'autre |
| `Entrée` / `Espace` | Activer ; cocher une ligne (Synchronisation) |
| `Échap` | Revenir à l'écran précédent |
| `a` | Aide |
| `s` | Réglages |
| `t` | Thème suivant |
| `r` | Redessiner l'écran |
| `q` | Quitter (avec confirmation) |
| `Ctrl+P` | Commandes : thème, capture d'écran, quitter |

### États

| Applications | Liaisons |
|---|---|
| ● Reliée — dans l'espace partagé, à jour | OK |
| ◐ Inscrite — a sa carte d'identité, pas encore dans l'espace partagé | à réparer |
| ○ Détectée — sans carte d'identité | à réparer (bloquant) |
| ▲ À réparer — un écart | absent — rien à relier |
| ◌ Ancienne version — à mettre à jour | non vérifiable |
| ◇ Installation inachevée — à réinstaller | |
| ✕ Injoignable — la machine ne répond plus | |

### Langues de l'interface

L'interface est disponible en 17 langues : français, anglais, espagnol, portugais (Brésil), italien, allemand, néerlandais, polonais, russe, chinois simplifié, vietnamien, thaï, indonésien, japonais, coréen, hindi et arabe. Le choix se fait dans les Réglages (« Langue / Language ») et s'applique après un redémarrage de l'interface ; la variable `OMEGA_CONNECT_LANG` (par exemple `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) force une langue le temps d'une session. Sur une console texte Linux (TTY), les langues à écriture non latine s'affichent en anglais pour la session. La ligne de commande reste en français.

### Contact et support

L'aide (touche `a`) propose un écran **Contact et support** : *Payer un café* (page PayPal du développeur), *Contacter le support* (adresse mail et formulaire de contact du site, affichés en clair), *Se déclarer utilisateur (anonyme)* et *Vérifier les mises à jour*. La déclaration est volontaire, désactivée par défaut et envoyée une seule fois : elle sert seulement à compter les utilisateurs et, si on le souhaite, leur continent ou leur pays (listes fermées, jamais de texte libre). Elle envoie une clé tirée au hasard, le nom du logiciel (`omega-connect`) et sa version ; jamais de nom, de nom de machine, d'adresse ni de réglage. L'adresse IP n'est pas enregistrée dans les déclarations, mais passe, comme toute visite, par les contrôles de sécurité et le journal du serveur de réception. Retrait à tout moment depuis le même écran. La vérification des mises à jour lit seulement la liste des versions publiées, et jamais sans clic.

### Mode scriptable (CLI)

Toute commande déclenche le mode ligne de commande :

```bash
# Applications de cette machine, ou d'une machine du réseau (SSH avec vos clés)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Relier les applications de cette machine, ou d'une machine du réseau
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Mettre à jour les applications trop anciennes d'une machine du réseau (Release GitHub)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Réparer : cette machine, ou une machine du réseau
./omega-connect.sh reparer --machine moi@192.168.1.109

# État de chaque liaison, et rapport complet
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` montre le plan sans rien lancer ; `--oui` lance sans poser la question ; `--toutes-machines` enchaîne toutes les machines connues, une à une.

## 4. Machines du réseau

- **Connexion :** SSH avec vos clés uniquement ; `~/.ssh/config` est respecté (alias, port, utilisateur). Une clé protégée par une phrase secrète doit être chargée dans l'agent SSH.
- **Première connexion :** l'empreinte de la clé de la machine est montrée avant tout ; une clé qui a changé est refusée.
- **Scan :** un programme est envoyé en mémoire, en lecture seule ; rien n'est installé ni écrit, aucun mot de passe n'est demandé.
- **Action** (synchroniser, réparer, mettre à jour) : un dossier privé temporaire reçoit le programme et, s'il y a lieu, les archives ; il est effacé à la fin. Le mot de passe administrateur est demandé par la machine elle-même, une fois.
- **Identité :** une machine est reconnue à l'empreinte de son identifiant système, pas à son adresse : jointe par deux réseaux, elle reste une seule machine.
- **Mises à jour :** depuis la Release GitHub de chaque application ; l'empreinte de l'archive est vérifiée avec `sha.txt` avant tout envoi, puis de nouveau sur la machine. Chaque application est installée comme le dit la section « Mise à jour » de son README.

## 5. Carte d'identité et espace partagé

- **Carte d'identité :** à son installation, chaque application omega écrit un petit fichier qui dit qui elle est (application, version, identifiant, machine). Lisible par tous, jamais modifiable par les autres comptes.
- **Espace partagé :** `/var/lib/omega-synchro`, réservé au groupe `omega-synchro`, où seul l'administrateur écrit. Omega-connect y recopie les cartes d'identité et la description de chaque application ; les applications s'y trouvent entre elles, même quand omega-connect n'est pas lancé.
- **Registre de l'espace partagé :** tout ce qu'omega-connect crée y est inscrit ; un retrait ne défait que ce qui y est inscrit, et un fichier inconnu n'est jamais supprimé.

## 6. Sécurité

- Aucune élévation au lancement : omega-connect tourne sous votre compte ; sudo est demandé action par action, la commande affichée avant.
- Les corrections sont faites par l'application propriétaire du fichier (omega-jail pour ce qu'il pose dans fail2ban, omega-serv pour les droits de son `var/`, chaque application pour sa carte d'identité).
- Aucune application n'est lancée si elle risque de demander un mot de passe sans terminal.
- La recherche ne suit jamais un lien symbolique, ne change pas de système de fichiers et ignore les montages réseau.
- La purge des dossiers d'export et de captures refuse les dossiers système, personnels et celui d'omega-connect.

## 7. Exports

- **Rapport** : bilan de toutes les machines, liste précise de ce qu'il reste à faire, registre, machines du réseau, liaisons de chaque machine, espace partagé. Texte, JSON ou page HTML (thème au choix).
- **Aide** : exportable en page HTML.
- **Captures d'écran** : `Ctrl+P` → « Capture d'écran » (SVG).
- Dossiers par défaut : `var/exports/` et `var/screenshots/` du dossier d'omega-connect, modifiables dans les Réglages.

## 8. Architecture

Clean Architecture, comme le reste de la suite : `domain/` (règles pures), `application/` (cas d'usage), `ports/`, `infrastructure/` (SSH, fichiers, GitHub, presse-papiers), `interfaces/` (ligne de commande et interface Textual), `app/` (assemblage). Les dépendances vont toujours vers l'intérieur, vérifiées par `import-linter`. Les contrats partagés entre applications (carte d'identité, description, espace partagé) vivent dans `omega-lib`.

## 9. Tests

```bash
source .venv/bin/activate
lint-imports        # vérifie la règle des dépendances
pytest -q
ruff check src tests
mypy src
```

Les tests ne touchent jamais au vrai `var/`, ni au réseau, ni à sudo : faux SSH exécuté en local, faux GitHub, dossiers temporaires.

## 10. Hors périmètre

- Remplacer fail2ban, omega-fire ou omega-jail.
- Surveiller en continu (pas de service permanent).
- Installer une application omega pour la première fois sur une machine du réseau.
- Tableau de bord web.

## Licence

MIT — voir [LICENSE](LICENSE).

---

> Omega-connect — Trouver, relier, réparer.
> Les applications omega se parlent ; omega-connect s'assure qu'elles le peuvent.
