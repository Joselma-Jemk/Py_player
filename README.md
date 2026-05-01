# PyPlayer

PyPlayer est un lecteur video desktop en Python base sur PySide6. Le projet
lit des medias locaux, gere des playlists persistantes et propose une
interface Qt avec modes de lecture `NORMAL`, `LOOP_ONE`, `LOOP_ALL` et
`SHUFFLE`.

## Prerequis

- Python 3.10+
- `PySide6`

## Installation

Installation minimale depuis le depot :

```bash
python -m pip install -r requirements.txt
```

Installation editable pour le developpement :

```bash
python -m pip install -e .
```

## Lancement

Depuis la racine du depot :

```bash
python main.py
```

Apres installation editable, une commande console est aussi disponible :

```bash
pyplayer
```

## Tests

Lancer toute la suite :

```bash
python -m unittest discover -s tests -v
```

## Structure

```text
assets/
  fonts/        Police d'icones Material Symbols
  icons/        Icônes applicatives et variantes light/dark
config/
  preferences.json
src/
  pyplayer/
    bootstrap.py
    app/
    domain/
    infrastructure/
    ui/
tests/
main.py
pyproject.toml
```

## Point d'entree

- `main.py` : lanceur mince pour le developpement
- `src/pyplayer/bootstrap.py` : bootstrap moderne (`run()`)

## Notes techniques

- Le projet charge ses assets depuis `assets/` et sa configuration depuis
  `config/`, via `src.pyplayer.infrastructure.config.settings.CONFIG`.
- Les tests couvrent le domaine playlist, le manager, les sauvegardes
  atomiques et un smoke test Qt offscreen.
- Le backend multimedia Qt est configure pour utiliser FFmpeg.
