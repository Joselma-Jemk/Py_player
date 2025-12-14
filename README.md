# README.md - PyPlayer

## 🎯 Vue d'ensemble

**PyPlayer** est un lecteur vidéo minimaliste développé en Python avec PySide6 (Qt6). Il permet de gérer et lire des vidéos locales avec une interface épurée et une gestion avancée des playlists.

## 🏗️ Architecture technique

### Structure du projet
```
src/main/python/
├── api/                     # Logique métier
│   ├── video.py             # Objet vidéo et état
│   ├── playlist.py          # Gestion des playlists
│   ├── pyplayer_manager.py  # Manager central
│   ├── test_api.py          # Tests API
│   └── generate.py          # Générateur / utilitaire
│
├── ui/                      # Interface utilisateur
│   ├── main_window.py       # Fenêtre principale
│   └── widget/              # Composants UI
│       ├── menu_bar.py      # Barre de menu
│       ├── tool_bar.py      # Barre d’outils
│       ├── dock_widget.py   # Panneau playlist
│       ├── player.py        # Lecteur vidéo
│       ├── staturbar_widget.py # Barre d’état
│       └── constant.py      # Constantes UI
│
└──__init__.py

```

### Technologies utilisées
- **Python 3.13** - Langage principal
- **PySide6** - Interface Qt6
- **FFmpeg** - Backend média (forcé via `QT_MEDIA_BACKEND="ffmpeg"`)
- **Material Icons** - Police d'icônes
- **JSON** - Sauvegarde des playlists

## 🎮 Fonctionnalités principales

### Gestion vidéo
- Support des formats: MP4, AVI, MKV, MOV, WEBM, WMV, FLV, MPEG, MPG, M4V (tout les formats supportés par FFmpeg)
- Métadonnées automatiques (résolution, durée)
- Sauvegarde d'état (position, volume, muet)

### Système de playlists
- Playlists basées sur dossiers
- Sauvegarde automatique en JSON
- Navigation intelligente
- Quatre modes de lecture:
  - Normal (lecture unique)
  - Boucle sur fichier
  - Boucle sur playlist
  - Lecture aléatoire

### Interface utilisateur
- Interface dark mode avec thème personnalisable
- Panneau playlist coulissant
- Barre de contrôle minimaliste
- Mode plein écran intelligent
- Curseur auto-masqué en plein écran

## 🔌 API Core

### Video
```python
class Video:
    """Représente un fichier vidéo avec état de lecture."""
    - Métadonnées: nom, taille, résolution, durée
    - État: position, volume, muet, progression
    - Sérialisation: to_dict()/from_dict()
```

### Playlist
```python
class Playlist:
    """Gestionnaire de collection de vidéos."""
    - Navigation: suivant/précédent selon mode
    - Modes: NORMAL, LOOP_ONE, LOOP_ALL, SHUFFLE
    - Sauvegarde: auto-save sur changements
    - Recherche: par nom, chemin, index
```

### PlaylistManager
```python
class PlaylistManager:
    """Gestionnaire central de toutes les playlists."""
    - Chargement automatique au démarrage
    - Sauvegarde de configuration
    - Nettoyage automatique des backups
    - Volume global persistant
```

## 🚀 Points techniques remarquables

### 1. Gestion d'état
Chaque vidéo conserve son état (position, volume, muet) entre les sessions. L'état est sauvegardé automatiquement.

### 2. Mode plein écran intelligent
- Masquage automatique des barres d'interface
- Curseur qui se cache après 3s d'inactivité
- Curseur réapparaît au mouvement de souris
- Synchronisation avec l'action du menu

### 3. Navigation avancée
- Quatre modes de lecture avec comportements différents
- Historique de navigation en mode shuffle
- Gestion des fichiers manquants
- Validation automatique des dossiers

### 4. Sérialisation robuste
- Versioning des données
- Validation des fichiers au chargement
- Gestion des erreurs avec fallback sur backups
- Rapports de validation détaillés

## 🎯 Raccourcis clavier

### Navigation
| Raccourci | Action |
|-----------|--------|
| **Espace** | Lire/Pause |
| **F11** | Plein écran |
| **Échap** | Quitter plein écran |
| **Ctrl+P** | Afficher/Masquer playlist |
| **Ctrl+→** | Vidéo suivante |
| **Ctrl+←** | Vidéo précédente |

### Fichiers
| Raccourci | Action |
|-----------|--------|
| **Ctrl+O** | Ouvrir fichier |
| **Ctrl+D** | Ouvrir dossier |
| **Ctrl+Q** | Quitter |

### Playlists
| Raccourci | Action |
|-----------|--------|
| **Ctrl+N** | Nouvelle playlist |
| **Ctrl+S** | Supprimer playlist |

### Volume
| Raccourci | Action |
|-----------|--------|
| **Flèche Haut** | Volume +2% |
| **Flèche Bas** | Volume -2% |
| **Touche Muet** | Activer muet |
| **Volume+/-** | Volume système |

## 🔧 Installation & Développement

### Dépendances
```bash
pip install PySide6
# FFmpeg doit être installé séparément
```

### Points d'extension
1. **Plugins de décodage** - Ajouter support nouveaux formats
2. **Thèmes** - Système de thèmes interchangeables
3. **Streaming** - Support URL réseau
4. **Éditeur playlist** - Interface drag & drop avancée

## 📝 Notes pour développeurs

### Patterns utilisés
- **Observer**: Signaux Qt pour mise à jour UI
- **State**: VideoState pour état de lecture
- **Repository**: PlaylistManager pour gestion données
- **Strategy**: Modes de lecture implémentés comme stratégies

### Bonnes pratiques
- Tous les chemins utilisent `pathlib.Path`
- Gestion d'erreurs avec logging structuré
- Sérialisation versionnée pour compatibilité
- UI responsive avec styles CSS

### Points d'attention
1. **Performance**: Chargement asynchrone des thumbnails si ajoutés
2. **Mémoire**: Nettoyage des objets UI supprimés
3. **Compatibilité**: Tester avec différentes versions FFmpeg
4. **Internationalisation**: Préfixer tous les textes UI
