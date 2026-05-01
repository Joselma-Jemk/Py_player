# TODO UI — PyPlayer

## À revoir après la correction du flux lazy

1. **Contenu de l’écran d’attente du player**
   - Revoir complètement ce qui est affiché pendant l’initialisation du lecteur.
   - Le message actuel est trop statique et reste peu informatif.
   - Définir un vrai état d’attente UX :
     - message plus utile
     - indicateur visuel crédible
     - disparition nette quand le player est prêt

2. **Boutons playback**
   - Raffiner encore `hover`
   - Raffiner encore `pressed`
   - Vérifier l’état actif `play/pause`
   - Harmoniser le poids visuel des icônes

3. **Bloc temps**
   - Réduire l’effet de “capsule trop lourde”
   - Revoir son alignement dans la barre basse
   - Ajuster le contraste courant / total

4. **Barre basse**
   - Revoir l’équilibre gauche / centre / droite
   - Vérifier le spacing global
   - Éliminer les éléments parasites visuellement

5. **Curseur volume**
   - Revoir la poignée blanche
   - Ajuster la taille et le contraste
   - Vérifier la cohérence avec la timeline principale

6. **Panneau playlist**
   - Revoir la zone vide
   - Mieux hiérarchiser les tabs
   - Repenser la zone de boutons d’action en bas

7. **Status bar**
   - Revoir `Pas de média en cours`
   - Déterminer si cette zone doit afficher un vrai état dynamique

8. **Cohérence générale**
   - Uniformiser rayons, bordures, accent vert et contrastes
   - Vérifier que les états interactifs suivent la même logique partout
