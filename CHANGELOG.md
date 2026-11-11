<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [0.1.0] — construite le 2026-11-11

### Ajouté

- **Lot A — `detecter`** (lecture seule, sans root) : cherche les outils omega dans le registre des
  instances d'omega-serv, les services systemd, OpenRC et runit, le HOME (3 niveaux), `/srv` (2 niveaux)
  et les dossiers donnés avec `--chemin`. Jamais de lien symbolique suivi, jamais de changement de système
  de fichiers, montages réseau ignorés. Pour chaque installation : jeton d'installation, fiche demandée à
  l'outil sous le compte propriétaire du dossier, identifiants en double signalés (jamais fusionnés).
  Sortie texte (français de référence) ou JSON (`--format json`, jamais traduit).
- **Lot B — `verifier`** (lecture seule, sans root) : état de chaque lien entre outils — actif, dégradé,
  absent, cassé ou non vérifiable — avec la commande qui corrigerait chaque écart, affichée sans jamais
  être lancée :
  - journaux d'omega-serv et de magnet → jails d'omega-jail : journal présent (sinon fail2ban refuse de
    démarrer), filtre présent, même fichier que celui qu'écrit l'instance, fonction active couverte, droits
    du journal pour le service, mode log-only d'omega-waf ;
  - pont fail2ban → liste noire : une action par instance, visant la bonne instance (jails RIPOSTE d'une
    deuxième instance compris), script du pont appartenant à root et non modifiable par un autre compte ;
  - liste protégée : `ignoreip` des jails et réseaux exemptés du pont identiques à ceux d'omega-serv ;
  - liste noire d'omega-serv : jamais à root, groupe du service, au moins 0660 ;
  - fichiers d'omega-jail dans fail2ban (root:root 0644, fichiers abîmés), jetons d'installation.
  Code de sortie 1 si un lien est cassé ou dégradé. Sortie texte (`--detail` pour les contrôles conformes)
  ou JSON (`--format json`, jamais traduit).
- **Lot C — tableau de bord** (`omega-connect.sh` sans commande, ou `tableau [--chemin DOSSIER]`), en
  lecture seule : outils et instances (version, service, jeton, fiche déclarée à telle heure), liens et leur
  état, contrôles du lien surligné avec les commandes de correction (jamais lancées), écran « Détail du
  lien », remarques sur la recherche. Vérification dans un fil au lancement puis toutes les 2 minutes tant
  que l'écran est ouvert (aucun démon). Même cadre que le reste de la suite : thèmes d'omega-lib (`t`),
  confirmation avant de quitter. Sans terminal interactif : message et code 2.
- **Lot D — zone neutre** (`etablir`, `retirer`) : crée le groupe `omega-synchro` et la zone
  `/var/lib/omega-synchro` (2750, sous-dossiers jetons, fiches, liens, bans), ajoute la personne au groupe,
  recopie jeton et fiche de chaque outil (0640, root:omega-synchro) et inscrit chaque création au registre
  (`registre.json`, format `omega-registre` d'omega-lib). Commandes ordinaires (groupadd, install, gpasswd,
  rm, rmdir, groupdel) affichées avant tout accord, puis lancées une à une avec `sudo -n` après une seule
  authentification ; jamais de shell, jamais d'élévation de tout l'outil. Au premier échec : arrêt, registre
  réécrit pour garder la trace de ce qui a été créé. Relancée, `etablir` actualise les copies (une date
  rafraîchie ne compte pas). `retirer --tout` défait exactement le registre (garder la zone « liens figés »
  ou tout retirer) ; `retirer CIBLE` enlève un outil désinstallé. `--simulation`, `--oui`. Zone illisible par
  la session (groupe pas encore pris en compte) : relue avec `sudo -n find / stat / cat`, après accord.
- **`verifier`** : nouveau lien « Zone neutre » (dossiers, groupe, membre, registre, copies à jour ou
  périmées, outil relié mais introuvable, outil installé pas encore relié).
- **Interface** : écran de démarrage (logo d'`ascii.txt`, nuances █▓▒░ rendues par transparence du ton
  clair), menu principal par thème — Tableau de bord, Outils, Synchronisation, Règles, Droits, Réseaux ;
  Réparer (lot E), Registre, Réglages, Aide, Contact et support (lot F). Synchronisation (« Établir /
  actualiser ») et Registre (« Retirer cet outil », « Tout retirer… ») montrent chaque commande avant de
  demander le mot de passe sudo sur le vrai terminal.
