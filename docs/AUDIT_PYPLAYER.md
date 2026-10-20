# Statut des corrections — version 0.2.0

Chaque point de l'audit ci-dessous a été corrigé **et** couvert par au moins un test automatisé (nom du test indiqué).
Suite complète : 287 tests (286 exécutés + 1 variante selon la présence d'un périphérique audio), sans échec,
94 % de couverture, mode approfondi (1 500 exemples) vert ; test de mutation : 148/150 = 99 % (2 mutants équivalents, voir `docs/TESTING.md`).
Le détail des anomalies d'origine reste plus bas dans ce document, inchangé.

| # | Statut | Correction | Test(s) qui le protègent |
|---|---|---|---|
| 1.1 | ✅ corrigé | ID = UUID généré à la création (plus de hash du dossier, plus de `empty_playlist`) | `test_empty_playlists_do_not_overwrite_each_other`, `test_two_playlists_from_same_folder_coexist`, `test_each_playlist_has_unique_id_even_when_empty_or_same_source` |
| 1.2 | ✅ | sauvegardes dans `playlists/backups/`, jamais scannées ; anciens `*.backup.*` déplacés | `test_backups_are_never_reloaded_as_playlists`, `test_stray_legacy_backups_are_moved_out_of_playlist_dir`, `test_legacy_backups_are_moved_and_originals_snapshotted` |
| 1.3 | ✅ | suppression par identifiant | `test_delete_dialog_returns_ids_for_same_named_playlists`, `test_archive_tab_lists_playlists_with_similar_names` |
| 1.4 | ✅ | annulation du dialogue = aucune action | `test_cancelled_folder_dialog_adds_nothing` |
| 1.5 | ✅ | retrait par objet `Video`, plus par sous-chaîne du nom | `test_dock_items_follow_video_objects_not_names`, `test_random_user_actions_never_break_ui_or_data[0-7]` |
| 1.6 | ✅ | position enregistrée pour le média **chargé** | `test_position_goes_to_loaded_video_not_selected_one` |
| 1.7 | ✅ | plus d'action sur Ctrl+S ; raccourcis uniques | `test_menu_shortcuts_are_unique`, `test_shortcuts_are_never_ambiguous` |
| 1.8 | ✅ | description transmise et enregistrée | `test_description_typed_in_the_dialog_is_really_saved`, `test_new_playlist_dialog_validation` |
| 2.1 | ✅ | aléatoire par « tour » sur des objets (plus d'indices) | `test_playlist_state_machine`, `test_remove_other_video_in_shuffle_keeps_current` |
| 2.2 | ✅ | historique d'aléatoire purgé à la suppression | `test_shuffle_history_never_points_to_removed_or_wrong_video`, `test_playlist_state_machine` |
| 2.3 | ✅ | une playlist est toujours active | `test_remove_playlist_picks_new_active_and_never_leaves_none`, `test_playlist_switch_and_delete_keep_an_active_playlist` |
| 2.4 | ✅ | « suivant » en fin de liste ne rejoue plus | `test_normal_mode_stops_at_end_and_keeps_current`, `test_next_at_end_of_playlist_does_not_replay` |
| 2.5 | ✅ | muet lu sur `QAudioOutput` | `test_mute_follows_the_real_audio_output` |
| 2.6 | ✅ | résolution lue dans les métadonnées du média | `test_open_file_queues_siblings_in_natural_order_and_plays_selected`, `test_media_info_rows_for_loaded_video` |
| 2.7 | ✅ | `MatchExactly` → liste par ID | `test_archive_tab_lists_playlists_with_similar_names` |
| 2.8 | ✅ | UI indexée par objet, doublons de noms gérés | `test_same_file_name_in_two_folders_are_distinct_videos`, `test_dock_items_follow_video_objects_not_names` |
| 2.9 | ✅ | pas de reprise près de la fin (marge proportionnelle) | `test_resume_returns_position_only_in_the_meaningful_window`, `test_resume_window_is_consistent_for_any_duration`, `test_legacy_positions_become_resume_entries_but_ends_and_starts_are_ignored` |
| 2.10 | ✅ | volume sans dérive, volume audio explicite au démarrage | `test_volume_roundtrip_does_not_drift`, `test_window_starts_with_default_playlist_and_consistent_audio_state` |
| 2.11 | ✅ | erreurs média signalées, fichier invalide sauté, fermeture propre (`closeEvent`) | `test_invalid_file_is_skipped_and_reported`, `test_real_process_starts_opens_a_file_and_exits_cleanly` |
| 2.12 | ✅ | Échap quitte seulement le plein écran | `test_escape_only_leaves_fullscreen` |
| 2.13 | ✅ | un seul `QShortcut` par touche | `test_shortcuts_are_never_ambiguous`, `test_volume_mute_key_toggles_mute` |
| 2.14 | ✅ | toutes les actions de menu sont reliées | `test_every_menu_action_is_wired_or_intentionally_passive` |
| 2.15 | ✅ | aide générée à partir des vrais raccourcis, vérifiée | `test_every_shortcut_promised_by_the_help_dialog_really_exists`, `test_help_and_about_report_the_real_version` |
| 2.16 | ✅ | animation inopérante supprimée | (code supprimé) |
| 2.17 | ✅ | infobulle décrit l'action du prochain clic | `test_play_button_tooltip_describes_next_action` |
| 2.18 | ✅ | plus de `.write_test`, parcours récursif | `test_new_playlist_does_not_touch_the_source_folder`, `test_new_playlist_dialog_validation` |
| 2.19 | ✅ | détails (loop-one, move, recherche par chemin, `play_history`…) | `test_playlist_state_machine` (≈ 150 séquences × 45 opérations comparées à un modèle) |
| 3.1 | ✅ | écriture des playlists uniquement si elles changent ; reprise dans un fichier séparé, flush périodique | `test_position_ticks_never_dirty_the_playlist`, `test_position_ticks_do_not_touch_playlists`, `test_ten_thousand_position_ticks_are_cheap` |
| 3.2 | ✅ | ajout par lot (une seule marque « dirty ») | `test_add_many_marks_dirty_once_and_is_fast` |
| 3.3 | ✅ | `initialize_playlist_state` ne reconstruit qu'une fois | `test_random_user_actions_never_break_ui_or_data` |
| 3.4 | ✅ | `current_video` sans effet de bord | `test_playlist_state_machine` |
| 3.5 | ✅ | une ligne ne se redessine que si sa barre change | `test_progress_updates_repaint_only_when_the_bar_changes` |
| 3.6 | ✅ | dessin par délégué (plus de widget par ligne) | `test_populating_a_huge_playlist_is_fast`, `test_list_rows_are_painted_with_the_color_of_their_state` |
| 3.7 | ✅ | recherches limitées pendant le glissement | `test_slider_dragging_does_not_flood_the_player_with_seeks`, `test_clicking_the_slider_jumps_to_that_position` |
| 3.8 | ✅ | volume : un seul connecteur, écriture par lots | `test_volume_is_persisted_by_flush_not_per_tick` |
| 3.9 | ✅ | validation du dossier temporisée | `test_folder_validation_is_debounced_not_run_per_keystroke` |
| 3.10 | ✅ | rotation des sauvegardes (5 par playlist) | `test_backups_are_rotated` |
| 3.11 | ✅ | police d'icônes chargée une fois | `test_icon_font_is_registered_only_once` |
| 4 | ✅ | code mort et sur-ingénierie supprimés (`get_backup_stats`, `find_missing_files`, `last_played.json`, 380 lignes de dialogue inline, `ui_and_api_update`, `ICON_DARK_*`…) | revue du code |
| 5 | ✅ | version unique, README à jour, paquet `pyplayer`, tests lançables par `pytest`, journal, chemins multiplateformes | `test_version_is_defined_in_one_place_and_displayed_everywhere`, `test_wheel_contains_code_resources_and_entry_point`, `test_installed_wheel_runs_from_a_clean_environment` |

## Anomalies supplémentaires trouvées par les nouveaux tests (non listées dans l'audit initial)

* **Tri naturel** : `natural_key("²")` levait `ValueError` (`"²".isdigit()` est vrai mais `int("²")` échoue) → un fichier
  nommé `²` faisait échouer le parcours d'un dossier. Corrigé, test de non-régression + propriétés Hypothesis.
* **Migration** : l'ancien format stocke `created_at` en date ISO ; la première version du nouveau chargeur la refusait
  et aurait mis **toutes** les playlists en quarantaine. Détecté grâce aux vrais fichiers de l'ancienne version
  (`tests/fixtures/legacy_v1`), corrigé.
* **Validation de format** : un JSON valide mais qui n'est pas une playlist (`{"videos": 5}`) était accepté comme
  playlist vide « Playlist » ; la sauvegarde n'était jamais essayée. Corrigé (signature de format exigée, rejet des
  fichiers dont aucune entrée n'est exploitable).
* **Reprise de lecture** : course entre le saut de reprise et les positions « avant saut » qui effaçaient la mémoire ;
  marge de fin fixe de 10 s qui marquait « terminé » tous les médias de moins de 20 s. Corrigés.
* **Plantage natif** (segfault) : double suppression d'un `QLocalSocket` dans la gestion de l'instance unique.
  Réécrit avec un cycle de vie déterministe, test de charge dédié.
* **Performance** : 1 500 médias mettaient ~18 s à s'afficher (un widget par ligne) → dessin direct.
* **`Playlist` vide = « fausse »** : `Playlist` définit `__len__`, donc `if not playlist` confondait une playlist vide avec
  « aucune » et `rename` échouait silencieusement. Corrigé (`__bool__`, comparaisons à `None`).
* **`QMediaPlayer.stop()` se bloque** (Qt 6.12, backend FFmpeg) : mesuré avec Qt seul, sans périphérique audio,
  150 itérations × 4 séries : **0 série sur 4 aboutit avec `stop()`, 4 sur 4 avec `setSource(QUrl())`** ; avec un
  périphérique, un arrêt immédiat après chargement bloque aussi par intermittence. L'application décharge désormais le
  média avec `setSource(QUrl())` (bouton Stop, fermeture) et n'enregistre plus la position « 0 » qui suit l'arrêt.
* **Blocage de Qt/FFmpeg sans périphérique audio** : `setActiveAudioTrack()` ne rend jamais la main s'il n'y a aucune
  sortie audio (reproduit avec Qt seul, 6 essais sur 6). L'application refuse le changement de piste avec un message
  au lieu de figer ; le test vérifie ce refus sans périphérique et le vrai changement avec un périphérique.
* **Sous-titres** : un sous-titre long pouvait être manqué quand 4 sous-titres ou plus démarraient au même instant
  (recherche limitée à 4 entrées). Trouvé par Hypothesis en profil approfondi (1 500 exemples) ; algorithme exact
  (fin maximale cumulée) + contre-exemple conservé comme test.

---


# Audit initial (état au commit bfd030c)


- **Repo** : `Joselma-Jemk/Py_player`
- **Version auditée** : `bfd030c` (30/04/2026) — « refactor: move config/constant to api and harden saves », maintenant `master`
- **Périmètre** : tout le Python de `src/` et `main.py` (~9 000 lignes), plus `README.md`, `todo.md`, `requirements.txt`
- **Méthode** : lecture complète du code, puis reproduction par exécution des points marqués ✅ (scripts de repro dans le scratchpad de la session)

Légende : ✅ = confirmé par exécution · sans marque = confirmé par lecture du code.

---

## Verdict global

Base saine : séparation `api/` et `ui/`, écriture JSON atomique (`io_utils.py`), un test de non-régression sur la sauvegarde atomique.
Les problèmes viennent surtout de deux causes :

1. **Identité des objets** : playlists et vidéos sont retrouvées par nom ou par un hash de chemin, d'où collisions, mauvaises suppressions et doublons.
2. **Auto-save appelé partout** : chaque modification, y compris chaque tick de position, réécrit tout le JSON sur le thread UI.

---

## 1. Bugs qui font perdre des données ou des playlists

| # | Bug | Où |
|---|-----|----|
| 1.1 ✅ | **Les playlists s'écrasent entre elles.** L'ID vaut `"empty_playlist"` pour toute playlist vide, sinon un hash du dossier source. Créer `PLAYLIST`, `A` et `B` donne 3 fichiers JSON mais 1 seule playlist en mémoire. Deux playlists du même dossier donnent le même ID. La collision recommence à chaque redémarrage. | `playlist.py:1364` (`_generate_id`) |
| 1.2 ✅ | **Les backups sont rechargés comme des playlists.** `glob("*.json")` ramasse aussi `*.backup.*.json`. Après `save_all_playlists` puis redémarrage, la playlist « Films » avait pour fichier d'auto-save `movies.backup.…json` ; l'original `movies.json` est orphelin. | `pyplayer_manager.py:804` |
| 1.3 | **« Supprimer une playlist » peut supprimer la mauvaise.** `find_playlist(name)` fait une recherche par sous-chaîne : supprimer « Rock » peut supprimer « Hard Rock » si elle est avant dans le dictionnaire. | `main_window.py:607`, `pyplayer_manager.py:365` |
| 1.4 | **Annuler « Ajouter un dossier » scanne le dossier courant.** Le dialogue annulé retourne `""`, `Path("")` vaut `"."` (✅), puis `rglob` récursif. | `main_window.py:178` |
| 1.5 | **Supprimer une vidéo peut en supprimer une autre.** Recherche par sous-chaîne du nom, première trouvée : `a.mp4` correspond aussi à `data.mp4`. | `main_window.py:855` (`find_videos_by_name`) |
| 1.6 | **La position est écrite dans la mauvaise vidéo.** Cliquer une autre playlist (onglet « Gestion ») change la playlist active sans arrêter le lecteur ; les positions de la vidéo qui joue sont ensuite écrites dans la vidéo « courante » de la nouvelle playlist. | `main_window.py:581` (`set_manually_active_playlist`) |
| 1.7 | **Ctrl+S est affecté à « Supprimer une playlist ».** | `menu_bar.py:319` |
| 1.8 | **La description saisie à la création d'une playlist est perdue** : lue dans le dialogue, jamais transmise à `create_playlist`. | `main_window.py:590` |

## 2. Bugs de logique et de crash

| # | Bug | Où |
|---|-----|----|
| 2.1 ✅ | **Mode aléatoire : `remove_video` change la vidéo en cours.** `_current_index` n'est pas utilisé en shuffle, donc la position n'est pas recalée. Test : suppression d'une vidéo non courante, le courant passe de `v001` à `v003`. | `playlist.py:710-780` |
| 2.2 | **`_shuffle_history` n'est jamais recalé** après `remove_video`, `move_video` ou `swap_videos` : « précédent » peut viser la mauvaise vidéo. | `playlist.py` |
| 2.3 | **Plus de playlist active : crash.** Après suppression de l'active, rien n'en choisit une autre ; `current_video` et `play_video` plantent sur `None`. Idem « suivant » sur une playlist vide. | `main_window.py:128`, `1001`, `pyplayer_manager.py:251` |
| 2.4 | **« Suivant » sur la dernière vidéo rejoue la courante** : le `(None, -1)` retourné est ignoré. | `main_window.py:988` |
| 2.5 | **Mute en désordre.** Lit `state.muted` de la vidéo, mis à jour seulement après 2 s de lecture ; il faut lire `audio_output.isMuted()`. L'état muet existe en 3 endroits (widget, audio_output, `Video.state`). | `main_window.py:1075` |
| 2.6 | **La « Résolution » affichée est la taille du widget**, pas celle de la vidéo (`video_output.width()/height()`). | `main_window.py:898` |
| 2.7 | **`add_playlist_state` ne liste pas certaines playlists** : `MatchEndsWith`, donc « Rock » n'est jamais listée si « Hard Rock » existe. | `dock_widget.py:551` |
| 2.8 | **UI et API divergent sur les doublons de nom.** L'UI déduplique par nom de fichier, l'API accepte deux fichiers de même nom dans des dossiers différents ; le double-clic joue toujours le premier. | `dock_widget.py:596`, `main_window.py:1020` |
| 2.9 | **Une vidéo vue jusqu'au bout reprend à 99 %** : la position n'est jamais remise à zéro à la fin. | `main_window.py:1014` |
| 2.10 ✅ | **Le volume dérive.** `int(0.29*100)` donne 28 ; après sauvegarde et rechargement, 29 devient 28. Utiliser `round()`. Si le volume sauvegardé vaut exactement 20 (défaut du slider), le signal n'est pas émis et l'audio reste à 100 %. | `main_window.py:933`, `tool_bar.py:28` |
| 2.11 | **Aucune gestion d'erreur média** (pas de `errorOccurred` ; un fichier illisible bloque la lecture) et pas de `closeEvent`. | `main_window.py` |
| 2.12 | **Escape entre en plein écran** : raccourci global lié à `toggle_fullscreen` ; il devrait seulement en sortir. | `main_window.py:81` |
| 2.13 ✅ | **Deux `QShortcut` sur `Key_VolumeMute`** : Qt les déclare ambigus et ne déclenche aucun des deux, donc la touche mute ne fait rien. | `tool_bar.py:595`, `604` |
| 2.14 | **Boutons de menu sans effet** : « Lire le suivant » et « Lire le précédent » ne sont connectés à rien. | `menu_bar.py:282-290` |
| 2.15 | **L'aide documente des choses qui n'existent pas** : `Ctrl+→` / `Ctrl+←`, « Ctrl+D = créer une playlist » (c'est « ajouter un dossier »), « bougez la souris pour afficher les contrôles » (ne réaffiche que le curseur). | `menu_bar.py:600-627` |
| 2.16 ✅ | **`animate_button_press` ne s'exécute jamais** : l'animation est détruite à la sortie de la fonction. | `tool_bar.py:393` |
| 2.17 | **Infobulle play/pause inversée** : `btn_play_pause_tooltip` est appelée avant puis après le changement d'icône, avec des hypothèses opposées. | `tool_bar.py:429` |
| 2.18 | **Validation du dialogue de création trop stricte.** Exige un droit d'écriture dans le dossier de vidéos (y crée puis supprime `.write_test`) et ne cherche qu'au premier niveau, alors que la playlist scanne en récursif. | `main_window.py:351` |
| 2.19 | **Détails.** `_next_loop_one` lève `IndexError` si la liste est vide (`playlist.py:1244`) ; `move_video` accepte `to_index == len` ; `find_video_by_id(Path)` retombe sur une comparaison par nom seul ; `PlaylistState.update_state(video_path=None)` ne peut pas effacer le chemin ; `play_history` ignore les relectures ; `remove_video` par `Path` ne met pas `p_state` à jour. | `playlist.py` |

## 3. Points de performance

| # | Problème | Où |
|---|----------|----|
| 3.1 ✅ | **Auto-save complet à chaque mise à jour de position.** `to_dict()` (un `stat()` par vidéo + un `logger.warning` par fichier manquant) + JSON complet + `fsync` + `replace`, sur le thread UI. Mesuré : **12,5 ms par appel pour 500 vidéos** (JSON de 177 Ko), plusieurs fois par seconde. Écrire toutes les 5 à 10 s et à l'arrêt suffit. | `main_window.py:909`, `playlist.py:367`, `401`, `1429` |
| 3.2 ✅ | **Ajouter un dossier avec l'auto-save actif : 5 s pour 300 vidéos.** `add_video` sauvegarde à chaque ajout, `choose_folder` ajoute un `auto_save` par vidéo, et le doublon est vérifié en O(n). | `playlist.py:674`, `main_window.py:179` |
| 3.3 | **`initialize_playlist_state` : trois appels mal indentés dans la boucle** → P playlists × V widgets reconstruits à chaque changement de playlist. | `main_window.py:781` |
| 3.4 | **`current_video` fait office de getter mais a des effets de bord** (`ensure_active()`, sauvegarde possible), et il est lu des dizaines de fois par seconde. | `main_window.py:128` |
| 3.5 | **Restyle de widget à chaque tick** : `VideoListItem.update_display` fait `unpolish/polish` de deux labels alors que la barre ne change que par pas de 10 %. | `dock_widget.py:129-152` |
| 3.6 | **Un widget par ligne** (`setItemWidget`) : ne tient pas pour des milliers de vidéos ; préférer un `QStyledItemDelegate`. | `dock_widget.py:605` |
| 3.7 | **Le slider de position seek plusieurs fois par clic ou déplacement** : `mouseMoveEvent` ré-émet `valueChanged` que `setValue` a déjà émis. | `player.py:36-68` |
| 3.8 | **Slider de volume** : un `fsync` par cran (`manager.volume` → `_save_config`) ; `valueChanged` connecté deux fois à `volume_update`, avec `setStyleSheet` à chaque cran. | `pyplayer_manager.py:76`, `tool_bar.py:147`, `592` |
| 3.9 | **Validation du dialogue de création** : jusqu'à 6 passes de `touch/unlink` + 20 `glob` par frappe. | `main_window.py:481-515` |
| 3.10 | **Backups non élagués à la sauvegarde manuelle** : le nettoyage ne tourne qu'au démarrage. | `playlist.py:1661`, `pyplayer_manager.py:52` |
| 3.11 | **Fonte d'icônes chargée 4 fois**, avec un `find_path` récursif et un `[0]` qui plante si la fonte est absente. | `main_window.py:32`, `dock_widget.py:261`, `tool_bar.py:255`, `menu_bar.py:25` |

## 4. Sur-ingénierie à couper

**`pyplayer_manager.py`**
- `get_backup_stats` (~80 lignes), `cleanup_backups` en 4 passes, `find_playlist` à 5 critères, `get_playlist_info` (avec un `created_at` factice : `unique_id`).
- `last_played.json` n'est jamais relu (doublon de `manager_config.json`).
- `hasattr(playlist, 'save_file_path')` sur des attributs qui existent toujours.

**`playlist.py`**
- Deux états parallèles : `_current_index` et `p_state.current_index`.
- Sans appelant dans l'UI : `find_missing_files` (cherche dans Downloads et Desktop), `get_video_info`, `swap_videos`, `jump_to_video_by_name`, `find_videos_by_path`.

**`constant.py`**
- Chargement paresseux via `__getattr__` de module pour ~70 constantes, plus un `find_path` récursif avec cache.
- Variantes `ICON_DARK_*` jamais utilisées : le thème dark n'est pas implémenté.

**`main_window.py`**
- `get_playlist_create_info` : ~380 lignes dans une seule méthode, avec `transself` (faute pour `transparent`) 7 fois.
- Dialogue « À propos » de 150 lignes, `ui_and_api_update` vide.

**UI**
- `DeletePlaylistDialog` (235 lignes, double confirmation avec drapeau `_back_to_selection_flag`) : un `QMessageBox` suffit.
- Le menu déclenche les boutons par `btn.clicked.emit` au lieu d'appeler la logique.
- L'état du mode de lecture est stocké dans le texte du glyphe du bouton (`play_mode_tooltip` modifie `self.play_mode`).
- `mediaStatusChanged` est branché à `btn_play_pause_update`, qui attend un `PlaybackState` : sans effet.
- `HelpDialog` : ~870 lignes de widgets inline.

## 5. Qualité et packaging

- **Version incohérente** : « 0.0.1 » (À propos, aide, `author.json`) contre le tag `v0.1.0`.
- **`README.md` obsolète** : cite `generate.py` et `ui/widget/constant.py`, qui n'existent pas.
- **Tests non lançables par `pytest`** : `test_api.py` est un script (`APIRobustTester`, `sys.exit` à l'import), `pytest` ne collecte rien. Seul `test_atomic_save.py` est un vrai `unittest`. Aucun test d'UI ni de scénario shuffle.
- **Imports absolus `src.main.python…` et `parents[3]`** : suppose de lancer depuis la racine, empêche `pip install`. `requirements.txt` sans version.
- **Fallback runtime vers `/tmp/.pyplayer`** : Linux uniquement.
- **`AA_UseOpenGLES` forcé** dans `main.py` : peut casser l'accélération vidéo sur certains pilotes.
- **`QT_MEDIA_BACKEND` défini à l'import de `main_window`** : à déplacer dans `main.py`, avant tout import Qt.
- **`StatusBar`** : label à largeur fixe de 800 px, ce qui impose une largeur minimale de fenêtre.

---

## Plan de correction proposé

1. **Identité des objets** : UUID généré à la création et stocké dans le JSON ; vidéos et playlists référencées par ID (ou chemin complet), jamais par nom. Règle 1.1, 1.3, 1.5, 2.7, 2.8.
2. **Backups** : les sortir du dossier scanné, ou filtrer `*.backup.*`. Règle 1.2 et 3.10.
3. **Auto-save** : `QTimer` de 5 à 10 s avec drapeau « dirty », sauvegarde à l'arrêt et à la fermeture. Règle presque tout le chapitre 3.
4. **Garde-fous** : annulation de dialogue (1.4), playlist active nulle (2.3), `current_video` sans effet de bord, mute via `audio_output`, résolution via les métadonnées du média.
5. **Mode aléatoire** : recaler position et historique dans `remove_video`, `move_video` et `swap_videos` (2.1, 2.2).
6. **Tests** : convertir `test_api.py` en vrai `pytest`, y ajouter les cas reproduits (1.1, 1.2, 2.1, 3.1, 3.2).
7. **Nettoyage** : supprimer le code mort du chapitre 4, aligner la version, mettre à jour le `README` et l'aide.

## Annexe — ce qui a été testé

- Exécutés sur l'API : collisions d'ID (1.1), backups rechargés (1.2), `remove_video` en shuffle (2.1), coût d'auto-save (3.1), ajout de dossier (3.2), `Path("")` (1.4), troncature du volume (2.10).
- Exécutés sous PySide6 6.12 en mode offscreen : raccourcis ambigus (2.13), animation détruite (2.16).
- Écartés après test : le sélecteur CSS `.video-item-text[state=…]` fonctionne bien, et `QSlider.setValue(float)` ne plante pas avec cette version de PySide6.
- Non testé en conditions réelles : lecture vidéo, plein écran et fréquence exacte de `positionChanged` (pas de pilote média ni d'écran dans cet environnement). Les points qui en dépendent sont déduits du code.
