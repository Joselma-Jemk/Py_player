# Feuille de route — vers un lecteur plus « pro »

Établie à partir d'une veille web (sources en bas) et de l'état réel du code. Chaque ligne indique ce que Qt
Multimedia permet, ce qui exige un autre backend, et ce qui n'a **pas** pu être vérifié.

## Déjà fait (inspiré de mpv, MPC-HC, VLC)
Raccourcis et fonctions repris des lecteurs de référence : vitesse `[` `]` ⌫, boucle A-B, saut précis, piste audio
(`A`), sous-titres (`V`, décalage `Z`/`X`), capture (`S`), plein écran (`F`), volume par molette, reprise de lecture,
instance unique et « Ouvrir avec… ».

## Priorité 1 — à faire avec Qt Multimedia
| Fonction | Remarque |
|---|---|
| Fenêtre Réglages (raccourcis personnalisables, dossier des captures, pas de saut, style des sous-titres) | aujourd'hui tout passe par `settings.json` |
| Recherche/filtre dans la playlist, file « lire ensuite », signets, minuteur d'arrêt | pur code applicatif |
| Pochette et tags des fichiers audio dans la liste, visualiseur simple | `QMediaMetaData` fournit titre/artiste/album/pochette |
| Vignette de prévisualisation au survol de la barre de progression | second `QMediaPlayer` muet ou images ffmpeg |
| Intégration système (touches multimédia globales : MPRIS sous Linux, SMTC sous Windows, Now Playing sous macOS) | dépend de la plateforme, à tester sur chacune |

## Priorité 2 — exige un autre backend (libmpv)
Qt Multimedia n'expose pas : avance **image par image**, **décalage audio** (VLC : touche `K`, 50 ms par appui),
**égaliseur** (VLC : 10 bandes), filtres vidéo avancés, **chapitres**, choix fin du décodage matériel.
La voie habituelle est **python-mpv** (libmpv chargé par `ctypes`).

Points d'attention relevés dans la documentation : sous PyQt/PySide il faut appeler
`locale.setlocale(locale.LC_NUMERIC, "C")` avant de créer le premier `mpv.MPV` ; le widget hôte doit être une fenêtre
native (`WA_NativeWindow`) dont on passe le `winId` ; sous macOS des bugs d'événements sont connus ; libmpv désactive
par défaut l'OSD et les raccourcis clavier. Intégrer libmpv dans Qt Quick plafonne la fréquence d'affichage de toute
l'interface à celle de la vidéo (alternative : rendu dans un framebuffer séparé).
*Non vérifié par la veille* : les noms exacts des propriétés mpv pour l'image par image, le décalage audio et `hwdec`
(à lire dans le manuel mpv avant de coder).

Intérêt supplémentaire : le blocage de Qt/FFmpeg observé pendant ce travail (`QMediaPlayer.stop()`,
`setActiveAudioTrack` sans périphérique audio) disparaîtrait avec un backend différent.

## Priorité 3 — lecture depuis des sites (YouTube, etc.)
`Ctrl+U` ne lit que les **adresses directes** de fichiers ou de flux. Une page YouTube n'est pas un flux : il faut un
extracteur. La pratique courante est d'utiliser **yt-dlp** pour obtenir l'adresse réelle du flux, puis de la donner au
lecteur. Contraintes :
* dépendance optionnelle (`pip install yt-dlp`), à tenir à jour car les sites changent ;
* la valeur retournée par `extract_info` n'est pas garantie d'être un dictionnaire sérialisable : traitement défensif ;
* **conditions d'utilisation des sites et droit d'auteur** : la veille n'a rien établi sur la légalité ; à vérifier avant
  de livrer cette fonction.

## Priorité 4 — distribution
Installateur Windows (PyInstaller + Inno Setup avec association des extensions), AppImage ou `.deb`, bundle `.app`
macOS, signature de code, mise à jour automatique. Traduction (i18n) et accessibilité (lecteurs d'écran, contrastes).

## Non établi par la veille
Chapitres, signets, minuteur d'arrêt et bibliothèque multimédia de VLC : les recherches n'ont rien retourné de
fiable ; ces fonctions sont décrites ici d'après l'usage courant des lecteurs, pas d'après une source.

## Sources
* Qt for Python — [QMediaPlayer](https://doc.qt.io/qtforpython/PySide6/QtMultimedia/QMediaPlayer.html) (pistes audio/sous-titres, vitesse ; aucun chargement de sous-titres externes)
* mpv — [raccourcis par défaut (input.conf)](https://raw.githubusercontent.com/mpv-player/mpv/master/etc/input.conf)
* MPC-HC — [notes de version : boucle A-B, vitesse, reprise](https://www.neowin.net/amp/media-player-classic---home-cinema-270/)
* VLC — [Adjustment & Effects](https://vlc-user-documentation.readthedocs.io/en/latest/settings/adjustmentsandeffects.html), [délai des sous-titres](https://forum.videolan.org/viewtopic.php?p=132013)
* python-mpv — [PyPI](https://pypi.org/project/python-mpv/) ; [Qt Forum : libmpv dans Qt Quick](https://forum.qt.io/topic/149728/improve-rendering-performance-while-integrating-libmpv-with-qtquick-python)
* yt-dlp — [intégration en Python](https://www.mintlify.com/yt-dlp/yt-dlp/advanced/embedding), [principe d'usage avec un lecteur](https://mcav.readthedocs.io/en/latest/library/yt-dlp.html)