- **Rapport** (Maintenance → Rapport ; commande `rapport [--format texte|json|html] [--theme T]
  [--enregistrer]`) : export complet — bilan, outils et instances (jeton, fiche, service, sources), chaque lien
  avec tous ses contrôles et commandes de correction, remarques de la recherche, zone neutre et registre. Lecture
  seule, sans root (zone illisible : dit tel quel). Texte, JSON (`omega-connect-rapport` v1, jamais traduit) ou
  page HTML autonome au cadre des rapports d'omega-fire (fenêtre de terminal, panneaux bleu nuit superposés, cartes,
  badges, pied de page ; feuilles reprises telles quelles dans `report_styles/`) aux 5 thèmes d'export d'omega-lib, tout texte de la machine échappé. Enregistré dans
  `var/exports/` (`OMEGA_CONNECT_VAR_DIR` le remplace) ; sous sudo, le fichier est rendu au propriétaire.
- **Menu** : « Rapport » sous Registre ; « Contact et support » rejoint l'Aide (lot F), comme dans les autres
  outils ; « Quitter » (avec confirmation) équilibre les deux colonnes (6 et 6). Placement du logo recalculé sur
  un axe unique ; voyant OFF allumé (l'interrupteur est sur OFF).
- **« Non vérifiable » toujours expliqué** : en attente de reconnexion (déjà membre du groupe omega-synchro),
  pas membre du groupe (`etablir` proposé), sans root, fiche non fournie, liste protégée absente, jeton
  illisible ; la raison s'affiche aussi dans la colonne « Constat ». Mode log-only : message explicite (jail
  waf-magnet posé par omega-jail qui bannit au niveau réseau ; omega-connect ne se substitue pas à fail2ban).
- **Barre d'état identique sur tous les écrans** (comme omega-log) : Échap Retour, q Quitter, t Thème suivant,
  r Rafraîchir, a Aide, s Réglages ; plus de touche propre à un écran ni de doublon Échap/q au menu.
- **Indicateurs d'attente** (animation + phrase) : génération du rapport, synchronisation, initialisation du
  registre, préparation des commandes.
- **Lot E — `reparer`** (`[--chemin] [--simulation] [--oui]`, et Maintenance → Réparer) : chaque écart de
  `verifier` est corrigé par la commande de l'outil qui possède le fichier, jamais par omega-connect à sa place —
  `omega-jail.sh --apply --update` pour tout ce qu'omega-jail pose dans fail2ban (contenu et droits),
  `omega-serv.sh service permissions` pour les droits de son `var/` (liste noire, journaux lus par les jails),
  `<outil> synchro jeton` sous le compte propriétaire pour un jeton absent ou abîmé ; puis, si la zone a des
  écarts, le plan d'`etablir` (seulement ce que le registre dit avoir créé), affiché à son tour. Commandes
  affichées avant l'accord, lanceur vérifié juste avant (fichier ordinaire du propriétaire du dossier, non
  modifiable par le groupe ni les autres), une seule authentification sudo, arrêt au premier échec. Ce qu'aucun
  outil ne sait corriger reste affiché « à faire à la main » ; un outil relié mais désinstallé reste une décision
  (`retirer`). `verifier` indique le nombre d'écarts corrigeables par `reparer`, et ses corrections proposées sont
  désormais ces commandes d'outils (plus de `chown`/`chmod` sur les fichiers d'omega-serv ou d'omega-jail).
