# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contenu de l'Aide (lot F ; demande de l'auteur, 2026-11-11 : « exhaustive et explicite », modele d'omega-log :
une section repliable par menu, sa fonction et le detail). Le meme contenu sert a l'ecran et a l'export HTML.

Balises : [b]...[/b] seulement (gras), converties pour l'export. Les mots sont ceux de l'interface (carte
d'identite, espace partage, noms des menus et des boutons)."""
from __future__ import annotations

from omega_connect.shared.i18n import N_

SHORTCUTS = (
    (N_("Haut / Bas"), N_("Passer d'un élément à l'autre (lignes d'un tableau, boutons)")),
    (N_("Tab / Maj+Tab"), N_("Passer d'une zone de l'écran à l'autre")),
    (N_("Entrée / Clic"), N_("Activer le bouton choisi ; dans une liste à cocher, cocher ou décocher la ligne")),
    (N_("Espace"), N_("Cocher ou décocher la ligne choisie (Synchronisation)")),
    (N_("Échap"), N_("Revenir à l'écran précédent")),
    ("a", N_("Cette aide, depuis n'importe quel écran")),
    ("s", N_("Réglages, depuis n'importe quel écran")),
    ("t", N_("Thème suivant (enregistré)")),
    ("r", N_("Redessiner l'écran et afficher la taille du terminal")),
    ("q", N_("Quitter (avec confirmation)")),
    (N_("Ctrl+P"), N_("Commandes : thème, capture d'écran (SVG, dans le dossier des captures), quitter")),
)

QUICKSTART = N_(
    "omega-connect relie entre elles les applications omega (omega-serv, omega-fire, omega-jail…) installées sur "
    "cette machine et sur les machines de votre réseau. Il montre ce qui est relié ou pas, et remet en place ce "
    "qui manque, toujours après vous avoir montré ce qu'il va faire.\n\n"
    "1. [b]Scanner[/b] : cherche les applications de cette machine. Ajoutez vos autres machines (proposées "
    "d'après vos profils Unison, ~/.ssh/config et known_hosts, ou saisies à la main) : elles sont jointes par "
    "SSH avec vos clés, rien n'y est installé.\n"
    "2. [b]Registre[/b] : la liste de toutes les applications de toutes les machines, avec leur état. Une "
    "application trop ancienne ou mal installée se met à jour ou se réinstalle depuis cet écran.\n"
    "3. [b]Synchronisation[/b] : cochez ce qui doit être relié, puis « Synchroniser » ; chaque machine montre son "
    "plan avant d'agir et demande son mot de passe une seule fois.\n"
    "4. [b]Liaisons[/b] : voir ce qui est relié ou pas, sur toutes les machines. [b]Dashboard[/b] : la vue "
    "d'ensemble, en cadres.\n"
    "5. [b]Réparer[/b] : la liste de tout ce qui ne va pas ; choisissez une ligne, ou « Tout réparer ».\n"
    "6. [b]Rapport[/b] : un document complet (texte, JSON ou page HTML) à garder ou à transmettre.")

SECTIONS: tuple[tuple[str, str], ...] = (
    (N_("Registre — toutes les applications et leur état"), N_(
        "Affiche, pour chaque machine (celle-ci et celles du réseau), chaque application omega trouvée : son "
        "instance ou service, sa version, son état et son dossier. Le résumé en haut compte les états.\n\n"
        "- [b]Mettre à jour le registre[/b] : refait le scan sur place (cette machine, puis les machines du "
        "réseau déjà connues), sans changer d'écran.\n"
        "- [b]Mettre à jour l'application[/b] : sur une ligne « Ancienne version » d'une machine du réseau, "
        "installe la dernière version publiée (Release GitHub de l'application, empreinte vérifiée avec sha.txt "
        "avant tout envoi). Le plan s'affiche d'abord ; rien d'autre n'est fait.\n"
        "- [b]Réinstaller l'application[/b] : même bouton sur une ligne « Installation inachevée » (son "
        "install.sh ne s'est pas terminé) ; la même version est réinstallée.\n"
        "- Sur cette machine-ci, une mise à jour se fait comme le dit la section « Mise à jour » du README de "
        "l'application.\n"
        "- Surlignez une ligne : l'explication de son état et ses écarts s'affichent en dessous.")),
    (N_("Scanner — trouver les applications, ajouter des machines"), N_(
        "- [b]Cette machine[/b] : cherche les applications omega (dossier personnel, services systemd, OpenRC ou "
        "runit, /srv, registre des instances d'omega-serv). Jamais de lien symbolique suivi, jamais de montage "
        "réseau parcouru.\n"
        "- [b]Machines proposées[/b] : celles que cet ordinateur sait déjà joindre (profils Unison, ~/.ssh/config, "
        "known_hosts). Choisissez une ligne puis « Scanner la machine choisie ».\n"
        "- [b]Saisie manuelle[/b] : utilisateur@machine (nom ou adresse), puis « Scanner cette machine ».\n"
        "- [b]Première connexion[/b] : l'empreinte de la clé de la machine est montrée ; vérifiez-la, puis "
        "acceptez. Une clé qui a CHANGÉ est refusée (machine réinstallée, ou usurpation).\n"
        "- [b]Machines connues[/b] : « Rescanner les machines connues », ou « Retirer cette machine » (elle sort "
        "du registre ; rien n'est modifié sur elle).\n"
        "- Le scan d'une machine du réseau est envoyé en mémoire par SSH, en lecture seule : rien n'y est "
        "installé ni écrit, aucun mot de passe n'est demandé (Python 3.10 ou plus récent requis là-bas).")),
    (N_("Liaisons — ce qui est relié ou pas"), N_(
        "Montre chaque lien entre applications, sur toutes les machines, avec son état et sa provenance (Local, "
        "ou Réseau — nom de la machine) : journaux d'omega-serv et de magnet lus par les jails d'omega-jail, pont "
        "fail2ban vers la liste noire d'omega-serv, liste protégée, liste noire partagée, fichiers d'omega-jail "
        "dans fail2ban, cartes d'identité, espace partagé.\n\n"
        "- Surlignez une ligne : ses contrôles s'affichent en dessous ; « Détail du lien » les montre tous, avec "
        "la commande de chaque correction (« Copier les commandes »).\n"
        "- Cet écran montre seulement : ce qui est « à réparer » se corrige dans le menu Réparer.")),
    (N_("Synchronisation — relier les applications"), N_(
        "Une seule liste : toutes vos machines et leurs applications (les machines du réseau sont rescannées à "
        "l'ouverture). Cochez des lignes (Entrée ou Espace), puis :\n"
        "- [b]Synchroniser la sélection[/b], ou [b]Synchroniser tout[/b].\n"
        "- [b]Cette machine[/b] : un seul plan, affiché avant d'agir — cartes d'identité qui manquent (créées "
        "par chaque application, sous son compte), puis espace partagé (groupe omega-synchro, dossiers, copie "
        "des cartes, accès des services). Un seul mot de passe administrateur.\n"
        "- [b]Machine du réseau[/b] : son plan est calculé sur elle et affiché ; « Synchroniser <machine> » le "
        "lance depuis ici : l'interface laisse la place au terminal, la machine demande elle-même son mot de "
        "passe, une fois ; Entrée ramène à l'interface, qui montre le résultat.\n"
        "- Les machines passent une à une : cette machine d'abord, puis le réseau.\n"
        "- Une application trop ancienne, inachevée ou injoignable ne se coche pas : la ligne dit où aller.\n"
        "- [b]Lire avec sudo[/b] : si votre session ne peut pas encore lire l'espace partagé (le groupe "
        "omega-synchro ne compte qu'après une reconnexion), lecture seule avec sudo.\n"
        "- [b]Détail[/b] : ce qu'omega-connect a créé (registre de l'espace partagé) et les retraits possibles.")),
    (N_("Dashboard — vue d'ensemble"), N_(
        "Une vue d'ensemble en cadres, comme un tableau de bord web. Rien n'est modifié depuis cet écran.\n\n"
        "- [b]Machines[/b], [b]Applications[/b], [b]Liaisons[/b], [b]Espace partagé[/b] : les compteurs, avec "
        "les mêmes états que le Registre et les Liaisons.\n"
        "- [b]Liaisons par type[/b] : pour chaque type de liaison, combien sont OK sur combien.\n"
        "- [b]Cette machine / Réseau[/b] : les mêmes chiffres, côte à côte.\n"
        "- [b]Top 5[/b] (top 3 sur un petit écran) : machines à réparer, liaisons à réparer, versions en retard, "
        "scans les plus anciens (machines du réseau).\n\n"
        "Cette machine est vérifiée à l'ouverture, puis régulièrement tant que l'écran est ouvert ; "
        "« Actualiser » relance la vérification. Les machines du réseau montrent leur dernier scan (menu Scanner "
        "pour les relire). Pour corriger : menu Réparer.")),
    (N_("Réparer — tout ce qui ne va pas"), N_(
        "La liste de tout ce qui ne va pas, sur toutes les machines (les machines du réseau sont rescannées à "
        "l'ouverture) : machine, problème, état, et qui le corrige.\n\n"
        "- [b]Réparer la ligne choisie[/b] : ouvre le plan de la machine. Cette machine : les commandes des "
        "applications elles-mêmes (omega-jail pour ce qu'il pose dans fail2ban, omega-serv pour les droits de "
        "son var/, chaque application pour sa carte d'identité), puis l'espace partagé. Machine du réseau : les "
        "mêmes corrections, plus les commandes qu'aucune application ne sait lancer, lancées SUR la machine "
        "depuis ici (seulement celles annoncées dans le plan).\n"
        "- [b]Tout réparer[/b] : les machines une à une (mettre à jour d'abord, puis réparer).\n"
        "- [b]Détail[/b] : tous les contrôles de la ligne choisie.\n"
        "- [b]Copier les commandes[/b] (plan de cette machine) : presse-papiers du système (xclip, xsel, "
        "wl-copy) ; sinon les commandes s'affichent en clair dans le terminal, à sélectionner à la souris.\n"
        "- omega-connect ne réécrit jamais le fichier d'une autre application : il lance sa commande.")),
    (N_("Rapport — un document complet"), N_(
        "Établi à l'instant (les machines du réseau sont rescannées avant) : bilan, liste précise de ce qu'il "
        "reste à faire (machine, quoi, quel menu), registre de toutes les applications, machines du réseau, "
        "applications de cette machine en détail, liaisons de chaque machine, espace partagé et son registre.\n\n"
        "- Export en texte, JSON ou page HTML (thème au choix, par défaut celui des Réglages), dans le dossier "
        "des exports.\n"
        "- En ligne de commande : omega-connect rapport --format html --enregistrer.")),
    (N_("Réglages"), N_(
        "- [b]Thème de l'interface[/b] (aussi touche t) et [b]thème des exports[/b] : enregistrés.\n"
        "- [b]Dossier des exports[/b] et [b]dossier des captures d'écran[/b] : par défaut var/exports/ et "
        "var/screenshots/ du dossier d'omega-connect ; un chemin complet, ou vide pour revenir au défaut.\n"
        "- [b]Vider le dossier des exports / des captures[/b] : après confirmation, supprime le contenu du "
        "dossier configuré (le dossier reste). Refusé pour un dossier système, personnel, ou celui "
        "d'omega-connect lui-même ; jamais de mot de passe demandé.\n"
        "- Tout est enregistré dans var/settings.json.")),
    (N_("Machines du réseau, mises à jour et sécurité"), N_(
        "- [b]Connexion[/b] : SSH avec VOS clés seulement ; omega-connect ne demande jamais le mot de passe "
        "SSH. Une clé protégée par une phrase secrète doit être chargée dans l'agent SSH (ssh-add).\n"
        "- [b]Mot de passe administrateur[/b] : seulement quand une action le demande (synchroniser, réparer, "
        "mettre à jour), une fois par machine, tapé par vous dans le terminal ; omega-connect ne le voit "
        "jamais.\n"
        "- [b]Ce qui va sur une machine du réseau[/b] : pour un scan, rien (programme en mémoire) ; pour une "
        "action, un dossier privé temporaire (programme et archives), effacé à la fin.\n"
        "- [b]Mises à jour[/b] : depuis la Release GitHub de chaque application (kraynux/<application>, "
        "étiquette v<version>) ; l'empreinte est vérifiée avec sha.txt avant tout envoi, puis de nouveau sur la "
        "machine. omega-fire : l'ancienne installation est mise de côté (son var/ appartient à root), puis son "
        "install.sh reprend réglages et données. Les autres : extraction par-dessus (l'état vivant n'est pas "
        "dans l'archive), puis leur install.sh.\n"
        "- [b]Jamais d'application lancée qui pourrait demander un mot de passe sans terminal[/b] : un échec "
        "silencieux de sudo compte comme une tentative et peut verrouiller le compte quelques minutes.")),
    (N_("États — ce que veut dire chaque mot"), N_(
        "[b]Applications[/b] :\n"
        "- ● Reliée : dans l'espace partagé, à jour.\n"
        "- ◐ Inscrite : a sa carte d'identité, pas encore dans l'espace partagé (Synchronisation).\n"
        "- ○ Détectée : trouvée, sans carte d'identité (Synchronisation la lui crée).\n"
        "- ▲ À réparer : un écart (Réparer).\n"
        "- ◌ Ancienne version : trop ancienne pour omega-connect (Registre → Mettre à jour l'application).\n"
        "- ◇ Installation inachevée : son install.sh ne s'est pas terminé (Registre → Réinstaller "
        "l'application).\n"
        "- ✕ Injoignable : la machine ne répond plus (Scanner → Rescanner).\n\n"
        "[b]Liaisons[/b] : OK ; à réparer ; à réparer (bloquant) ; absent (rien à relier, par exemple "
        "omega-jail non installé) ; non vérifiable (lecture impossible depuis votre session).")),
    (N_("Carte d'identité et espace partagé"), N_(
        "- [b]Carte d'identité[/b] : un petit fichier (var/omega-jeton.json) que chaque application écrit à son "
        "installation : quelle application, quelle version, quel identifiant, sur quelle machine. Lisible par "
        "tous, jamais modifiable par les autres comptes.\n"
        "- [b]Espace partagé[/b] : /var/lib/omega-synchro, groupe omega-synchro, où seul root écrit ; "
        "omega-connect y recopie les cartes d'identité et la description de chaque application, pour qu'elles se "
        "trouvent entre elles, même quand omega-connect n'est pas lancé.\n"
        "- Tout ce qu'omega-connect crée est inscrit au registre de l'espace partagé : un retrait ne défait que "
        "ce qui y est inscrit.")),
    (N_("Ligne de commande"), N_(
        "omega-connect.sh <commande> (sans commande : l'interface).\n"
        "- scanner [utilisateur@machine] [--liste] [--retirer MACHINE]\n"
        "- synchroniser [--machine MACHINE | --toutes-machines] [--simulation] [--oui]\n"
        "- mettre-a-jour --machine MACHINE | --toutes-machines [--simulation] [--oui]\n"
        "- reparer [--machine MACHINE | --toutes-machines] [--simulation] [--oui]\n"
        "- verifier [--format json], detecter [--format json]\n"
        "- rapport [--format texte|json|html] [--enregistrer]\n"
        "- etablir, retirer --tout : l'espace partagé, plan affiché avant tout lancement.\n"
        "--simulation montre le plan sans rien lancer ; --oui lance sans poser la question.")),
    (N_("Fichiers d'omega-connect"), N_(
        "Tout vit dans le dossier d'omega-connect, sous var/ :\n"
        "- parc.json : registre des machines du réseau (dernier scan, adresses, empreinte).\n"
        "- settings.json : réglages.\n"
        "- exports/ et screenshots/ : par défaut (voir Réglages).\n"
        "- declaration.json : déclaration d'utilisateur anonyme (si vous l'avez faite).")),
    (N_("Aide, export et contact"), N_(
        "- [b]Exporter l'aide en HTML[/b] : toute cette aide, dans une page, thème au choix, dans le dossier "
        "des exports.\n"
        "- [b]Contact et support[/b] : payer un café (PayPal), se déclarer utilisateur anonyme (une seule fois), "
        "contacter le support (mail et formulaire du site), vérifier les mises à jour.")),
)
