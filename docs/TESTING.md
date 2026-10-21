# Stratégie de tests

Plus de 560 tests (566 au dernier passage complet, 3 ignorés selon la machine), dont la couverture de branches de
l'API a été mesurée à 94 % sur la version précédente, exécutés hors écran
(`QT_QPA_PLATFORM=offscreen`) avec de **vrais médias** générés par ffmpeg. Durée : ~1 min 30.

```bash
pip install -e ".[dev]"
pytest                                   # suite complète
PYPLAYER_THOROUGH=1 pytest               # Hypothesis : 1 500 exemples par propriété au lieu de 120
pytest --cov=pyplayer --cov-report=term-missing
python tools/mutation_check.py --sample 90 --seed 7     # test de mutation (voir plus bas)
```

Voir aussi `docs/ROADMAP.md` (fonctions à ajouter, issues de la veille web).

## Ce qui est testé, par couche

| Fichier | Rôle |
|---|---|
| `test_property_playlist.py` | **machine à états** : des séquences aléatoires d'ajout/suppression/déplacement/tri/mode/navigation/sérialisation, comparées à un modèle de référence après chaque opération ; 14 invariants (ordre, index, vidéo courante, historique…) |
| `test_property_misc.py` | propriétés Hypothesis : reprise (machine à états), réglages, fuzzing de tous les chargeurs avec du JSON hostile, sous-titres comparés à une recherche exhaustive, aller-retour M3U avec noms exotiques, durées |
| `test_crash_safety.py` | pannes : injection d'erreurs à chaque étape de l'écriture atomique, **`SIGKILL` répété** d'un processus qui écrit en boucle, disque plein, dossier en lecture seule, corruption aléatoire (troncature, octets modifiés, bruit, mauvais types) de tous les fichiers de playlist, deux gestionnaires sur le même dossier |
| `test_legacy_migration.py` | migration à partir des **vrais fichiers de l'ancienne version** (`tests/fixtures/legacy_v1`, générés par le code d'origine) |
| `test_playlist.py`, `test_manager.py`, `test_media.py`, `test_m3u.py`, `test_resume_settings_io.py` | tests unitaires et de régression de chaque point de l'audit |
| `test_ui.py`, `test_ui_flows.py` | interface complète : lecture réelle, reprise, fin de playlist, vitesse/A-B, sous-titres, capture, plein écran, dialogues simulés, réglages restaurés, fermeture |
| `test_ui_stress.py` | **8 séquences de 120 actions utilisateur aléatoires** avec invariants UI↔API après chaque action, clavier, glisser-déposer, menus contextuels, rendu des lignes, performances (1 500 médias, 10 000 ticks, 5 000 médias à recharger) |
| `test_units.py` | journalisation, chemins, inhibition de veille (branches Windows/macOS/Linux simulées), widget lecteur, panneau de playlists |
| `test_cli_packaging.py` | ligne de commande, **vrai processus** qui démarre/ouvre un fichier/se termine proprement, instance unique entre deux processus, construction et installation de la roue dans un environnement vierge |

Toute exception levée dans un slot Qt (qui ne ferait normalement qu'afficher une trace) fait échouer le test
(`no_unhandled_exceptions`). Aucun test ne touche le vrai `~/.pyplayer` (`isolated_home`).

## Test de mutation

`tools/mutation_check.py` modifie le code de `pyplayer.api` (opérateurs de comparaison, `and`/`or`, arithmétique,
constantes, `if` inversés, `return` neutralisés, instructions supprimées), relance les tests et vérifie qu'ils
**échouent**. Un mutant survivant = un comportement non protégé.

Le harnais se vérifie lui-même avant de mesurer : il contrôle que `pyplayer` est bien importé depuis la copie mutée,
que la suite réussit sur le code intact et qu'un mutant évident est tué.

> **Résultats mesurés** (150 mutants tirés au hasard sur 826, `--sample 150 --seed 3`) : 1re mesure valide
> **143/150 = 95 %** ; après ajout des tests ciblant les 7 survivants, **148/150 = 99 %**.
> Les 2 survivants restants sont des **mutants équivalents** (aucun comportement observable ne change) :
> `video.py:71` (`width > 0` → `>= 0` : `0 / h` vaut déjà `0.0`) et `playlist.py:304` (`remember=True` alors qu'il n'y a
> pas de vidéo courante à mémoriser).
> Une première version du harnais chargeait le vrai code au lieu du code muté (`conftest.py` plaçait `src` en tête du
> chemin) ; ses scores d'alors étaient **invalides** et ont été écartés.

## Bugs trouvés *par* ces tests (et corrigés)

Voir « Anomalies supplémentaires » dans `docs/AUDIT_PYPLAYER.md` : tri naturel qui plante sur « ² », migration qui
mettait toutes les playlists en quarantaine, fichier JSON quelconque accepté comme playlist vide, course sur la
reprise de lecture, double suppression d'un `QLocalSocket` (segfault), playlist vide considérée comme « fausse »
(`__len__`), 1 500 médias affichés en 18 s, **blocage de Qt/FFmpeg sur `setActiveAudioTrack` sans périphérique audio**,
sous-titre long manqué derrière 4 sous-titres simultanés (trouvé seulement par le profil approfondi `PYPLAYER_THOROUGH=1`),
**`QMediaPlayer.stop()` qui bloque par intermittence** (trouvé parce que la suite se figeait : mesuré avec Qt seul, remplacé par
`setSource(QUrl())`) et position de reprise effacée par le retour à 0 qui suit un arrêt.

## Limites connues

* Pas d'écran dans l'environnement de test : le **rendu vidéo réel** et le plein écran sur un vrai bureau ne sont testés
  que hors écran ; l'inhibition de veille que par simulation.
* **Audio** : la suite passe dans les deux configurations. Sans périphérique, le test qui vérifie le *refus* du changement
  de piste s'exécute ; avec un périphérique (PulseAudio + « null sink », voir `.github/workflows/tests.yml`), c'est le
  test du *vrai* changement de piste qui s'exécute. Chaque configuration ignore donc exactement 1 test.
* Les tests visuels sont des vérifications de couleurs par état, pas des captures « or » (dépendantes des polices).
