# Changelog

## 0.3.2 — carte de notification et clavier

### Ajouté
* **Carte de notification** en bas du lecteur : « Lecture » et le titre au démarrage (effacée au bout de
  2,5 s), « Pause » et le titre tant qu'on est en pause, et chaque action (volume, vitesse, capture, téléchargement…).
  Une action passe devant la pause, qui revient ensuite.

### Corrigé
* **Raccourcis clavier** : les flèches du lecteur marchent quel que soit le widget qui a le focus, y compris
  quand le panneau de playlist est détaché ; le focus revient au lecteur après un double-clic, une boîte de
  dialogue ou un menu. ↑/↓ restent à la liste quand elle a le focus.

## 0.3.1 — thème sombre indépendant du système

### Corrigé
* **Menus illisibles sous Windows en thème clair** : les sous-menus (« Vitesse de lecture », pistes audio,
  sous-titres, format de l'image…) s'ouvraient sur fond blanc avec un texte clair. L'application impose maintenant
  son thème sombre (style Fusion et palette sombre complète) : menus, sous-menus, menus contextuels, boîtes de
  dialogue et info-bulles ne dépendent plus du thème du système.

### Tests
* Un test parcourt tous les menus réels de la barre sur un système simulé en thème clair et vérifie qu'ils restent
  sombres (il échoue si le thème est retiré).

## 0.3.0 — version de publication corrigée

### Corrigé
* **Tests** : un test d'interface instable (téléchargements) ne peut plus être relancé par un événement tardif après son retrait ; la CI est verte.

## 0.2.0 — refonte de la logique, fonctions pro, tests durcis

Le look de l'interface est conservé (mêmes widgets, couleurs, disposition) ; la logique, la persistance et les
performances sont reprises en profondeur, et de nouvelles fonctions de lecteur « pro » sont ajoutées.

### Corrigé (voir `AUDIT_PYPLAYER.md`)
* **Playlists** : identifiants uniques (UUID) — fin des écrasements entre playlists vides ou de même dossier ;
  les sauvegardes ne sont plus rechargées comme des playlists ; suppression par identifiant (plus de playlist
  « Hard Rock » supprimée à la place de « Rock ») ; une playlist reste toujours active.
* **Lecture** : la position est enregistrée pour le média réellement chargé ; plus de reprise à 99 % ; « suivant »
  en fin de liste ne rejoue plus ; mode aléatoire sans répétition, cohérent après suppression/ajout/saut ;
  état muet lu sur la vraie sortie audio ; résolution lue depuis le média (et non la taille du widget) ;
  erreurs de lecture signalées et fichier invalide sauté ; volume sans dérive.
* **Interface** : annulation du dialogue « ajouter un dossier » sans effet ; Échap ne fait que quitter le plein
  écran ; touche muet fonctionnelle ; infobulle play/pause juste ; raccourcis uniques (Ctrl+S ne supprime plus) ;
  aide et raccourcis conformes à la réalité ; doublons de noms de fichiers gérés ; dossier source jamais modifié.
* **Performances** : plus d'écriture de playlist à chaque tick (12,5 ms × plusieurs/s) ; ajout de 300 dossiers en
  quelques ms au lieu de 5 s ; liste de milliers de médias fluide (dessin direct, plus de widget par ligne) ;
  volume écrit par lots, pas à chaque cran.
* **Tri naturel** (`ep2` avant `ep10`), sans planter sur les noms contenant « ² » ou d'autres chiffres Unicode.
* **Windows** (trouvé par le CI Windows) : nom de playlist figé à 1 caractère en tapant « C:\… » à la main ; chemins
  glissés-déposés en « C:/… » mélangés aux « C:\… » ; `file://C:/x` d'une playlist M3U non lu ; instance unique qui
  pouvait perdre les fichiers envoyés par « Ouvrir avec… » (le client ferme maintenant après l'accusé de réception).
* **Reprise** : un second signal « média chargé » ne laisse plus la reprise et l'enregistrement actifs ensemble.
* **Migration** depuis l'ancien format (dates ISO, positions, dernière playlist, volume), avec instantané du v1.

### Ajouté (téléchargements, ligne de commande, mises à jour)
* **Ligne de commande** `pyplayer download | tools | update | self-install` (sans Qt, démarrage instantané), codes de
  sortie précis, sortie JSON, reprise après Ctrl+C ; l'installateur Windows ajoute `pyplayer` au PATH.
* **Onglet « Téléchargements »** (yt-dlp) : file, parallélisme, pause/reprise, reprise automatique, playlists dépliées,
  options avancées, chasse aux liens (presse-papiers), lecture « intelligente » avec bascule sur le fichier local.
* **Lecture en ligne** via yt-dlp (page web → flux), adresses acceptées en ligne de commande et par glisser-déposer.
* **Installation de yt-dlp et FFmpeg** en un clic (versions officielles, SHA-256 vérifié) ; **mises à jour
  automatiques** de l'application (release GitHub, SHA-256, installateur silencieux).
* **Informations détaillées** sur le média (fichier, conteneur, pistes, chapitres, métadonnées, pochette, SHA-256),
  **miniatures** au survol de la barre de progression, **OSD** à la place de la barre d'état, boutons de lecture en gras,
  **réinitialisation** des données, la navigation suit la playlist qui joue (et non celle qui est affichée).

### Ajouté
* Ligne de commande, « Ouvrir avec… », instance unique, glisser-déposer, ouverture d'URL, fichiers récents.
* Vitesse 0,25×–4×, boucle A-B, « aller à l'instant », pistes audio, sous-titres intégrés et externes (.srt/.vtt) avec
  décalage, périphérique audio, formats d'image, capture d'écran, toujours au premier plan, inhibition de la veille.
* Menus contextuels, informations sur le média, réorganisation par glisser-déposer / Alt+↑↓, tri, import/export M3U,
  actualisation depuis le dossier source, lecture audio, mémorisation de la fenêtre, mode « Lecture rapide ».
* Binaire autonome Nuitka (un seul fichier, ~53 Mo sous Linux) et workflow de release sur tag `v*` (Linux + Windows).
* Package `pyplayer` installable (`pyproject.toml`, commande `pyplayer`), journal tournant, CI GitHub Actions.

### Tests
* 287 tests, 94 % de couverture : API, UI hors écran avec lecture réelle (ffmpeg), propriétés (Hypothesis), pannes
  (SIGKILL, disque plein, corruption), migration depuis de vrais fichiers v1, stress de l'UI, paquet ; test de mutation (148/150 = 99 %). État de lecture explicite et testable seul (`api/playback.py`).
  Voir `docs/TESTING.md`.

## 0.1.0
Version initiale.