- **Groupe de la zone donné au service omega-serv** (spec §5, décision de l'auteur : complément systemd) :
  `etablir` demande à omega-serv (`synchro groupe-service ajouter`) d'écrire
  `/etc/systemd/system/<service>.service.d/omega-synchro.conf` pour un service qui tourne sous un compte dédié ;
  l'unité n'est jamais touchée, pris en compte au prochain redémarrage du service (jamais redémarré par
  omega-connect). Inscrit au registre ; `retirer --tout` le fait retirer par omega-serv **avant** de supprimer le
  groupe (sinon le service ne démarrerait plus), et garde le groupe si omega-serv est introuvable. `verifier` :
  « service sans le groupe omega-synchro ». Test de réversibilité étendu au faux système (service compris).
- **Parcours plus clair** (retour de l'auteur) : `reparer` enchaîne sur le plan d'`etablir` après avoir créé un
  jeton, ou quand la zone n'est pas lisible sans sudo ; Synchronisation a « Lire avec sudo » ; Registre montre les
  outils « installés, pas encore reliés » avec « Relier (établir)… ». La notification de lecture avec sudo dit
  pourquoi (groupe pas encore pris en compte par la session).
- **Plus besoin de se reconnecter après « Établir »** (« il faut une commande universelle ») : si vous êtes membre
  du groupe omega-synchro mais que votre session ne le sait pas encore, omega-connect se relance lui-même au
  démarrage avec ce groupe, qu'il soit lancé par `omega-connect.sh` ou par `python -m omega_connect` (`sg`, ou
  `newgrp` là où `sg` n'existe pas, comme sur Manjaro). Aucun mot de passe, rien à
  taper, arguments et code de sortie inchangés ; une seule fois (pas de boucle). Sans terminal ni `sg` (script) :
  comportement d'avant (zone « en attente de reconnexion », lecture avec sudo après accord).

- **Refonte du parcours, lot R1** (bilan de l'auteur : « parcours incompréhensible ») : menu Registre, Scanner,
  Liaisons, Dashboard | Réparer, Rapport, Réglages, Aide. Le **Registre** montre toutes les applications de la
  machine et leur état (Détectée, Inscrite, Reliée, À corriger, Ancienne version), avec cases à cocher, pastille de
  l'espace partagé, « Corriger » et « Détail ». **Inscrire** (sélection ou tout ; commande `inscrire`) remplace
  Établir + jetons + lecture avec sudo : un seul plan, un seul mot de passe, rien de non annoncé n'est lancé.
  **Scanner** (commande `scanner`) met à jour le registre et le registre du parc (`var/parc.json`). Mots simples
  en premier plan (carte d'identité, espace partagé). L'écran Synchronisation et les vues Outils, Règles, Droits,
  Réseaux disparaissent (Registre, Liaisons et Dashboard les remplacent).
  Retour de l'auteur le jour même : menu GESTION (Registre, Scanner, Liaisons, Synchronisation, Dashboard) |
  MAINTENANCE (Réparer, Rapport, Réglages, Aide, Quitter). Le **Registre** n'est plus qu'un affichage (états en
  couleur, bilan par état) ; **Synchronisation** revient et porte l'action : « Synchroniser tout / la sélection »
  (commande `synchroniser`, `inscrire` reste accepté), contrôles de l'espace partagé, « Lire avec sudo », Détail.

- **Provenance des liaisons** (demande de l'auteur) : colonne « Provenance » dans Liaisons et le Dashboard —
  « Local » (cette machine) ou « Réseau — machine » (machine distante, lot R2 ; liaison entre machines, lot R4) ;
  aussi dans le JSON de `verifier`.

- **Lot R2 — scanner distant** (Scanner → Machine distante ; `scanner utilisateur@machine`) : SSH avec vos clés
  seulement, scanner envoyé en mémoire (rien installé là-bas, Python 3.10+ requis), machine inconnue = empreinte de
  sa clé montrée et confiance demandée, clé changée = refus. Une machine est reconnue à son empreinte, pas à son
  adresse (plusieurs réseaux = une machine, adresses cumulées). Registre multi-machines (« Injoignable » si elle ne
  répond plus) ; liaisons distantes en provenance « Réseau ». Le Scanner propose les machines que cet ordinateur
  sait déjà joindre (profils Unison, `~/.ssh/config`, `known_hosts`), sans rien taper ; la saisie manuelle reste
  (`scanner --liste` en ligne de commande).
- **Lot R3 — synchroniser une machine distante sans rien y taper** (Synchronisation → Machines distantes ;
  `synchroniser --machine MACHINE`, `--toutes-machines`) : plan calculé sur la machine elle-même, sans sudo, et
  affiché avant tout ; un outil trop ancien y est mis à jour depuis sa Release GitHub (`kraynux/<outil>`,
  étiquette `v<version>`) — archive téléchargée ici, empreinte vérifiée avec le `sha.txt` de la Release avant tout
  envoi, refusée sinon ; extraction par-dessus (omega-serv, omega-jail) ou ancienne installation mise de côté
  (omega-fire, comme son README), puis l'`install.sh` de l'outil ; ensuite `reparer` et `synchroniser` sur la
  machine. Tout se passe dans le terminal : la machine demande elle-même son mot de passe sudo, une fois ;
  omega-connect ne le voit jamais. Le programme envoyé vit dans un dossier privé (0700) effacé à la fin ; la
  machine est rescannée et le registre montre le résultat. « Toutes les machines » : une à une, un mot de passe
  par machine.
- **Version installée lue dans les fichiers de l'outil** (`pyproject.toml`, constante d'omega-fire), sans rien
  exécuter : une version trop ancienne est reconnue même sans carte d'identité ni fiche, et le registre l'affiche.

- **Lot F — Réglages, Aide, langues, installation et publication** :
  - Réglages : langue (17), thème de l'interface et des exports (enregistrés), dossiers des exports et des captures
    (par défaut `var/exports/` et `var/screenshots/`), purge protégée de ces deux dossiers ;
  - capture d'écran Textual (Ctrl+P → « Capture d'écran », SVG dans le dossier des captures) ;
  - Aide exhaustive sur le modèle d'omega-log (une section repliable par menu, démarrage rapide, raccourcis, états,
    sécurité, ligne de commande), exportable en HTML, avec Contact et support (écrans partagés d'omega-lib) ;
  - interface en 17 langues (catalogue `omega-connect`, la ligne de commande reste en français) ;
  - `install.sh` (un `.venv` incomplet est mis de côté et recréé), `build-release.sh` (archive versionnée,
    `sha.txt`, omega-lib embarquée, langues compilées, `var/` jamais livré), `.gitignore` ;
  - README en 17 langues, site (présentation et README en 17 langues, galerie, captures A-D par langue).

### Corrigé

- **Dashboard refait en vue d'ensemble** (demande de l'auteur, 2026-11-11) : des cadres séparés, comme un tableau
  de bord web. En haut, Machines, Applications, Liaisons et Espace partagé ; au milieu, Liaisons par type (barres OK
  sur total) et Cette machine / Réseau ; en bas, un top 5 par catégorie (top 3 sur un petit écran) : machines à
  réparer, liaisons à réparer, versions en retard, scans les plus anciens. Les cadres se rangent sur 4, 2 ou
  1 colonne(s) selon la largeur. Actualiser et Retour seulement ; mêmes mots d'état que partout ailleurs. Le
  tableau des applications (dossier, service, carte d'identité) reste au Registre, les contrôles et « Détail du
  lien » aux Liaisons, les remarques de recherche au Rapport. La phrase « à venir pendant la refonte » disparaît.
- Aide : la liste des thèmes d'export a une largeur fixe ; elle repoussait « Exporter » et « Retour » hors de
  l'écran. Disposition : le thème puis « Exporter l'aide en HTML », en dessous « Contact et support » et « Retour ».
- Réglages : les dossiers par défaut s'affichent `var/exports/` et `var/screenshots/` (dossier d'omega-connect),
  jamais le chemin complet de la machine ; un chemin relatif part du dossier d'omega-connect.
- Langues : plus de mention « en test » dans la liste.

- **Trois actions distinctes, nommées explicitement** (retour de l'auteur, 2026-11-11 : « mettre à jour le
  registre, mettre à jour l'application, synchroniser l'application, c'est pas la même chose ») :
  - Registre : « Mettre à jour le registre » refait le scan sur place (avant : ouvrait le Scanner) ;
    « Mettre à jour l'application » installe la dernière version GitHub d'une application trop ancienne (ligne
    choisie, machine distante), et rien d'autre ;
  - Synchronisation : réparer puis synchroniser, jamais de mise à jour ;
  - en ligne de commande : `mettre-a-jour --machine …` et `synchroniser --machine …`.
- **Synchronisation = une seule liste de toutes les machines et de leurs applications** (rôle défini par l'auteur) :
  les machines du réseau sont rescannées à l'ouverture ; on coche des lignes de n'importe quelle machine, puis
  « Synchroniser la sélection » ou « Synchroniser tout ». Cette machine passe d'abord (son plan, un mot de passe),
  puis chaque machine du réseau, une à une (plan calculé sur elle, lancé depuis ici). Une application trop
  ancienne, inachevée ou injoignable ne se coche pas : la ligne dit où aller.
- **Réparer = la liste de tout ce qui ne va pas** (retour de l'auteur, 2026-11-11 : « on tourne en boucle ») :
  - une ligne par problème, sur toutes les machines : machine, problème, état, qui le corrige ;
  - « Réparer la ligne choisie », « Tout réparer », « Détail ».
  - Les machines du réseau sont rescannées à l'ouverture : la liste dit l'état réel, jamais celui d'un ancien
    scan.
  - Une ligne sans correction connue n'est pas présentée comme réparable.
- **Mêmes mots d'état partout** : liaisons « OK », « à réparer », « à réparer (bloquant) » (avant : actif, dégradé,
  cassé) ; Registre « À réparer » (avant : À corriger). Les écrans qui montrent (Dashboard, Liaisons) n'agissent
  pas : les actions sont dans Réparer et Synchronisation.
- **Carte d'identité « toujours dégradée » après Réparer** (craftdark) : omega-serv partage son var/ avec le groupe
  de son service (0664) ; la règle exigeait 0644 exactement. 0644 ou 0664 sont acceptés, jamais d'écriture pour
  les autres comptes.
- **« Réinstaller l'application »** pour une installation inachevée (avant : « trop ancien, mettre à jour » alors
  que c'était la dernière version).
- **Rapport refait** : bilan de toutes les machines, liste précise de ce qu'il reste à faire (par menu et par
  bouton, avec la machine, la liaison et qui corrige), registre, machines du réseau rescannées avant le rapport,
  liaisons de chaque machine. Les phrases propres à la ligne de commande sont retirées (« relisez-les avant… »,
  « Aucune action n'est lancée sans votre accord »), ainsi que le vocabulaire technique : carte d'identité (et non
  jeton), espace partagé (et non zone), description (et non fiche), noms des menus.
- **Installation inachevée** (omega-server : fichiers 2.6.1, `install.sh` arrêté, ni environnement Python ni
  carte) : nouvel état du Registre ◇ « Installation inachevée » ; « Mettre à jour l'application » la réinstalle
  (même version acceptée). Le `.venv` est vu sans rien exécuter (`bin/activate` et `bin/python`).
- **Réparer agit aussi sur les machines distantes** (retour de l'auteur : « on ne peut rien réparer depuis
  omega-connect, et les commandes il faut les retaper à la main sur la machine distante ») : Réparer → Machines
  distantes → « Réparer la machine choisie » lance les commandes des outils SUR la machine, depuis ici ;
  `reparer --machine …`. Ce qu'aucun outil ne sait faire se copie : « Copier les commandes » (Réparer, machine
  distante, détail d'une liaison), presse-papiers du terminal.
- **« Réparer <machine> » lance aussi les commandes qu'aucun outil ne sait faire** (retour de l'auteur : « un
  bouton Réparer et ça lance directement la commande distante ») : annoncées dans le plan, puis lancées une à une
  sur la machine, après les corrections des outils, dans le terminal. Celles déjà réglées entre-temps sont
  sautées ; une commande qui n'était pas annoncée n'est jamais lancée.
- **Copier, quel que soit le presse-papiers** (« ça copie rien, juste la notif » ; « ma machine n'est pas
  représentative ») : presse-papiers du système d'abord (wl-copy, xclip, xsel, lancé dans sa propre session pour
  survivre, comme la copie de lnav), puis celui du terminal (OSC 52) en plus. Sans outil, les commandes
  s'affichent en clair dans le terminal (interface mise de côté), à sélectionner à la souris : ça marche partout.
- **Compte verrouillé par le scan** (omega-server, 2026-11-11 : « le mot de passe est refusé ») : pour lire sa
  fiche, le scan lançait un très vieil omega-fire, qui se relance lui-même avec sudo. Sans terminal, sudo échouait
  sans rien demander, mais `pam_faillock` comptait chaque échec. Au bout de trois, le compte était verrouillé
  10 minutes et le vrai mot de passe refusé. Désormais, un outil n'est lancé que s'il a une carte d'identité, ou si
  sa version, lue dans ses fichiers, est assez récente pour répondre.
- **`.venv` cassé** (omega-server : création interrompue en septembre) : l'`install.sh` d'omega-serv le gardait et
  échouait sur `activate`. Avant `install.sh`, un `.venv` qui ne fonctionne pas est mis de côté
  (`.venv.casse-…`, jamais supprimé).
- **Synchronisation distante, premiers lancements réels** (2026-11-11) :
  - **craftdark** : tout avait réussi sur la machine, mais l'interface disait « aucun résultat ». La commande qui
    relit le résultat et efface le dossier privé ne fixait pas le PATH (zsh d'Archcraft : `cat`, `rm`
    introuvables). Chaque commande distante a désormais le PATH standard en tête. Un dossier de session oublié
    (coupure, terminal fermé) est effacé au lancement suivant, après 2 h.
  - **omega-server** : omega-fire n'était pas mis à jour (« anciennes installations voisines… rangez-les ») parce
    qu'un vieux `omega-fire.old-20260927` traînait à côté. omega-connect, qui vient de mettre l'ancienne
    installation de côté, désigne maintenant lui-même celle à reprendre (`sudo ./migrate-state.sh <ancienne>
    --yes`, comme le conseille le README d'omega-fire). Les autres ne sont jamais touchées.
- **Commande inconnue proposée à une version trop ancienne** (constaté par l'auteur sur craftdark :
  `omega-jail.sh --apply --update` → « unrecognized arguments: --update » avec omega-jail 1.1.0) : un outil plus
  ancien que sa première version à contrats ne reçoit plus aucune commande de réparation ; il est listé « trop
  ancien », et la Synchronisation le met à jour d'abord.

- **Écrans qui n'occupaient pas l'écran** (retour de l'auteur sur Liaisons) : les tableaux étaient bloqués à 16 lignes
  et à la largeur de leur contenu, avec un ascenseur alors qu'il restait de la place. Liaisons et Registre : le
  tableau prend toute la place restante et défile seul, titre et détail restent visibles ; partout, la dernière
  colonne s'étire jusqu'au bord et les plafonds suivent la hauteur de l'écran (`vh`). Test en 120×40 et 200×60.
- **Scanner : « Retirer cette machine »** (grand parc : ne plus tout rescanner) — la machine sort du registre, rien
  n'est modifié sur elle ; `scanner --retirer MACHINE` en ligne de commande. La machine locale ne se retire pas.

- **Scanner distant** (retour de l'auteur) : le scan annulait la vérification de la clé de la machine encore en cours
  (tâches dans un même groupe exclusif) ; échecs SSH désormais distincts et expliqués — nom inconnu, aucun serveur
  SSH (« Connection refused »), machine injoignable.

- **Rapport : l'interface se fermait sur la console** (constaté par l'auteur juste après sa première
  synchronisation réelle) : la liste des libellés des créations ne connaissait pas « groupe donné au service »
  (`KeyError`). Une seule liste désormais, partagée par le rapport et l'écran Détail, et un test exige un libellé
  pour chaque type de création. Reproduit puis vérifié en réel (terminal simulé, parcours clavier jusqu'au Rapport).
- **Scanner** : bouton « Retour » en bas ; « Voir le registre » ouvre le Registre quand le Scanner vient du menu
  (il ramenait au menu).

- **Copies de sauvegarde ignorées par la recherche** (décision de l'auteur) : dossiers `…-bak`, `….bak`, `…_bak`,
  `….bak-…` (comme `….old-…`). Un dossier donné avec `--chemin` reste examiné.

- **Mot de passe sudo refusé depuis l'interface** (constaté par l'auteur : invite de sudo affichée dans l'en-tête).
  Cause : pendant la détection, la fiche est demandée à chaque outil ; une ancienne version d'omega-fire (sans
  `synchro`) s'élève alors avec sudo, et sudo ouvre le terminal directement : son invite s'affichait par-dessus
  l'interface et les frappes partaient à moitié dans Textual. La fiche est désormais demandée dans une nouvelle
  session, sans terminal de contrôle : aucun outil ne peut plus demander de mot de passe (sudo échoue aussitôt,
  fiche « non obtenue »). En plus, avant l'invite de « Lancer avec sudo », le terminal est remis à l'état ordinaire
  (écran normal, écran effacé, une ligne d'explication).
