# Contribuer à PyPlayer

Merci de votre intérêt ! Quelques règles simples gardent le projet fiable.

## Mise en place

```bash
git clone https://github.com/Joselma-Jemk/Py_player.git && cd Py_player
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest
```

FFmpeg doit être installé pour les tests qui lisent de vrais médias (ils sont ignorés sinon).

## Principes du code

* **`api/` n'importe jamais Qt** : toute la logique métier y reste testable seule. `ui/` ne fait que l'affichage et
  l'orchestration.
* **Le look de l'interface est stable** : ne changez pas les couleurs, la disposition ou les widgets sans discussion.
* La vidéo courante est référencée par objet, jamais par index ou par nom.
* Ne contactez le réseau que via `api/fetch.py` (HTTPS, hôtes autorisés, SHA-256 obligatoire).
* Écrivez comme le code environnant : même densité de commentaires, mêmes noms, même langue (français).

## Avant d'ouvrir une pull request

1. Ajoutez ou adaptez des tests : un bug corrigé doit avoir un test qui échouait avant le correctif.
2. `QT_QPA_PLATFORM=offscreen pytest` et `python -m pyflakes src` doivent passer.
3. Les tests doivent être **portables** (Windows et Linux : chemins avec `Path`, JSON via `json.dumps`, pas de supposition
   sur la présence de FFmpeg) et **sans sommeil fixe** : attendez une condition, pas un délai.
4. Mettez à jour `CHANGELOG.md` si le changement se voit côté utilisateur.

## Publier une version

Changez `__version__` dans `src/pyplayer/__init__.py`, ajoutez la section correspondante au `CHANGELOG.md`, puis :

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
```

Le workflow `release.yml` vérifie que le tag correspond à `__version__`, lance les tests, compile Linux et Windows,
teste l'installateur et publie la release.
