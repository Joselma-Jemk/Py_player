# TODO — PyPlayer

## Points d'amélioration identifiés

1. **Éviter la dépendance fragile à `parents[3]` / `parents[5]`**
   - Détecter dynamiquement la racine du projet au lieu d'indices fixes.
   - Utiliser des marqueurs stables (ex: `requirements.txt`, `README.md`, `src/main`).

2. **Réduire le travail fait à l'import du module**
   - Éviter de résoudre toutes les icônes à l'import si possible.
   - Préférer un chargement à la demande (lazy) ou un cache central.

3. **Supprimer la duplication massive des constantes d’icônes**
   - Générer les chemins via une liste centrale / map.
   - Éviter les dizaines d’affectations manuelles `ICON_*`.

4. **Limiter le coût de `find_path()`**
   - Favoriser les chemins directs avant la recherche récursive.
   - Ajouter cache et/ou bornes de profondeur plus strictes.

5. **Améliorer les logs/erreurs**
   - Remplacer `print()` par `logging`.
   - Clarifier les messages de fallback.

6. **Mieux valider les préférences**
   - Valider `theme` (`light|dark`) et `icon_number` (entier positif).
   - Option: dataclass de configuration.

7. **Ajouter des tests unitaires ciblés**
   - Résolution racine projet.
   - Fallback preferences absentes/corrompues.
   - Résolution icônes light/dark + fallback.
   - Robustesse `find_path(safe=True)`.

8. **Extraire la configuration vers un module dédié (`config.py`)**
   - Déplacer le chargement/validation des préférences hors de `constant.py`.
   - Garder `constant.py` centré sur constantes + helpers.

9. **Ajouter une invalidation explicite des caches runtime**
   - Exposer une fonction type `reset_runtime_caches()`.
   - Réinitialiser `_FIND_PATH_CACHE`, `_ICON_CACHE`, `_LAZY_MISC_CACHE`.

10. **Améliorer la stratégie de logs**
   - Ajouter rotation (`RotatingFileHandler`) et taille max.
   - Garder le fichier dans le dossier runtime (`pyplayer_directory()`).

11. **Durcir `find_path` côté sécurité/périmètre**
   - Ajouter option `allowed_root` pour empêcher de sortir d'un périmètre.
   - Limiter la profondeur par défaut dans certains cas.

12. **Sécuriser les écritures JSON API (save) par écriture atomique**
   - Écrire d'abord dans un fichier temporaire puis `replace()`.
   - Éviter les fichiers JSON partiellement écrits en cas de crash/interruption.

13. **Ajouter des tests pytest headless persistants**
   - Créer des tests unitaires automatisables sans UI.
   - Exécuter en environnement serveur (sans écran).

14. **Ajouter un healthcheck CLI de déploiement headless**
   - Vérifier config, assets essentiels, permissions runtime, logs.
   - Retourner un statut clair pour CI/CD.

## Convention de typage (Python 3.13)

- Utiliser le typage moderne natif : `int | None`, `list[str]`, `dict[str, str]`.
- Éviter `Optional`, `List`, `Dict` du module `typing`.

---

## En cours maintenant

- [x] Point 1 — Démarré
- [x] Point 1 — Terminé
- [x] Point 2 — Démarré
- [x] Point 2 — Terminé
- [x] Point 3 — Démarré
- [x] Point 3 — Terminé
- [x] Point 4 — Démarré
- [x] Point 4 — Terminé
- [x] Point 5 — Démarré
- [x] Point 5 — Terminé
- [x] Point 6 — Démarré
- [x] Point 6 — Terminé
- [x] Point 8 — Démarré
- [x] Point 8 — Terminé
- [x] Point 9 — Démarré
- [x] Point 9 — Terminé
- [x] Point 10 — Démarré
- [x] Point 10 — Terminé
- [x] Point 11 — Démarré
- [x] Point 11 — Terminé
- [x] Point 12 — Démarré
- [x] Point 12 — Terminé

## Notes d'implémentation (Point 1)

