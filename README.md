# PyPlayer

Lecteur vidéo et audio local, minimaliste et rapide, écrit en Python avec **PySide6 (Qt 6)** et FFmpeg.
Interface sombre épurée, playlists persistantes, reprise de lecture fichier par fichier.

## Installation

```bash
pip install .                 # ou, pour développer : pip install -e ".[dev]"
pyplayer                      # ou : python -m pyplayer
```

Prérequis : Python ≥ 3.10. Qt Multimedia utilise son backend FFmpeg (déjà embarqué dans les roues PySide6).

## Utilisation

```text
pyplayer [options] [fichiers | dossiers | playlists .m3u/.m3u8/.pls | URL …]

  -a, --enqueue        ajoute à la playlist active au lieu de lire tout de suite
  -n, --new-instance   n'utilise pas la fenêtre déjà ouverte
      --fullscreen     démarre en plein écran
      --debug          journaux détaillés
  -v, --version
```

### « Ouvrir avec… » et instance unique

* Un fichier ouvert depuis l'explorateur (ou `pyplayer film.mkv`) est lu immédiatement ; si PyPlayer est déjà
  ouvert, le fichier lui est transmis (aucune seconde fenêtre).
* Ouvrir **un seul fichier** met aussi en file les médias du même dossier, dans l'ordre naturel
  (`ep2` avant `ep10`) : l'épisode suivant se lance tout seul. Réglage `open_siblings` dans `settings.json`.
* Glisser-déposer des fichiers ou dossiers sur la fenêtre pour les lire ; sur la liste de lecture pour les ajouter.
* **Linux** : installez `packaging/pyplayer.desktop` (`~/.local/share/applications/`) pour que PyPlayer
  apparaisse dans « Ouvrir avec… » pour les formats vidéo/audio.
* **Windows** : associez les extensions à `pyplayer-gui.exe` (Propriétés → Ouvrir avec → Choisir une autre application).

## Fonctions

| | |
|---|---|
| **Lecture** | vidéo et audio (MP4, MKV, WebM, AVI, MOV, TS, FLAC, MP3, OGG, Opus…), URL réseau, vitesse 0,25× → 4×, boucle A-B, « aller à l'instant », capture d'écran |
| **Reprise** | position mémorisée pour chaque fichier (≥ 5 s, hors fin de média) ; reprise automatique à la réouverture |
| **Pistes** | choix de la piste audio, sous-titres intégrés **et** externes (`.srt`/`.vtt`, chargés automatiquement s'ils portent le nom du film), décalage des sous-titres, choix du périphérique de sortie |
| **Image** | ajuster / remplir / étirer, plein écran avec contrôles qui réapparaissent à la souris, toujours au premier plan, veille d'écran inhibée pendant la lecture |
| **Playlists** | plusieurs playlists persistantes, 4 modes (normal, boucle fichier, boucle liste, aléatoire sans répétition), tri naturel/nom/date/taille/durée, glisser-déposer pour réordonner, import/export M3U, actualisation depuis le dossier source |
| **Confort** | fichiers récents, menu contextuel (vidéo et liste), informations sur le média, taille/position de la fenêtre mémorisées, molette = volume, touches multimédia |
| **Robustesse** | écriture atomique des fichiers, instantanés rotatifs, quarantaine des fichiers corrompus, migration automatique des playlists de l'ancienne version |

### Raccourcis

| Touche | Action | Touche | Action |
|---|---|---|---|
| `Espace` / clic | lecture / pause | `Ctrl+O` | ajouter des fichiers |
| `←` `→` (`Maj` : ±60 s) | ±10 s | `Ctrl+Maj+O` | ouvrir et lire un fichier |
| `↑` `↓` / molette | volume | `Ctrl+D` | ajouter un dossier |
| `M` | muet | `Ctrl+U` | ouvrir une adresse réseau |
| `[` `]` `⌫` | plus lent / plus rapide / normal | `Ctrl+N` | nouvelle playlist |
| `L` | boucle A-B | `Ctrl+P` | afficher/masquer la liste |
| `Ctrl+G` | aller à l'instant | `F2` / `F5` | renommer / actualiser la playlist |
| `A` / `V` | piste audio / sous-titres suivants | `Alt+↑` `Alt+↓` | déplacer dans la liste |
| `Z` / `X` | sous-titres −/+ 0,1 s | `Suppr` | retirer de la liste |
| `S` | capture d'écran | `Ctrl+I` | informations |
| `F`, `F11`, double-clic | plein écran | `Ctrl+←` / `Ctrl+→` | précédent / suivant |
| `Échap` | quitter le plein écran | `F1` | aide |

## Données utilisateur

Dans `~/.pyplayer` (surchargeable avec `PYPLAYER_HOME`) :

```
playlists/<nom>-<id8>.json    une playlist par fichier
playlists/backups/            5 instantanés par playlist (jamais rechargés comme playlists)
settings.json                 volume, fenêtre, récents, options
resume.json                   positions de reprise (1 000 entrées max)
pyplayer.log                  journal tournant
```

## Architecture

```
src/pyplayer/
├── __main__.py        ligne de commande, instance unique, gestion des erreurs
├── api/               logique métier — AUCUNE dépendance à Qt (testable seule)
│   ├── playlist.py    liste ordonnée, vidéo courante, modes de lecture, sérialisation
│   ├── manager.py     chargement/sauvegarde, playlist active, sauvegardes, migration
│   ├── resume.py      mémoire de reprise (indépendante des playlists)
│   ├── settings.py    réglages typés et validés
│   ├── media.py       extensions, tri naturel, parcours de dossiers
│   ├── m3u.py · subtitles.py · io_utils.py · paths.py · video.py · logging_setup.py
└── ui/                interface Qt
    ├── main_window.py fenêtre et orchestration de la lecture
    ├── widget/        lecteur, barre d'outils, menus, panneau de playlists, barre d'état
    ├── dialogs.py · theme.py · power.py · single_instance.py
```

Principes : la vidéo courante est référencée par objet (jamais par index ou par nom) ; les playlists ne sont
réécrites que lorsqu'elles changent (jamais à chaque tick de lecture) ; la position de lecture est enregistrée
pour le média **réellement chargé**.

## Développement

```bash
pip install -e ".[dev]"
pytest                              # 236 tests, 93 % de couverture (voir docs/TESTING.md)
PYPLAYER_THOROUGH=1 pytest          # ×10 exemples pour les tests à base de propriétés
pytest --cov=pyplayer
python -m pyflakes src
python tools/mutation_check.py      # test de mutation de l'API
```

Les tests couvrent notamment : machine à états aléatoire de la playlist (Hypothesis), fuzzing des chargeurs JSON,
coupure brutale (`SIGKILL`) en pleine écriture, disque plein, corruption aléatoire des fichiers, migration depuis de
vrais fichiers de l'ancienne version, 8 séquences de 120 actions utilisateur aléatoires, clavier, glisser-déposer,
instance unique et construction du paquet.

## Licence

MIT — voir `Licence.txt`.
