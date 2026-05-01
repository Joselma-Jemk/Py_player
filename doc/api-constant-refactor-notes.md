# Pistes d'amélioration pour `constant.py` et l'API

## Objectif

Ce document résume les améliorations prioritaires à apporter à `src/main/python/api/constant.py` et à l'API métier, afin de réduire le couplage, clarifier les responsabilités et rendre les futurs refactors plus sûrs.

## Diagnostic sur `constant.py`

Le module `constant.py` concentre aujourd'hui plusieurs responsabilités qui devraient être séparées :

- configuration runtime et chemins du projet
- recherche récursive de ressources
- préférences utilisateur
- résolution d'icônes et gestion du thème
- caches runtime
- constantes UI comme les couleurs
- formats média supportés

### Problèmes principaux

- Le module mélange logique API et logique UI.
- Des accès disque sont cachés derrière de fausses constantes dynamiques via `__getattr__`.
- Le typage et l'autocomplétion sont affaiblis par les valeurs résolues dynamiquement.
- Le mélange français/anglais dans les noms rend l'API plus difficile à stabiliser.
- Le dict global `preferences` est mutable et partagé implicitement.

## Refactor recommandé pour `constant.py`

### 1. Sortir la logique UI de `api`

Déplacer hors de `api.constant` :

- couleurs UI
- thème
- icônes
- polices

Modules proposés :

- `src/main/python/ui/theme.py`
- `src/main/python/ui/resources.py`
- `src/main/python/ui/icon_registry.py`

### 2. Garder `api.constant` minimal

Conserver dans `api` uniquement les éléments réellement métier ou transverses :

- `VIDEO_EXTENSIONS`
- éventuellement `SUPPORTED_AUDIO_FORMATS`
- quelques chemins runtime si vraiment partagés par plusieurs couches non UI

### 3. Extraire `find_path()`

La fonction `find_path()` est utile, mais ne doit pas vivre avec les couleurs et les icônes.

Modules proposés :

- `src/main/python/api/path_utils.py`
- ou `src/main/python/api/resource_locator.py`

### 4. Supprimer le faux modèle “constantes dynamiques”

Le `__getattr__` utilisé pour exposer des icônes ou chemins calculés doit être remplacé par des fonctions explicites :

- `get_icon_path(...)`
- `get_current_theme_icon(...)`
- `get_font_path()`
- `get_sample_video_path()`

Effets attendus :

- meilleur typage
- autocomplétion plus fiable
- comportement plus lisible
- moins de surprises au runtime

### 5. Encapsuler les préférences

Éviter `preferences = CONFIG.preferences` comme dict global mutable.

Approches préférables :

- un objet typé immuable
- une dataclass de préférences
- ou des getters explicites via `CONFIG`

### 6. Uniformiser le naming

Exemples de dette de nommage actuelle :

- `py_player_icone`
- `chemin_video`
- `PRINCIPAL_COLOR`
- `ICON_DARK_*`

Décision à prendre :

- soit API publique en anglais
- soit API publique en français

Le plus important est d'arrêter le mélange.

## Diagnostic sur l'API métier

Les deux modules les plus lourds sont :

- `src/main/python/api/playlist.py`
- `src/main/python/api/pyplayer_manager.py`

### Problème de `Playlist`

`Playlist` mélange actuellement :

- modèle métier
- navigation
- état courant
- autosave
- sérialisation JSON
- chargement depuis disque
- validation de fichiers

Cela rend la classe difficile à tester, à faire évoluer et à raisonner.

### Problème de `PlaylistManager`

`PlaylistManager` mélange actuellement :

- registre de playlists
- gestion de la playlist active
- config
- last played
- nettoyage de backups
- persistance

Le module joue à la fois le rôle de service applicatif, repository, registre et orchestrateur runtime.

## Refactor recommandé pour l'API

### 1. Découper `Playlist`

Découpage recommandé :

- `playlist_model.py` pour l'entité
- `playlist_navigation.py` pour `next/previous/shuffle`
- `playlist_serializer.py` pour `to_dict/from_dict`
- `playlist_repository.py` pour `save/load`

### 2. Découper `PlaylistManager`

Découpage recommandé :

- `playlist_registry.py`
- `manager_config_store.py`
- `last_played_store.py`
- `backup_cleaner.py`

### 3. Réduire les effets de bord dans `__init__`

Aujourd'hui, le manager :

- charge la config
- charge les playlists
- nettoie les backups
- crée une playlist par défaut
- choisit une playlist active

Mieux :

```python
manager = PlaylistManager(data_dir=...)
manager.load()
```

Effets attendus :

- tests plus simples
- bootstrap plus clair
- moins de logique implicite au démarrage

### 4. Clarifier les erreurs métier

Beaucoup de méthodes retournent seulement `True` ou `False` et loguent en silence.

Mieux :

- exceptions métier explicites
- ou objets de retour structurés

Par exemple :

- `PlaylistNotFoundError`
- `InvalidPlaylistStateError`
- `PersistenceError`

### 5. Renforcer le typage de l'API publique

Exemples actuels à améliorer :

- `volume` sans annotation explicite
- `all_playlist` au singulier alors qu'il retourne un dict
- `all_video`
- `p_state`

Renommages recommandés à moyen terme :

- `all_playlist` -> `playlists`
- `all_video` -> `videos`
- `p_state` -> `state`

## Ordre de refactor recommandé

Pour avancer sans tout casser :

1. sortir les constantes UI de `api.constant`
2. figer une petite API publique stable dans `api/__init__.py`
3. extraire la persistance de `Playlist`
4. extraire config / last played / backups de `PlaylistManager`
5. renommer progressivement les symboles legacy

## Premier refactor conseillé

Le meilleur point d'entrée est simple et peu risqué :

- créer `api/media_formats.py`
- créer `api/path_utils.py`
- créer `ui/theme.py`
- créer `ui/icon_registry.py`
- réduire fortement `api/constant.py`

## Résultat visé

À terme :

- `api` ne dépend plus de préoccupations UI
- les modules sont plus petits et plus lisibles
- les tests unitaires sont plus simples à écrire
- les effets de bord au démarrage sont réduits
- le typage et l'autocomplétion deviennent fiables
