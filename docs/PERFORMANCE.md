# Performance et mémoire

Mesures avec `python tools/benchmark.py` (Linux, rendu logiciel hors écran, 20 000 médias).

| Mesure | Avant | Après |
|---|---|---|
| RSS après import | 68,9 Mo | 69,8 Mo |
| Fenêtre au repos | 103,2 Mo | 103,4 Mo |
| Lecture 720p (RSS) | 149,7 Mo | 150,0 Mo |
| Ajout de 20 000 médias | 2,50 s | 2,03 s |
| Rafraîchissement de la liste | 0,93 s | 0,75 s |
| Mémoire par 1000 médias | 2,69 Mo | 2,47 Mo |
| Liste de 20 000 médias (RSS) | 196,8 Mo | 193,7 Mo |

Changements : `Video` en `slots`, tri naturel sans `relative_to`, enregistrement de la position limité à 2 fois/s,
vérification d'existence des fichiers par paquets au-delà de 300 médias, rafraîchissement de l'affichage du
temps seulement quand il change.

Limites honnêtes : le CPU en lecture (~33 %) vient surtout du décodage/rendu logiciel de la machine de test,
pas de l'application ; la RAM de base est dominée par Qt et FFmpeg. Les gains mesurés sont modestes (10–20 %
sur les listes), pas un changement d'ordre de grandeur.
