import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from PySide6 import QtCore

from src.main.python.api.playlist import Playlist
from src.main.python.ui.widget.constant import pyplayer_directory

logger = logging.getLogger(__name__)

class PlaylistManager:
    """
    Gestionnaire de playlists ultra-simplifié.
    - Charge toutes les playlists au démarrage
    - Sauvegarde automatiquement les changements
    - Gère la dernière playlist jouée
    """

    def __init__(self,data_dir: Optional[Path] = None):
        """
        Initialise le gestionnaire de playlists.
        """
        if data_dir:
            self.data_dir = Path(data_dir)
            self.data_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.data_dir = pyplayer_directory() / "playlists"

        # Fichiers de configuration
        self._config_file = self.data_dir / "manager_config.json"
        self._last_played_file = self.data_dir / "last_played.json"

        # Le volume du player
        self._volume: float = 0.45

        # Playlists chargées
        self._playlists: Dict[str, Playlist] = {}  # id -> Playlist

        # Dernière playlist jouée
        self._last_played_id: Optional[str] = None

        # Playlist active
        self._active_playlist_id: Optional[str] = None

        # Charger la configuration et les playlists
        self._load_config()
        self._load_all_playlists()

        self.auto_cleanup_backups_if_needed(threshold_count=5)

        #Initialisé si vide
        if self.playlist_count == 0:
            playlist = self.create_playlist(
                name="PLAYLIST",
            )

        # Définir un actif par défaut
        if self.active_playlist is None:
            for key, playlist in self.all_playlist.items():
                self.set_active_playlist_by_name(playlist.name)
                break

        logger.info(f"PlaylistManager initialisé: {len(self._playlists)} playlists chargées")

    # ============================================
    # PROPRIÉTÉS SIMPLES
    # ============================================

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        self._save_config()

    @property
    def active_playlist(self) -> Optional[Playlist]:
        """Playlist active actuellement."""
        if self._active_playlist_id:
            return self._playlists.get(self._active_playlist_id)
        return None

    @property
    def all_playlist(self) -> Dict[str, Playlist]:
        return self._playlists

    @property
    def last_played_playlist(self) -> Optional[Playlist]:
        """Dernière playlist jouée."""
        if self._last_played_id:
            return self._playlists.get(self._last_played_id)
        return None

    @property
    def playlist_count(self) -> int:
        """Nombre de playlists chargées."""
        return len(self._playlists)

    @property
    def playlist_ids(self) -> List[str]:
        """IDs de toutes les playlists."""
        return list(self._playlists.keys())

    @property
    def playlist_names(self) -> Dict[str, str]:
        """Noms de toutes les playlists."""
        return {pid: p.name for pid, p in self._playlists.items()}


    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================

    def create_playlist(self, source_path: Optional[Path] = None,
                        name: Optional[str] = None) -> Playlist:
        """
        Crée une nouvelle playlist.

        Args:
            source_path: Dossier ou fichier vidéo
            name: Nom personnalisé

        Returns:
            Nouvelle playlist créée
        """
        try:
            # Créer la playlist
            playlist = Playlist(source_path)

            if name:
                playlist.name = name

            # Générer un nom de fichier pour la sauvegarde
            if source_path:
                base_name = source_path.stem
            else:
                base_name = playlist.name.replace(" ", "_")

            file_name = self._generate_filename(base_name)
            save_path = self.data_dir / file_name

            # Configurer la sauvegarde automatique
            playlist.set_auto_save(save_path)

            # Ajouter au gestionnaire
            self._playlists[playlist.id] = playlist

            # Sauvegarder immédiatement
            playlist.save_to_file(save_path)

            # Mettre à jour la configuration
            self._save_config()

            logger.info(f"Playlist créée: {playlist.name}")
            return playlist

        except Exception as e:
            logger.error(f"Erreur création playlist: {e}")
            raise

    def load_playlist(self, playlist_id: str) -> Optional[Playlist]:
        """
        Charge une playlist par son ID.

        Args:
            playlist_id: ID de la playlist

        Returns:
            Playlist chargée ou None
        """
        return self._playlists.get(playlist_id)

    def get_playlist(self, playlist_id: str) -> Optional[Playlist]:
        """
        Alias pour load_playlist.

        Args:
            playlist_id: ID de la playlist

        Returns:
            Playlist ou None
        """
        return self.load_playlist(playlist_id)

    def set_active_playlist(self, playlist_id: str) -> bool:
        """
        Définit la playlist active.

        Args:
            playlist_id: ID de la playlist

        Returns:
            True si succès
        """
        if playlist_id not in self._playlists:
            logger.error(f"Playlist non trouvée: {playlist_id}")
            return False

        self._active_playlist_id = playlist_id
        self._last_played_id = playlist_id

        # Sauvegarder la dernière playlist jouée
        self._save_last_played()
        self._save_config()

        logger.info(f"Playlist active: {playlist_id}")
        return True

    def set_active_playlist_by_name(self, name: str) -> bool:
        """
        Définit la playlist active par son nom.

        Args:
            name: Nom de la playlist

        Returns:
            True si succès
        """
        for playlist_id, playlist in self._playlists.items():
            if playlist.name == name:
                return self.set_active_playlist(playlist_id)

        logger.error(f"Playlist non trouvée: {name}")
        return False

    def save_all_playlists(self) -> bool:
        """
        Sauvegarde toutes les playlists.

        Returns:
            True si toutes sauvegardées avec succès
        """
        success = True
        for playlist in self._playlists.values():
            if hasattr(playlist, 'save_file_path') and playlist.save_file_path:
                if not playlist.save_to_file(playlist.save_file_path):
                    success = False
                    logger.error(f"Échec sauvegarde: {playlist.name}")

        if success:
            logger.info("Toutes les playlists sauvegardées")


        return success

    def remove_playlist(self, playlist_id: str, delete_file: bool = True) -> bool:
        """
        Supprime une playlist.

        Args:
            playlist_id: ID de la playlist
            delete_file: Supprimer aussi le fichier

        Returns:
            True si succès
        """
        if playlist_id not in self._playlists:
            return False

        playlist = self._playlists[playlist_id]

        # Supprimer le fichier si demandé
        if delete_file and hasattr(playlist, 'save_file_path') and playlist.save_file_path:
            try:
                playlist.save_file_path.unlink()
                logger.info(f"Fichier supprimé: {playlist.save_file_path}")
            except Exception as e:
                logger.error(f"Erreur suppression fichier: {e}")

        # Retirer de la mémoire
        del self._playlists[playlist_id]

        # Si c'était la playlist active, la désactiver
        if playlist_id == self._active_playlist_id:
            self._active_playlist_id = None

        # Si c'était la dernière jouée, la retirer
        if playlist_id == self._last_played_id:
            self._last_played_id = None

        # Sauvegarder la configuration
        self._save_config()

        logger.info(f"Playlist supprimée: {playlist.name}")
        return True

    def rename_playlist(self, playlist_id: str, new_name: str) -> bool:
        """
        Renomme une playlist.

        Args:
            playlist_id: ID de la playlist
            new_name: Nouveau nom

        Returns:
            True si succès
        """
        if playlist_id not in self._playlists:
            return False

        playlist = self._playlists[playlist_id]
        playlist.name = new_name

        # Sauvegarde automatique via la playlist elle-même
        if hasattr(playlist, '_auto_save_if_needed'):
            playlist._auto_save_if_needed()

        # Sauvegarder la configuration
        self._save_config()

        logger.info(f"Playlist renommée: {playlist.name}")
        return True

    # ============================================
    # MÉTHODES UTILITAIRES
    # ============================================

    def get_all_playlists(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste de toutes les playlists.

        Returns:
            Liste de dictionnaires d'informations
        """
        playlists = []
        for playlist_id, playlist in self._playlists.items():
            playlists.append({
                'id': playlist_id,
                'name': playlist.name,
                'description': playlist.description,
                'video_count': playlist.total,
                'total_duration': playlist.total_duration,
                'is_active': playlist_id == self._active_playlist_id,
                'is_last_played': playlist_id == self._last_played_id,
                'path': str(playlist.path) if playlist.path else None,
                'save_path': str(playlist.save_file_path) if hasattr(playlist, 'save_file_path') else None
            })

        return playlists

    def find_playlist_by_name(self, name: str) -> List[str]:
        """
        Trouve des playlists par nom.

        Args:
            name: Nom ou partie du nom

        Returns:
            Liste des IDs correspondants
        """
        results = []
        name_lower = name.lower()

        for playlist_id, playlist in self._playlists.items():
            if name_lower in playlist.name.lower():
                results.append(playlist_id)

        return results

    def find_playlist(self, search_term: str, search_by: str = "name") -> Optional[Playlist]:
        """
        Recherche une playlist selon différents critères.

        Args:
            search_term: Terme de recherche (nom, ID, etc.)
            search_by: Critère de recherche. Options:
                - "name": Recherche par nom (exact ou partiel selon exact_match)
                - "id": Recherche par ID exact
                - "path": Recherche par chemin (contient le terme)
                - "description": Recherche dans la description
                - "all": Recherche dans tous les champs

        Returns:
            Première Playlist trouvée ou None
        """
        search_term_lower = search_term.lower().strip()

        for playlist_id, playlist in self._playlists.items():
            try:
                if search_by == "id":
                    # Recherche exacte par ID
                    if playlist_id == search_term:
                        return playlist

                elif search_by == "name":
                    # Recherche par nom (insensible à la casse)
                    if search_term_lower in playlist.name.lower():
                        return playlist

                elif search_by == "path":
                    # Recherche par chemin si disponible
                    if playlist.path and search_term_lower in str(playlist.path).lower():
                        return playlist

                    # Recherche dans le chemin de sauvegarde
                    if hasattr(playlist, 'save_file_path') and playlist.save_file_path:
                        if search_term_lower in str(playlist.save_file_path).lower():
                            return playlist

                elif search_by == "description":
                    # Recherche dans la description
                    if playlist.description and search_term_lower in playlist.description.lower():
                        return playlist

                elif search_by == "all":
                    # Recherche dans tous les champs
                    if (search_term_lower in playlist.name.lower() or
                            playlist_id == search_term or
                            (playlist.path and search_term_lower in str(playlist.path).lower()) or
                            (playlist.description and search_term_lower in playlist.description.lower())):
                        return playlist

            except AttributeError:
                # Ignorer les playlists qui n'ont pas tous les attributs
                continue

        return None

    def get_playlist_info(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """
        Retourne les informations d'une playlist.

        Args:
            playlist_id: ID de la playlist

        Returns:
            Dictionnaire d'informations ou None
        """
        if playlist_id not in self._playlists:
            return None

        playlist = self._playlists[playlist_id]

        return {
            'id': playlist_id,
            'name': playlist.name,
            'description': playlist.description,
            'video_count': playlist.total,
            'total_duration': playlist.total_duration,
            'current_index': playlist.current_index,
            'play_mode': str(playlist.play_mode),
            'path': str(playlist.path) if playlist.path else None,
            'created_at': playlist.unique_id,  # L'ID peut servir de timestamp
            'is_active': playlist_id == self._active_playlist_id,
            'is_last_played': playlist_id == self._last_played_id
        }

    def cleanup(self) -> Dict[str, int]:
        """
        Nettoie les playlists dont les fichiers sont manquants.

        Returns:
            Statistiques du nettoyage
        """
        removed = 0
        cleaned = 0

        for playlist_id, playlist in list(self._playlists.items()):
            # Vérifier les vidéos manquantes
            if hasattr(playlist, 'remove_missing_files'):
                removed_videos = playlist.remove_missing_files()
                if removed_videos:
                    removed += len(removed_videos)
                    cleaned += 1
                    logger.info(f"Playlist nettoyée: {playlist.name} ({len(removed_videos)} vidéos supprimées)")

        # Si des vidéos ont été supprimées, sauvegarder
        if removed > 0:
            self.save_all_playlists()

        return {
            'playlists_cleaned': cleaned,
            'videos_removed': removed
        }

    def cleanup_backups(self,
                        max_backups_per_playlist: int = 5,
                        max_total_backups: int = 50,
                        delete_older_than_days: Optional[int] = 30) -> Dict[str, Any]:
        """
        Nettoie automatiquement les anciens backups.

        Args:
            max_backups_per_playlist: Nombre maximum de backups par playlist
            max_total_backups: Nombre maximum total de backups
            delete_older_than_days: Supprimer les backups plus vieux que X jours

        Returns:
            Statistiques du nettoyage
        """
        results = {
            'total_backups_before': 0,
            'total_backups_after': 0,
            'backups_deleted_by_playlist_limit': 0,
            'backups_deleted_by_age': 0,
            'backups_deleted_by_total_limit': 0,
            'files_deleted': [],
            'errors': []
        }

        try:
            # Trouver tous les fichiers backup
            backup_files = list(self.data_dir.glob("*.backup.*.json"))
            results['total_backups_before'] = len(backup_files)

            if not backup_files:
                logger.info("Aucun backup à nettoyer")
                return results

            # 1. Grouper les backups par playlist
            backups_by_playlist = self._group_backups_by_playlist(backup_files)

            # 2. Nettoyer par limite par playlist
            for playlist_name, backups in backups_by_playlist.items():
                if len(backups) > max_backups_per_playlist:
                    # Garder les X plus récents, supprimer les anciens
                    backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    backups_to_delete = backups[max_backups_per_playlist:]

                    for backup_file in backups_to_delete:
                        try:
                            if not backup_file.exists():
                                continue

                            backup_file.unlink()
                            results['backups_deleted_by_playlist_limit'] += 1
                            results['files_deleted'].append(str(backup_file))
                            logger.debug(f"Backup supprimé (limite playlist): {backup_file.name}")

                        except Exception as e:
                            results['errors'].append(f"{backup_file}: {e}")

            # 3. Nettoyer par âge
            if delete_older_than_days:
                cutoff_time = datetime.now().timestamp() - (delete_older_than_days * 24 * 3600)

                # Re-lister les backups restants
                backup_files = list(self.data_dir.glob("*.backup.*.json"))

                for backup_file in backup_files:
                    try:
                        if backup_file.stat().st_mtime < cutoff_time:
                            backup_file.unlink()
                            results['backups_deleted_by_age'] += 1
                            results['files_deleted'].append(str(backup_file))
                            logger.debug(f"Backup supprimé (âge): {backup_file.name}")

                    except Exception as e:
                        results['errors'].append(f"{backup_file}: {e}")

            # 4. Nettoyer par limite totale
            backup_files = list(self.data_dir.glob("*.backup.*.json"))

            if len(backup_files) > max_total_backups:
                # Trier par date (plus ancien d'abord)
                backup_files.sort(key=lambda x: x.stat().st_mtime)
                backups_to_delete = backup_files[:len(backup_files) - max_total_backups]

                for backup_file in backups_to_delete:
                    try:
                        backup_file.unlink()
                        results['backups_deleted_by_total_limit'] += 1
                        results['files_deleted'].append(str(backup_file))
                        logger.debug(f"Backup supprimé (limite totale): {backup_file.name}")

                    except Exception as e:
                        results['errors'].append(f"{backup_file}: {e}")

            # Compteur final
            backup_files = list(self.data_dir.glob("*.backup.*.json"))
            results['total_backups_after'] = len(backup_files)

            total_deleted = (results['backups_deleted_by_playlist_limit'] +
                             results['backups_deleted_by_age'] +
                             results['backups_deleted_by_total_limit'])

            if total_deleted > 0:
                logger.info(f"Nettoyage backups: {total_deleted} supprimés, {results['total_backups_after']} restants")

            return results

        except Exception as e:
            logger.error(f"Erreur nettoyage backups: {e}")
            results['errors'].append(str(e))
            return results

    def _group_backups_by_playlist(self, backup_files: List[Path]) -> Dict[str, List[Path]]:
        """
        Groupe les fichiers backup par playlist.

        Args:
            backup_files: Liste des fichiers backup

        Returns:
            Dictionnaire {nom_playlist: [backups]}
        """
        backups_by_playlist = {}

        for backup_file in backup_files:
            # Extraire le nom de la playlist du nom de fichier
            # Format: playlist.backup.20240101_120000.json
            parts = backup_file.stem.split('.')
            if len(parts) >= 3:
                playlist_name = parts[0]
            else:
                playlist_name = "unknown"

            if playlist_name not in backups_by_playlist:
                backups_by_playlist[playlist_name] = []

            backups_by_playlist[playlist_name].append(backup_file)

        return backups_by_playlist

    def auto_cleanup_backups_if_needed(self,
                                       threshold_count: int = 100,
                                       force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Nettoie automatiquement les backups si nécessaire.
        À appeler périodiquement (au démarrage, toutes les heures, etc.).

        Args:
            threshold_count: Seuil déclencheur du nettoyage
            force: Forcer le nettoyage même si sous le seuil

        Returns:
            Résultats du nettoyage ou None si pas nécessaire
        """
        try:
            # Compter les backups actuels
            backup_files = list(self.data_dir.glob("*.backup.*.json"))
            backup_count = len(backup_files)

            logger.debug(f"Backups actuels: {backup_count} (seuil: {threshold_count})")

            # Vérifier si le nettoyage est nécessaire
            if backup_count >= threshold_count or force:
                logger.info(f"Nettoyage auto backups déclenché: {backup_count} fichiers")

                # Paramètres de nettoyage automatique
                return self.cleanup_backups(
                    max_backups_per_playlist=3,  # Garder seulement 3 derniers par playlist
                    max_total_backups=50,  # Maximum 50 backups au total
                    delete_older_than_days=7  # Supprimer les backups > 7 jours
                )
            else:
                return None

        except Exception as e:
            logger.error(f"Erreur nettoyage auto backups: {e}")
            return None

    def get_backup_stats(self) -> Dict[str, Any]:
        """
        Retourne des statistiques sur les backups.

        Returns:
            Dictionnaire de statistiques
        """
        try:
            backup_files = list(self.data_dir.glob("*.backup.*.json"))

            if not backup_files:
                return {
                    'total_count': 0,
                    'total_size_mb': 0,
                    'oldest_backup': None,
                    'newest_backup': None,
                    'by_playlist': {}
                }

            # Calculer la taille totale
            total_size = sum(f.stat().st_size for f in backup_files)

            # Trier par date
            backup_files.sort(key=lambda x: x.stat().st_mtime)
            oldest = backup_files[0]
            newest = backup_files[-1]

            # Grouper par playlist
            by_playlist = {}
            for backup_file in backup_files:
                parts = backup_file.stem.split('.')
                playlist_name = parts[0] if len(parts) >= 3 else "unknown"

                if playlist_name not in by_playlist:
                    by_playlist[playlist_name] = {
                        'count': 0,
                        'size_bytes': 0,
                        'oldest': None,
                        'newest': None
                    }

                by_playlist[playlist_name]['count'] += 1
                by_playlist[playlist_name]['size_bytes'] += backup_file.stat().st_size

                # Mettre à jour oldest/newest
                backup_mtime = backup_file.stat().st_mtime
                playlist_data = by_playlist[playlist_name]

                if (playlist_data['oldest'] is None or
                        backup_mtime < playlist_data['oldest'].stat().st_mtime):
                    playlist_data['oldest'] = backup_file

                if (playlist_data['newest'] is None or
                        backup_mtime > playlist_data['newest'].stat().st_mtime):
                    playlist_data['newest'] = backup_file

            # Formater les résultats
            for playlist_name, data in by_playlist.items():
                data['size_mb'] = data['size_bytes'] / (1024 * 1024)
                if data['oldest']:
                    data['oldest_date'] = datetime.fromtimestamp(data['oldest'].stat().st_mtime).isoformat()
                if data['newest']:
                    data['newest_date'] = datetime.fromtimestamp(data['newest'].stat().st_mtime).isoformat()

            return {
                'total_count': len(backup_files),
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'oldest_backup': {
                    'path': str(oldest),
                    'date': datetime.fromtimestamp(oldest.stat().st_mtime).isoformat(),
                    'size_mb': oldest.stat().st_size / (1024 * 1024)
                },
                'newest_backup': {
                    'path': str(newest),
                    'date': datetime.fromtimestamp(newest.stat().st_mtime).isoformat(),
                    'size_mb': newest.stat().st_size / (1024 * 1024)
                },
                'by_playlist': by_playlist
            }

        except Exception as e:
            logger.error(f"Erreur statistiques backups: {e}")
            return {'error': str(e)}

    # ============================================
    # MÉTHODES PRIVÉES
    # ============================================

    def _load_config(self) -> None:
        """Charge la configuration depuis le fichier."""
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Charger la dernière playlist jouée
                if 'last_played_id' in config:
                    self._last_played_id = config['last_played_id']
                    self._active_playlist_id = self._last_played_id
                if 'volume' in config:
                    self._volume = config['volume']

                logger.debug("Configuration chargée")

        except Exception as e:
            logger.error(f"Erreur chargement configuration: {e}")

    def _save_config(self) -> None:
        """Sauvegarde la configuration."""
        try:
            config = {
                'version': '1.0',
                'volume': self.volume,
                'last_updated': datetime.now().isoformat(),
                'playlist_count': len(self._playlists),
                'last_played_id': self._last_played_id,
                'active_playlist_id': self._active_playlist_id
            }

            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.debug("Configuration sauvegardée")

        except Exception as e:
            logger.error(f"Erreur sauvegarde configuration: {e}")

    def _save_last_played(self) -> None:
        """Sauvegarde la dernière playlist jouée."""
        try:
            last_played = {
                'playlist_id': self._last_played_id,
                'timestamp': datetime.now().isoformat()
            }

            with open(self._last_played_file, 'w', encoding='utf-8') as f:
                json.dump(last_played, f, indent=2, ensure_ascii=False)

            logger.debug("Dernière playlist sauvegardée")

        except Exception as e:
            logger.error(f"Erreur sauvegarde dernière playlist: {e}")

    def _load_all_playlists(self) -> None:
        """Charge toutes les playlists du dossier."""
        try:
            # Chercher tous les fichiers .json dans le dossier
            playlist_files = list(self.data_dir.glob("*.json"))

            # Exclure les fichiers de configuration
            config_files = [self._config_file, self._last_played_file]
            playlist_files = [f for f in playlist_files if f not in config_files]

            for file_path in playlist_files:
                try:
                    # Charger la playlist
                    playlist = Playlist.load_from_file(file_path)
                    if playlist:
                        # Configurer la sauvegarde automatique
                        playlist.set_auto_save(file_path)

                        # Ajouter au gestionnaire
                        self._playlists[playlist.id] = playlist

                        logger.debug(f"Playlist chargée: {playlist.name}")

                except Exception as e:
                    logger.error(f"Erreur chargement {file_path}: {e}")

            logger.info(f"{len(playlist_files)} fichiers playlist trouvés, {len(self._playlists)} chargés")

        except Exception as e:
            logger.error(f"Erreur chargement playlists: {e}")

    def _generate_filename(self, base_name: str) -> str:
        """
        Génère un nom de fichier unique.

        Args:
            base_name: Nom de base

        Returns:
            Nom de fichier unique
        """
        # Nettoyer le nom
        import re
        clean_name = re.sub(r'[^\w\s-]', '', base_name)
        clean_name = re.sub(r'[-\s]+', '_', clean_name).strip('-_')

        # Chercher un nom unique
        counter = 1
        while True:
            if counter == 1:
                filename = f"{clean_name}.json"
            else:
                filename = f"{clean_name}_{counter}.json"

            full_path = self.data_dir / filename
            if not full_path.exists():
                return filename

            counter += 1

    # ============================================
    # MÉTHODES MAGIQUES
    # ============================================

    def __str__(self) -> str:
        """Représentation textuelle."""
        active = f" (active: {self._active_playlist_id})" if self._active_playlist_id else ""
        return f"PlaylistManager[{self.playlist_count} playlists{active}]"

    def __len__(self) -> int:
        """Nombre de playlists."""
        return len(self._playlists)

    def __contains__(self, playlist_id: str) -> bool:
        """Vérifie si une playlist existe."""
        return playlist_id in self._playlists

    def __getitem__(self, playlist_id: str) -> Playlist:
        """Accès par index."""
        if playlist_id not in self._playlists:
            raise KeyError(f"Playlist non trouvée: {playlist_id}")
        return self._playlists[playlist_id]

    pass

"""
# 1. Initialisation (tout est automatique)
from src.main.python.ui.widget.constant import pyplayer_directory
manager = PlaylistManager()

# Ça y est ! Toutes les playlists sont déjà chargées
print(f"Playlists chargées: {manager.playlist_count}")

# 2. Si aucune playlist n'existe, on en crée une
if manager.playlist_count == 0:
    playlist = manager.create_playlist(
        source_path=Path("C:/Videos"),
        name="Mes Vidéos"
    )
    print(f"Playlist créée: {playlist.name}")

# 3. La dernière playlist jouée est automatiquement restaurée
if manager.last_played_playlist:
    print(f"Dernière playlist jouée: {manager.last_played_playlist.name}")
    
# 4. Définir une playlist active
if manager.playlist_count > 0:
    # Par ID
    manager.set_active_playlist(list(manager.playlist_ids)[0])
    
    # Ou par nom
    manager.set_active_playlist_by_name("Mes Vidéos")

# 5. Utiliser la playlist active
active = manager.active_playlist
if active:
    print(f"Playlist active: {active.name}")
    
    # Navigation (sauvegarde automatique !)
    video, idx = active.get_next_video()
    if video:
        print(f"Prochaine vidéo: {video.name}")

# 6. Lister toutes les playlists
for info in manager.get_all_playlists():
    print(f"{info['name']} - {info['video_count']} vidéos")

# 7. Trouver une playlist
results = manager.find_playlist_by_name("vidéo")
for playlist_id in results:
    playlist = manager.get_playlist(playlist_id)
    print(f"Trouvé: {playlist.name}")

# 8. Informations sur une playlist
info = manager.get_playlist_info(active.id if active else None)
if info:
    print(f"Informations: {info}")

# 9. Nettoyage automatique
stats = manager.cleanup()
print(f"Nettoyage: {stats}")

# 10. Sauvegarde manuelle (optionnelle - normalement automatique)
manager.save_all_playlists()


# 1. Initialisation (nettoie auto si > 50 backups)
manager = PlaylistManager()

# 2. Voir les statistiques des backups
stats = manager.get_backup_stats()
print(f"Backups actuels: {stats['total_count']}")
print(f"Taille totale: {stats['total_size_mb']:.1f} MB")

# 3. Nettoyage manuel avec paramètres personnalisés
results = manager.cleanup_backups(
    max_backups_per_playlist=3,      # Garde 3 derniers backups par playlist
    max_total_backups=30,            # Maximum 30 backups au total
    delete_older_than_days=14        # Supprime les backups > 14 jours
)

print(f"Supprimés: {results['backups_deleted_by_age']} par âge")
print(f"Restaient: {results['total_backups_after']} backups")

# 4. Vérifier si un nettoyage auto est nécessaire
cleanup_needed = manager.auto_cleanup_backups_if_needed(threshold_count=100)
if cleanup_needed:
    print(f"Nettoyage auto effectué: {cleanup_needed}")

# 5. Maintenance complète (tout nettoyer)
maintenance_results = manager.maintenance()
print(f"Maintenance: {maintenance_results}")
"""