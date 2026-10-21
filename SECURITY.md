# Politique de sécurité

## Signaler une vulnérabilité

Merci de **ne pas** ouvrir d'issue publique pour une faille. Utilisez le signalement privé de GitHub
(onglet *Security* → *Report a vulnerability*) ou contactez le mainteneur par message privé. Indiquez la version,
le système, les étapes pour reproduire et l'impact. Une réponse est donnée dès que possible.

## Versions prises en charge

Seule la dernière version publiée reçoit des correctifs.

## Ce que PyPlayer garantit

* **Téléchargements d'outils et mises à jour** : HTTPS uniquement, hôtes GitHub autorisés revérifiés à chaque
  redirection, taille limitée, **somme SHA-256 obligatoire** (pas de repli sans vérification), remplacement atomique.
* **Sous-processus yt-dlp** : les options sont validées, passées sous la forme `--option=valeur`, et l'URL est toujours
  placée après `--` (aucune injection d'option possible depuis un lien).
* **Données locales** : écritures atomiques, fichiers corrompus mis en quarantaine, aucune télémétrie.

## Limites connues

* La vérification SHA-256 des mises à jour protège contre la corruption et l'altération **en transit** ; elle ne
  protège pas d'une release publiée par un compte compromis (les binaires ne sont pas encore signés).
* yt-dlp et FFmpeg sont des programmes tiers : leur sécurité dépend de leurs propres versions, installées depuis leurs
  publications officielles.