- `PROJECT_ROOT` n'utilise plus `parents[5]`.
- Ajout de `_find_project_root(start_path)` qui remonte dynamiquement les dossiers.
- Détection par marqueurs stables :
  - prioritaire : `requirements.txt` + `README.md`
  - fallback : `requirements.txt`
- `MAIN_DIR`, `ICONS_DIR`, `RESOURCES_DIR` sont dérivés de `PROJECT_ROOT`.
- Vérification runtime OK (import module + résolution chemins/icônes).

## Notes d'implémentation (Point 2)

- Suppression de la résolution eager des constantes `ICON_*` à l'import.
- Introduction de `_ICON_SPECS` (nom constante -> `(icon_name, theme)`).
- Introduction de `_ICON_CACHE` pour mémoïser les résolutions d'icônes.
- Ajout de `__getattr__` module-level pour résolution lazy des attributs `ICON_*`.
- Passage de `icon_directory`, `chemin_video`, `font_dir` en lazy + cache (`_LAZY_MISC_CACHE`).
- Compatibilité conservée : les appels existants `constant.ICON_PLAY` etc. restent valides.
- Vérification runtime OK (imports + accès aux attributs historiques).

## Notes d'implémentation (Point 3)

- Suppression de la map `_ICON_SPECS` écrite à la main.
- Ajout de listes sources `_LIGHT_ICON_NAMES` et `_DARK_ICON_NAMES`.
- Génération automatique des constantes via `_build_icon_specs()`.
- Ajout de `_ICON_CONST_ALIASES` pour les cas de nommage spéciaux (ex: `check_circle` -> `ICON_PLAYED`).
- Réduction de duplication et meilleure maintenabilité : ajout/retrait d'icône = modifier une liste, pas des dizaines de lignes.
- Vérification runtime OK (`ICON_PLAY`, `ICON_DARK_PLAY`, `ICON_PLAYED`, etc.).

## Notes d'implémentation (Point 4)

- Ajout d'un cache global `_FIND_PATH_CACHE` pour `find_path`.
- Clé de cache basée sur les paramètres structurants (`name`, `parent_dir`, `max_depth`, etc.).
- Ajout d'un fast-path : test direct de `base_dir / name` avant scan récursif.
- Normalisation de `base_dir` via `.resolve()` et des extensions via `tuple` immuable.
- Les résultats négatifs sont aussi mémorisés (`None`) pour éviter les rescans inutiles.
- Vérification cache OK : deuxième appel identique n'augmente pas la taille du cache.

## Notes d'implémentation (Point 5)

- Ajout d'un logger dédié `pyplayer.constant` avec `FileHandler`.
- Fichier de logs runtime: `pyplayer-runtime.log` dans le dossier d'exécution créé par le code.
- Dossier runtime centralisé via `_ensure_runtime_dir()` et exposé par `pyplayer_directory()`.
- Remplacement des `print()` de warning dans `constant.py` par `LOGGER.warning(...)`.
- Le logger est non-propagé pour éviter la duplication des messages.
- Vérification faite : un warning réel est bien écrit dans le fichier log runtime.

## Notes d'implémentation (Point 6)

- Ajout de validateurs dédiés : `_normalize_theme`, `_normalize_icon_number`, `_normalize_icon_name`.
- Validation stricte de `theme` sur `{light, dark}` avec fallback + warning log.
- Validation stricte de `icon_number` (entier >= 1) avec fallback + warning log.
- Validation de `icon_name` non-vide (après trim) avec fallback + warning log.
- `load_preferences()` utilise désormais ces validateurs avant de construire `preferences`.
- Vérification faite : prefs invalides sont normalisées et tracées dans `pyplayer-runtime.log`.

## Notes d'implémentation (Point 8)

- Création de `python/ui/widget/config.py`.
- Ajout d'une classe dédiée `PyPlayerConfig`.
- `PyPlayerConfig` centralise :
  - détection des chemins projet (`project_root`, `main_dir`, `icons_dir`, `resources_dir`)
  - runtime/logging (`runtime_dir`, `log_file_path`, `logger`)
  - chargement + validation des préférences (`preferences`).
- Exposition d'un singleton `CONFIG`.
- `constant.py` est allégé et consomme `CONFIG` (plus de logique config dupliquée).
- Vérification runtime OK : import `CONFIG`, accès `constant.PROJECT_ROOT`, `constant.preferences`, `constant.ICON_PLAY`.
- Mise à jour architecture :
  - `config.py` déplacé vers `src/pyplayer/infrastructure/config/settings.py`
  - `constant.py` déplacé vers `src/pyplayer/ui/theme/colors.py`
  - imports migrés vers `src.pyplayer.ui.theme`
  - compilation `py_compile` OK sur les fichiers impactés.

## Notes d'implémentation (Point 9)

- Ajout d'une API explicite `reset_runtime_caches() -> None` dans `src/pyplayer/ui/theme/colors.py`.
- Cette API vide :
  - `_FIND_PATH_CACHE`
  - `_ICON_CACHE`
  - `_LAZY_MISC_CACHE`
- Vérification headless effectuée :
  - caches remplis avant reset `(1, 1, 1)`
  - caches vides après reset `(0, 0, 0)`.

## Notes d'implémentation (Point 10)

- `FileHandler` remplacé par `RotatingFileHandler` dans `src/pyplayer/infrastructure/config/settings.py`.
- Paramètres appliqués :
  - `maxBytes=5 * 1024 * 1024` (5 MB)
  - `backupCount=3`
  - `encoding='utf-8'`
- Vérification runtime headless : le logger expose bien un handler `RotatingFileHandler`.

## Notes d'implémentation (Point 11)

- Ajout du paramètre `allowed_root: Path | None` à `find_path(...)`.
- Contrôle de périmètre : `parent_dir` doit être sous `allowed_root` (via `relative_to`).
- En cas de sortie de périmètre :
  - `safe=False` → `ValueError`
  - `safe=True` → fallback `default`
- Le périmètre est inclus dans la clé de cache de `find_path`.
- Appels internes durcis :
  - recherche d'icônes bornée à `ICONS_DIR`
  - recherche `samplevideo.mp4` bornée à `PROJECT_ROOT`
- Vérification headless OK :
  - cas autorisé (`play.png` dans `ICONS_DIR`) passe
  - cas interdit (`/etc` hors projet) lève/retourne fallback selon `safe`.

## Retour analyse API "save"

- Zones sensibles identifiées :
  - `src/pyplayer/domain/playlist/playlist.py` → `save_to_file()`
  - `src/pyplayer/app/playlist_manager.py` → `_save_config()`, `_save_last_played()`
- État actuel : écritures directes `open(..., 'w')` + `json.dump(...)`.
- Risque : si interruption/crash en cours d'écriture, JSON tronqué/corrompu.
- Action recommandée : appliquer une écriture atomique (`.tmp` + `replace()`).
- Cette action est inscrite au **Point 12** du TODO.

## Notes d'implémentation (Point 12)

- Nouveau module ajouté : `src/pyplayer/infrastructure/persistence/io_utils.py`.
- Nouvelle fonction `write_json_atomic(file_path, data, indent=2, ensure_ascii=False)` :
  - écrit dans un fichier temporaire caché dans le même dossier (`.{name}.tmp-<uuid>`)
  - `json.dump(...)` + `flush()` + `os.fsync(...)`
  - `Path.replace(...)` atomique vers la cible
  - tentative de `fsync` du dossier parent (best effort)
  - suppression du temporaire en `finally` si présent.
- Intégrations réalisées :
  - `src/pyplayer/domain/playlist/playlist.py` → `save_to_file()` utilise `write_json_atomic(...)`
  - `src/pyplayer/app/playlist_manager.py` → `_save_config()` et `_save_last_played()` utilisent `write_json_atomic(...)`
- Vérifications headless effectuées :
  - test unitaire dédié `tests/test_atomic_save.py` (unittest) en mode RED→GREEN
  - cas de panne simulée (`json.dump` patché qui écrit partiellement puis lève une erreur)
  - les fichiers cibles existants restent intacts dans les 3 cas
  - `python3 -m unittest tests/test_atomic_save -v` → `OK (3 tests)`
  - compilation ciblée `py_compile` OK sur les fichiers modifiés
  - sanity check runtime playlist/manager JSON OK.
