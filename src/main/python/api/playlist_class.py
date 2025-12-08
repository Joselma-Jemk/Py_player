from datetime import datetime
import hashlib
import json
import random
import logging

from enum import Enum
from pathlib import Path
from typing import Optional, List, Union, Tuple, Dict, Any
from dataclasses import dataclass, field

from src.main.python.api.video_class import Video
from src.main.python.ui.widget.constant import VIDEO_EXTENSIONS


class PlayMode(Enum):
    """Modes de lecture."""
    NORMAL = "normal"
    LOOP_ONE = "loop_one"
    LOOP_ALL = "loop_all"
    SHUFFLE = "shuffle"

    def __str__(self) -> str:
        return self.value

    # Méthodes de sérialisation
    def to_dict(self) -> str:
        """Sérialisation en chaîne de caractères."""
        return self.value

    @classmethod
    def from_dict(cls, data: str) -> 'PlayMode':
        """Désérialisation depuis une chaîne."""
        return cls(data)

@dataclass
class PlaylistState:
    """
    Capture l'état courant d'une playlist.
    Simple, épuré et auto-descriptif.
    """
    # Identité de la playlist
    playlist_id: str = ""

    # État de navigation
    play_mode: PlayMode = PlayMode.NORMAL
    current_index: int = -1
    current_video_path: Optional[Path] = None

    # Métadonnées playlist
    total_videos: int = 0
    total_duration: int = 0  # ms

    # État de lecture
    is_playing: bool = False
    play_history: List[int] = field(default_factory=list)

    @property
    def has_video(self) -> bool:
        """Indique si une vidéo est actuellement active."""
        return self.current_index >= 0 and self.current_video_path is not None

    @property
    def is_empty(self) -> bool:
        """Indique si la playlist contient zéro vidéo."""
        return self.total_videos == 0

    @property
    def last_played_index(self) -> int:
        """Retourne l'index de la dernière vidéo jouée."""
        return self.play_history[-1] if self.play_history else -1

    def update_state(self,
                     index: Optional[int] = None,
                     playing: Optional[bool] = None,
                     video_path: Optional[Path] = None,
                     mode: Optional[PlayMode] = None) -> None:
        """
        Met à jour l'état actuel.

        Args:
            index: Nouvel index courant
            playing: Nouvel état de lecture
            video_path: Nouveau chemin de vidéo
            mode: Nouveau mode de lecture
        """
        if index is not None:
            self.current_index = index

            # Ajouter à l'historique si c'est un nouvel index valide
            if index >= 0 and index not in self.play_history:
                self.play_history.append(index)

        if playing is not None:
            self.is_playing = playing

        if video_path is not None:
            self.current_video_path = video_path

        if mode is not None:
            self.play_mode = mode

    def reset_playback(self) -> None:
        """Réinitialise l'état de lecture (conserve playlist_id et métadonnées)."""
        self.current_index = -1
        self.current_video_path = None
        self.is_playing = False
        # Garde l'historique et les métadonnées

    def __str__(self) -> str:
        """Représentation textuelle simple."""
        if self.is_empty:
            return "Playlist vide"

        status = "▶️" if self.is_playing else "⏸️"
        video_name = self.current_video_path.name if self.current_video_path else "Aucune"

        return (
            f"{status} {video_name} "
            f"({self.current_index + 1}/{self.total_videos}) "
            f"[{self.play_mode}]"
        )

    def to_dict(self) -> dict:
        """Sérialise l'état en dictionnaire."""
        return {
            'playlist_id': self.playlist_id,
            'play_mode': self.play_mode.value if self.play_mode else None,
            'current_index': self.current_index,
            'current_video_path': str(self.current_video_path) if self.current_video_path else None,
            'total_videos': self.total_videos,
            'total_duration': self.total_duration,
            'is_playing': self.is_playing,
            'play_history': self.play_history.copy() if self.play_history else []
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PlaylistState':
        """Recrée un PlaylistState depuis un dictionnaire."""
        # Convertir le chemin de fichier
        video_path = Path(data['current_video_path']) if data.get('current_video_path') else None

        # Convertir le mode de lecture
        play_mode = None
        if data.get('play_mode'):
            play_mode = PlayMode.from_dict(data['play_mode'])

        return cls(
            playlist_id=data.get('playlist_id', ''),
            play_mode= play_mode  if play_mode else PlayMode.NORMAL,
            current_index=data.get('current_index', -1),
            current_video_path=video_path,
            total_videos=data.get('total_videos', 0),
            total_duration=data.get('total_duration', 0),
            is_playing=data.get('is_playing', False),
            play_history=data.get('play_history', [])
        )

class Playlist:
    """Représente une playlist de vidéos, chargée depuis un dossier ou vide."""

    def __init__(self, video_path: Optional[Path] = None):
        """
        Initialise une playlist.

        Args:
            video_path: Chemin du dossier ou fichier vidéo (optionnel).
        """
        self.path = video_path
        self.name = video_path.name if video_path else "Playlist sans titre"
        self.unique_id = self._generate_id()
        self.play_mode = PlayMode.NORMAL
        self.videos: List[Video] = []

        #State
        self.p_state = PlaylistState(
            playlist_id=self.unique_id,
            total_videos=len(self.videos),
            total_duration=self.total_duration
        )

        # Index courant pour NORMAL, LOOP_ONE, LOOP_ALL
        self._current_index = -1

        # État pour la navigation shuffle
        self._shuffle_order = []
        self._shuffle_position = -1
        self._shuffle_history = []

        if video_path and video_path.exists():
            if video_path.is_dir():
                self._load_videos_from_folder()
            else:
                self.add_video(video_path)

    # ============================================
    # PROPRIÉTÉS PUBLIQUES
    # ============================================

    @property
    def id(self) -> str:
        """Accès en lecture à l'ID unique de la playlist (hash immutable)."""
        return self.unique_id

    @property
    def total(self) -> int:
        """Nombre total de vidéos dans la playlist."""
        return len(self.videos)

    @property
    def total_duration(self) -> int:
        """Durée totale cumulée de toutes les vidéos (en millisecondes)."""
        return sum(video.duration for video in self.videos if video.duration > 0)

    @property
    def current_index(self) -> int:
        """
        Index courant de la vidéo active.

        Pour NORMAL/LOOP_ONE/LOOP_ALL : retourne self._current_index
        Pour SHUFFLE : calcule l'index depuis l'ordre shuffle
        """
        if not self.videos:
            return -1

        if self.play_mode != PlayMode.SHUFFLE:
            # Mode normal : index simple
            if self._current_index < 0:
                return -1
            # Protection contre index invalide
            return min(self._current_index, len(self.videos) - 1)
        else:
            # Mode shuffle : calcul depuis l'ordre shuffle
            if (not self._shuffle_order or
                    self._shuffle_position < 0 or
                    self._shuffle_position >= len(self._shuffle_order)):
                return -1
            try:
                shuffle_index = self._shuffle_order[self._shuffle_position]
                # Vérifier que l'index est valide
                if 0 <= shuffle_index < len(self.videos):
                    return shuffle_index
                return -1
            except (IndexError, TypeError):
                return -1

    @current_index.setter
    def current_index(self, value: int) -> None:
        """
        Définit l'index courant avec gestion du mode actuel.

        Args:
            value: Nouvel index (0 <= value < total ou -1)
        """
        if not self.videos:
            self._current_index = -1
            return

        # Validation stricte
        if value < -1 or value >= len(self.videos):
            raise ValueError(f"Index {value} invalide. Doit être entre -1 et {len(self.videos) - 1}")

        if self.play_mode != PlayMode.SHUFFLE:
            # Mode normal : mettre à jour directement
            self._current_index = value
        else:
            # Mode shuffle : trouver la position dans l'ordre shuffle
            if value >= 0:
                try:
                    # Chercher cet index dans l'ordre shuffle
                    self._shuffle_position = self._shuffle_order.index(value)
                except ValueError:
                    # Si l'index n'est pas dans l'ordre shuffle, ajuster
                    self._shuffle_position = 0 if self._shuffle_order else -1
            else:
                self._shuffle_position = -1

        self.p_state.update_state(
            index=value,
            video_path=self.videos[value].file_path if value >= 0 else None
        )

    # ============================================
    # MÉTHODES PUBLIQUES DE NAVIGATION
    # ============================================

    def get_next_video(self) -> Tuple[Optional[Video], int]:
        """
        Retourne la prochaine vidéo selon le mode actuel.
        Met à jour self.current_index automatiquement.

        Returns:
            Tuple (video, nouvel_index) ou (None, -1) si fin/fichier non trouvé
        """
        try:
            if not self.videos:
                return None, -1

            # Utiliser l'index courant stocké
            current_idx = self.current_index

            # Sélectionne la stratégie selon le mode
            if self.play_mode == PlayMode.NORMAL:
                video, new_idx = self._next_normal(current_idx)
            elif self.play_mode == PlayMode.LOOP_ONE:
                video, new_idx = self._next_loop_one(current_idx)
            elif self.play_mode == PlayMode.LOOP_ALL:
                video, new_idx = self._next_loop_all(current_idx)
            elif self.play_mode == PlayMode.SHUFFLE:
                video, new_idx = self._next_shuffle(current_idx)
            else:
                return None, -1

            # Vérifier la validité de la vidéo retournée
            if video is None or new_idx < 0 or new_idx >= len(self.videos):
                return None, -1

            # Mettre à jour l'index courant selon le mode
            if self.play_mode != PlayMode.SHUFFLE:
                self._current_index = new_idx

            # Mettre à jour l'état
            self.p_state.update_state(
                index=new_idx,
                playing=True,  # ou selon ta logique
                video_path=video.file_path if video else None,
                mode=self.play_mode
            )

            # Mettre à jour les métadonnées
            self.p_state.total_videos = self.total
            self.p_state.total_duration = self.total_duration

            return video, new_idx

        except Exception as e:
            print(f"Erreur get_next_video: {e}")
            return None, -1

    def get_previous_video(self) -> Tuple[Optional[Video], int]:
        """
        Retourne la vidéo précédente selon le mode actuel.
        Met à jour self.current_index automatiquement.

        Returns:
            Tuple (video, nouvel_index) ou (None, -1)
        """
        try:
            if not self.videos:
                return None, -1

            current_idx = self.current_index

            # Sélectionne la stratégie selon le mode
            if self.play_mode == PlayMode.NORMAL:
                video, new_idx = self._previous_normal(current_idx)
            elif self.play_mode == PlayMode.LOOP_ONE:
                video, new_idx = self._previous_loop_one(current_idx)
            elif self.play_mode == PlayMode.LOOP_ALL:
                video, new_idx = self._previous_loop_all(current_idx)
            elif self.play_mode == PlayMode.SHUFFLE:
                video, new_idx = self._previous_shuffle()
            else:
                return None, -1

            # Vérifier la validité
            if video is None or new_idx < 0 or new_idx >= len(self.videos):
                return None, -1

            # Mettre à jour l'index courant
            if self.play_mode != PlayMode.SHUFFLE and new_idx >= 0:
                self._current_index = new_idx

            # Mettre à jour l'état
            self.p_state.update_state(
                index=new_idx,
                video_path=video.file_path if video else None
            )

            return video, new_idx

        except Exception as e:
            print(f"Erreur get_previous_video: {e}")
            return None, -1

    def set_play_mode(self, mode: PlayMode) -> None:
        """Change le mode de lecture avec conservation de la position."""
        try:
            if mode == self.play_mode:
                return

            old_mode = self.play_mode

            # CRITIQUE: Sauvegarder la position AVANT de changer quoi que ce soit
            if old_mode == PlayMode.SHUFFLE:
                # En mode shuffle, sauvegarder l'index réel avant de vider les structures
                current_video_idx = -1
                if (self._shuffle_order and
                        0 <= self._shuffle_position < len(self._shuffle_order)):
                    try:
                        current_video_idx = self._shuffle_order[self._shuffle_position]
                    except (IndexError, TypeError):
                        current_video_idx = -1
            else:
                # Mode normal : index direct
                current_video_idx = self._current_index

            self.play_mode = mode

            # Mettre à jour l'état
            self.p_state.update_state(
                mode=mode,
                # Garder l'index actuel s'il est valide
                index=current_video_idx if current_video_idx >= 0 else -1
            )

            # Réinitialisations spécifiques selon la transition
            if mode == PlayMode.SHUFFLE:
                self._generate_shuffle_order()

                # Si on avait une vidéo active, essayer de la garder
                if current_video_idx >= 0 and self._shuffle_order:
                    try:
                        self._shuffle_position = self._shuffle_order.index(current_video_idx)
                    except ValueError:
                        # La vidéo n'est pas dans l'ordre shuffle (peut arriver si vidéo supprimée)
                        self._shuffle_position = 0 if self._shuffle_order else -1
                else:
                    self._shuffle_position = -1

            elif old_mode == PlayMode.SHUFFLE and mode != PlayMode.SHUFFLE:
                # Quitte le mode shuffle - nettoyer APRÈS avoir sauvegardé
                self._shuffle_order.clear()
                self._shuffle_history.clear()
                self._shuffle_position = -1

                # Restaurer l'index
                self._current_index = current_video_idx if current_video_idx >= 0 else -1

        except Exception as e:
            print(f"Erreur set_play_mode {self.play_mode} -> {mode}: {e}")
            # En cas d'erreur, revenir à un état stable
            self.play_mode = PlayMode.NORMAL
            self._current_index = -1
            self._shuffle_order.clear()
            self._shuffle_history.clear()
            self._shuffle_position = -1
            self.p_state.reset_playback()

    # ============================================
    # MÉTHODES PUBLIQUES DE GESTION DES VIDÉOS
    # ============================================

    def add_video(self, file_path: Path) -> bool:
        """
        Ajoute une vidéo à la playlist.

        Args:
            file_path: Chemin du fichier vidéo à ajouter.

        Returns:
            bool: True si ajout réussi, False sinon
        """
        try:
            if not file_path.exists() or file_path.is_dir():
                return False
            suffix = file_path.suffix.lower()
            if suffix not in VIDEO_EXTENSIONS:
                return False
            # Vérifier doublon par chemin exact
            if any(v.file_path == file_path for v in self.videos):
                return False
            self.videos.append(Video(file_path))
            self.p_state.total_videos = self.total
            self.p_state.total_duration = self.total_duration
            return True
        except Exception as e:
            print(f"Erreur add_video {file_path}: {e}")
            return False

    def remove_video(self, identifier: Union[Video, Path, int]) -> bool:
        """
        Supprime une vidéo de la playlist.

        Args:
            identifier: Objet Video, chemin Path, ou index entier de la vidéo à supprimer.

        Returns:
            bool: True si suppression réussie, False sinon.
        """
        try:
            if isinstance(identifier, int):
                if 0 <= identifier < len(self.videos):
                    # Ajuster l'index courant si on supprime la vidéo courante
                    if identifier == self._current_index:
                        self._current_index = -1
                        self.p_state.update_state(index=-1, video_path=None)
                    elif identifier < self._current_index:
                        self._current_index -= 1

                    # Ajuster l'ordre shuffle si nécessaire
                    if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                        # Retirer cet index de l'ordre shuffle
                        if identifier in self._shuffle_order:
                            self._shuffle_order.remove(identifier)
                            # Ajuster les indices supérieurs dans l'ordre shuffle
                            self._shuffle_order = [
                                idx if idx < identifier else idx - 1
                                for idx in self._shuffle_order
                            ]
                            # Ajuster la position shuffle
                            if self._shuffle_position >= len(self._shuffle_order):
                                self._shuffle_position = -1

                    del self.videos[identifier]
                    self.p_state.total_videos = self.total
                    self.p_state.total_duration = self.total_duration
                    return True
                return False

            target_path = identifier.file_path if isinstance(identifier, Video) else identifier
            for i, video in enumerate(self.videos):
                if video.file_path == target_path:
                    # Ajuster l'index courant
                    if i == self._current_index:
                        self._current_index = -1
                    elif i < self._current_index:
                        self._current_index -= 1

                    # Ajuster l'ordre shuffle
                    if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                        if i in self._shuffle_order:
                            self._shuffle_order.remove(i)
                            self._shuffle_order = [
                                idx if idx < i else idx - 1
                                for idx in self._shuffle_order
                            ]
                            if self._shuffle_position >= len(self._shuffle_order):
                                self._shuffle_position = -1

                    del self.videos[i]
                    return True
            return False

        except Exception as e:
            print(f"Erreur remove_video: {e}")
            return False

    def move_video(self, from_index: int, to_index: int) -> bool:
        """
        Déplace une vidéo dans la playlist vers une nouvelle position.

        Args:
            from_index: Index actuel de la vidéo à déplacer (0-based).
            to_index: Nouvel index cible (0-based ; peut être égal à from_index).

        Returns:
            bool: True si déplacement réussi, False sinon.
        """
        try:
            if (not 0 <= from_index < len(self.videos) or
                    not 0 <= to_index <= len(self.videos)):
                return False
            if from_index == to_index:
                return True

            video = self.videos.pop(from_index)
            self.videos.insert(to_index, video)

            # Ajuster l'index courant
            if self._current_index == from_index:
                self._current_index = to_index
            elif from_index < self._current_index <= to_index:
                self._current_index -= 1
            elif to_index <= self._current_index < from_index:
                self._current_index += 1

            # Ajuster l'ordre shuffle si nécessaire
            if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                new_shuffle_order = []
                for idx in self._shuffle_order:
                    if idx == from_index:
                        new_shuffle_order.append(to_index)
                    elif from_index < to_index:  # Déplacement vers la droite
                        if from_index < idx <= to_index:
                            new_shuffle_order.append(idx - 1)
                        else:
                            new_shuffle_order.append(idx)
                    else:  # Déplacement vers la gauche
                        if to_index <= idx < from_index:
                            new_shuffle_order.append(idx + 1)
                        else:
                            new_shuffle_order.append(idx)
                self._shuffle_order = new_shuffle_order

            return True

        except Exception as e:
            print(f"Erreur move_video {from_index}->{to_index}: {e}")
            return False

    def swap_videos(self, idx1: int, idx2: int) -> bool:
        """
        Échange deux vidéos aux positions spécifiées dans la playlist.

        Args:
            idx1: Premier index (0-based).
            idx2: Deuxième index (0-based).

        Returns:
            bool: True si échange réussi, False sinon.
        """
        try:
            if (not 0 <= idx1 < len(self.videos) or
                    not 0 <= idx2 < len(self.videos)):
                return False
            if idx1 == idx2:
                return True

            self.videos[idx1], self.videos[idx2] = self.videos[idx2], self.videos[idx1]

            # Ajuster l'index courant
            if self._current_index == idx1:
                self._current_index = idx2
            elif self._current_index == idx2:
                self._current_index = idx1

            # Ajuster l'ordre shuffle
            if self.play_mode == PlayMode.SHUFFLE and self._shuffle_order:
                new_shuffle_order = []
                for idx in self._shuffle_order:
                    if idx == idx1:
                        new_shuffle_order.append(idx2)
                    elif idx == idx2:
                        new_shuffle_order.append(idx1)
                    else:
                        new_shuffle_order.append(idx)
                self._shuffle_order = new_shuffle_order

            return True

        except Exception as e:
            print(f"Erreur swap_videos {idx1}<->{idx2}: {e}")
            return False

    def update_playlist_state(self) -> None:
        """Met à jour automatiquement l'état de la playlist."""
        self.p_state.playlist_id = self.unique_id
        self.p_state.play_mode = self.play_mode
        self.p_state.current_index = self.current_index
        self.p_state.total_videos = self.total
        self.p_state.total_duration = self.total_duration

        # Mettre à jour le chemin de la vidéo courante
        if 0 <= self.current_index < len(self.videos):
            self.p_state.current_video_path = self.videos[self.current_index].file_path
        else:
            self.p_state.current_video_path = None

    # ============================================
    # MÉTHODES PRIVÉES DE NAVIGATION
    # ============================================

    def _next_normal(self, current_index: int) -> Tuple[Optional[Video], int]:
        """Mode NORMAL : lecture séquentielle simple."""
        next_index = current_index + 1

        if next_index >= len(self.videos):
            return None, -1

        return self.videos[next_index], next_index

    def _next_loop_one(self, current_index: int) -> Tuple[Optional[Video], int]:
        """Mode LOOP_ONE : boucle sur la même vidéo."""
        if current_index < 0 or current_index >= len(self.videos):
            # Si pas de vidéo active, prendre la première
            return self.videos[0], 0 if self.videos else -1

        return self.videos[current_index], current_index

    def _next_loop_all(self, current_index: int) -> Tuple[Optional[Video], int]:
        """Mode LOOP_ALL : boucle infinie sur toute la playlist."""
        if not self.videos:
            return None, -1

        next_index = current_index + 1

        # Si fin de playlist, recommence au début
        if next_index >= len(self.videos):
            next_index = 0

        return self.videos[next_index], next_index

    def _next_shuffle(self, current_index: int) -> Tuple[Optional[Video], int]:
        """Mode SHUFFLE : lecture aléatoire avec ordre pré-calculé."""
        if not self.videos:
            return None, -1

        # Initialiser l'ordre shuffle si vide ou épuisé
        if not self._shuffle_order:
            self._generate_shuffle_order()
            if not self._shuffle_order:  # Toujours vide après génération
                return None, -1

        # Avancer dans l'ordre shuffle
        self._shuffle_position += 1

        # Si fin de l'ordre shuffle, en générer un nouveau
        if self._shuffle_position >= len(self._shuffle_order):
            self._generate_shuffle_order()
            self._shuffle_position = 0

        # Récupérer l'index réel dans la playlist
        try:
            shuffle_index = self._shuffle_order[self._shuffle_position]
            # Vérifier que l'index est valide
            if not (0 <= shuffle_index < len(self.videos)):
                return None, -1
        except (IndexError, TypeError):
            return None, -1

        # Ajouter à l'historique (pour "previous")
        if current_index >= 0:
            self._shuffle_history.append(current_index)
            # Garder seulement les N dernières entrées
            if len(self._shuffle_history) > 50:
                self._shuffle_history.pop(0)

        return self.videos[shuffle_index], shuffle_index

    def _previous_normal(self, current_index: int) -> Tuple[Optional[Video], int]:
        """Précédent en mode NORMAL : recule d'une position."""
        if current_index <= 0:
            # Déjà au début
            return None, -1

        prev_index = current_index - 1
        return self.videos[prev_index], prev_index

    def _previous_loop_one(self, current_index: int) -> Tuple[Optional[Video], int]:
        """Précédent en mode LOOP_ONE : même vidéo."""
        if current_index < 0 or current_index >= len(self.videos):
            return self.videos[0], 0 if self.videos else -1

        return self.videos[current_index], current_index

    def _previous_loop_all(self, current_index: int) -> Tuple[Optional[Video], int]:
        """Précédent en mode LOOP_ALL : boucle inversée."""
        if not self.videos:
            return None, -1

        if current_index <= 0:
            # Si au début, aller à la fin
            prev_index = len(self.videos) - 1
        else:
            prev_index = current_index - 1

        return self.videos[prev_index], prev_index

    def _previous_shuffle(self) -> Tuple[Optional[Video], int]:
        """Précédent en mode SHUFFLE : utilise l'historique."""
        if not self.videos:
            return None, -1

        # Cas 1: Utiliser l'historique si disponible
        if self._shuffle_history:
            try:
                prev_index = self._shuffle_history.pop()
                # Vérifier que l'index est valide
                if 0 <= prev_index < len(self.videos):
                    # Ajuster la position shuffle
                    if self._shuffle_order:
                        try:
                            self._shuffle_position = self._shuffle_order.index(prev_index)
                        except ValueError:
                            self._shuffle_position = max(0, self._shuffle_position - 1)
                    return self.videos[prev_index], prev_index
            except (IndexError, ValueError):
                pass

        # Cas 2: Recule dans l'ordre shuffle actuel
        if self._shuffle_order and self._shuffle_position > 0:
            self._shuffle_position -= 1
            try:
                shuffle_index = self._shuffle_order[self._shuffle_position]
                if 0 <= shuffle_index < len(self.videos):
                    return self.videos[shuffle_index], shuffle_index
            except (IndexError, TypeError):
                pass

        return None, -1

    # ============================================
    # MÉTHODES PRIVÉES AUXILIAIRES
    # ============================================

    def _generate_id(self) -> str:
        """Génère un ID unique court via hash SHA-256 du chemin absolu."""
        if not self.path:
            return "empty_playlist"
        try:
            path_str = str(self.path.absolute())
            hash_obj = hashlib.sha256(path_str.encode('utf-8'))
            return hash_obj.hexdigest()[:8].upper()
        except Exception:
            return "error_id"

    def _generate_shuffle_order(self) -> None:
        """Génère un nouvel ordre aléatoire pour le shuffle."""
        if not self.videos:
            self._shuffle_order = []
            self._shuffle_position = -1
            self._shuffle_history.clear()
            return

        indices = list(range(len(self.videos)))
        random.shuffle(indices)

        # Éviter que la première vidéo soit la même que la dernière du précédent ordre
        if self._shuffle_order and indices[0] == self._shuffle_order[-1] and len(indices) > 1:
            swap_pos = random.randint(1, len(indices) - 1)
            indices[0], indices[swap_pos] = indices[swap_pos], indices[0]

        self._shuffle_order = indices
        self._shuffle_position = -1
        self._shuffle_history.clear()

    def _load_videos_from_folder(self) -> None:
        """Parcourt le dossier récursivement et ajoute chaque vidéo valide via add_video."""
        if not self.path or not self.path.exists() or not self.path.is_dir():
            return

        try:
            for file_path in self.path.rglob('*'):
                if file_path.is_file():
                    self.add_video(file_path)
        except Exception as e:
            print(f"Erreur _load_videos_from_folder: {e}")

    # ============================================
    # MÉTHODES UTILITAIRES
    # ============================================

    def __str__(self) -> str:
        """Représentation textuelle de la playlist."""
        return f"Playlist '{self.name}' ({self.total} vidéos, mode: {self.play_mode})"

    # ============================================
    # MÉTHODES DE SÉRIALISATION
    # ============================================

    def to_dict(self, include_video_states: bool = True) -> Dict[str, Any]:
        """
        Sérialise la playlist en dictionnaire.

        Args:
            include_video_states: Inclure les états de lecture individuels des vidéos

        Returns:
            Dictionnaire sérialisé avec versioning et validation
        """
        # Sérialiser les vidéos avec validation
        videos_data = []
        valid_video_count = 0
        missing_video_count = 0

        for video in self.videos:
            # Vérifier si le fichier existe encore
            file_exists = video.file_path.exists() if video.file_path else False

            video_dict = video.to_dict()

            # Ajouter un flag pour indiquer si le fichier existe
            video_dict['file_exists'] = file_exists

            # Optionnel: exclure l'état si demandé
            if not include_video_states:
                video_dict.pop('state', None)

            videos_data.append(video_dict)

            if file_exists:
                valid_video_count += 1
            else:
                missing_video_count += 1

        # Sérialiser l'état shuffle si présent
        shuffle_state = None
        if self.play_mode == PlayMode.SHUFFLE:
            shuffle_state = {
                'shuffle_order': self._shuffle_order.copy() if self._shuffle_order else [],
                'shuffle_position': self._shuffle_position,
                'shuffle_history': self._shuffle_history.copy() if self._shuffle_history else []
            }

        return {
            # Métadonnées de version et validation
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'file_validation': {
                'total_videos': len(self.videos),
                'valid_videos': valid_video_count,
                'missing_videos': missing_video_count,
                'validation_date': datetime.now().isoformat()
            },

            # Informations de base
            'path': str(self.path) if self.path else None,
            'name': self.name,
            'unique_id': self.unique_id,

            # Configuration
            'play_mode': self.play_mode.value,

            # Vidéos
            'videos': videos_data,

            # État interne
            'current_index': self._current_index,

            # État shuffle
            'shuffle_state': shuffle_state,

            # État de lecture complet
            'playlist_state': self.p_state.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict, validate_files: bool = True) -> 'Playlist':
        """
        Recrée une playlist depuis un dictionnaire avec validation optionnelle.

        Args:
            data: Données de sérialisation provenant de to_dict()
            validate_files: Vérifier l'existence des fichiers au chargement

        Returns:
            Playlist restaurée avec gestion des fichiers manquants

        Raises:
            ValueError: Si les données sont invalides
        """
        try:
            # Validation de base
            if not isinstance(data, dict):
                raise ValueError("Les données doivent être un dictionnaire")

            # Créer une playlist vide
            path_data = data.get('path')
            path = Path(path_data) if path_data else None
            playlist = cls(video_path=None)

            # Restaurer les propriétés de base
            playlist.path = path
            playlist.name = data.get('name', 'Playlist restaurée')
            playlist.unique_id = data.get('unique_id', playlist._generate_id())

            # Restaurer le mode de lecture
            play_mode_str = data.get('play_mode', 'normal')
            try:
                playlist.play_mode = PlayMode.from_dict(play_mode_str)
            except ValueError:
                playlist.play_mode = PlayMode.NORMAL

            # Restaurer les vidéos avec validation
            playlist.videos.clear()
            missing_files = []
            corrupted_files = []

            for i, video_data in enumerate(data.get('videos', [])):
                try:
                    video = Video.from_dict(video_data)

                    # Validation du fichier si demandé
                    if validate_files and video.file_path:
                        if not video.file_path.exists():
                            missing_files.append({
                                'index': i,
                                'path': str(video.file_path),
                                'name': video.name
                            })
                        else:
                            # Vérifier que c'est bien un fichier et pas un dossier
                            if video.file_path.is_dir():
                                corrupted_files.append({
                                    'index': i,
                                    'path': str(video.file_path),
                                    'reason': "Est un dossier, pas un fichier"
                                })

                    playlist.videos.append(video)

                except Exception as e:
                    corrupted_files.append({
                        'index': i,
                        'path': video_data.get('file_path', 'inconnu'),
                        'reason': str(e)
                    })

            # Restaurer l'état interne
            playlist._current_index = data.get('current_index', -1)

            # Restaurer l'état shuffle si présent
            shuffle_state = data.get('shuffle_state')
            if shuffle_state and playlist.play_mode == PlayMode.SHUFFLE:
                playlist._shuffle_order = shuffle_state.get('shuffle_order', [])
                playlist._shuffle_position = shuffle_state.get('shuffle_position', -1)
                playlist._shuffle_history = shuffle_state.get('shuffle_history', [])

            # Restaurer l'état de lecture
            playlist_state_data = data.get('playlist_state')
            if playlist_state_data:
                playlist.p_state = PlaylistState.from_dict(playlist_state_data)

            # Stocker les informations de validation
            playlist._load_validation = {
                'missing_files': missing_files,
                'corrupted_files': corrupted_files,
                'total_loaded': len(playlist.videos),
                'load_time': datetime.now().isoformat()
            }

            # Ajuster l'index courant si nécessaire
            if validate_files and missing_files:
                # Si la vidéo courante est manquante, réinitialiser
                if 0 <= playlist.current_index < len(playlist.videos):
                    current_video = playlist.videos[playlist.current_index]
                    if not current_video.file_path.exists():
                        playlist.current_index = -1
                        playlist.p_state.update_state(index=-1, video_path=None)

            # Mettre à jour les métadonnées
            playlist.update_playlist_state()

            return playlist

        except Exception as e:
            raise ValueError(f"Impossible de charger la playlist: {e}")

    def save_to_file(self, file_path: Path, create_backup: bool = True) -> bool:
        """
        Sauvegarde la playlist dans un fichier JSON avec backup optionnel.

        Args:
            file_path: Chemin du fichier de sauvegarde
            create_backup: Créer un backup du fichier existant

        Returns:
            True si réussite, False sinon
        """
        try:
            # Créer le dossier parent si nécessaire
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Créer un backup si demandé et si le fichier existe
            if create_backup and file_path.exists():
                backup_path = file_path.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                except Exception as e:
                    return

            # Sérialiser et sauvegarder
            data = self.to_dict()

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True

        except IOError as e:
            return False
        except json.JSONDecodeError as e:
            return False
        except Exception as e:

            return False

    @classmethod
    def load_from_file(cls, file_path: Path, validate_files: bool = True) -> Optional['Playlist']:
        """
        Charge une playlist depuis un fichier JSON avec gestion d'erreurs.

        Args:
            file_path: Chemin du fichier de sauvegarde
            validate_files: Vérifier l'existence des fichiers

        Returns:
            Playlist restaurée ou None en cas d'erreur

        Note:
            Cette méthode ne lève pas d'exception, elle retourne None et log l'erreur
        """
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            playlist = cls.from_dict(data, validate_files=validate_files)

            # Ajouter le chemin du fichier source
            playlist._source_file = file_path

            return playlist

        except json.JSONDecodeError as e:

            # Essayer de charger depuis le backup le plus récent
            return cls._try_load_from_backup(file_path, validate_files)

        except Exception as e:
            return None

    @classmethod
    def _try_load_from_backup(cls, original_path: Path, validate_files: bool = True) -> Optional['Playlist']:
        """Tente de charger depuis un backup."""
        try:
            # Chercher les backups
            backup_pattern = original_path.with_suffix('.backup.*.json')
            backups = list(original_path.parent.glob(backup_pattern.name))

            if not backups:
                logger.error(f"Aucun backup trouvé pour {original_path}")
                return None

            # Prendre le backup le plus récent
            backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            latest_backup = backups[0]

            logger.info(f"Tentative de chargement depuis backup: {latest_backup}")

            with open(latest_backup, 'r', encoding='utf-8') as f:
                data = json.load(f)

            playlist = cls.from_dict(data, validate_files=validate_files)
            playlist._source_file = original_path  # Garder le chemin original
            playlist._loaded_from_backup = True

            logger.info(f"Chargé depuis backup avec succès: {latest_backup}")
            return playlist

        except Exception as e:
            logger.error(f"Échec du chargement depuis backup: {e}")
            return None

    def get_validation_report(self) -> Dict[str, Any]:
        """
        Retourne un rapport de validation des fichiers.

        Returns:
            Dictionnaire avec les informations de validation
        """
        if hasattr(self, '_load_validation'):
            return self._load_validation.copy()

        # Calculer à la volée si pas déjà fait
        missing_files = []
        valid_files = []

        for i, video in enumerate(self.videos):
            if video.file_path and video.file_path.exists():
                valid_files.append({
                    'index': i,
                    'path': str(video.file_path),
                    'name': video.name
                })
            else:
                missing_files.append({
                    'index': i,
                    'path': str(video.file_path) if video.file_path else 'None',
                    'name': video.name
                })

        return {
            'missing_files': missing_files,
            'valid_files': valid_files,
            'total_videos': len(self.videos),
            'valid_count': len(valid_files),
            'missing_count': len(missing_files),
            'check_time': datetime.now().isoformat()
        }

    def remove_missing_files(self) -> List[Dict[str, Any]]:
        """
        Supprime automatiquement les vidéos dont les fichiers sont manquants.

        Returns:
            Liste des vidéos supprimées
        """
        report = self.get_validation_report()
        missing_files = report.get('missing_files', [])

        removed = []

        # Supprimer en ordre inverse pour éviter les problèmes d'index
        for item in sorted(missing_files, key=lambda x: x['index'], reverse=True):
            idx = item['index']
            if 0 <= idx < len(self.videos):
                removed_video = self.videos[idx]
                if self.remove_video(idx):
                    removed.append({
                        'index': idx,
                        'name': removed_video.name,
                        'path': str(removed_video.file_path)
                    })
                    logger.info(f"Vidéo supprimée (fichier manquant): {removed_video.name}")

        # Mettre à jour l'état
        self.update_playlist_state()

        return removed

    def find_missing_files(self) -> List[Dict[str, Any]]:
        """
        Recherche les fichiers manquants dans des emplacements courants.

        Returns:
            Liste des fichiers potentiellement trouvés
        """
        report = self.get_validation_report()
        missing_files = report.get('missing_files', [])

        found_files = []

        for item in missing_files:
            original_path = Path(item['path'])

            # Chercher dans différents emplacements
            search_locations = [
                # Même nom dans le dossier de la playlist
                self.path / original_path.name if self.path else None,

                # Dans le dossier parent de la playlist
                self.path.parent / original_path.name if self.path and self.path.parent else None,

                # Dans le dossier du fichier source (si chargé depuis fichier)
                getattr(self, '_source_file', Path('.')).parent / original_path.name,

                # Chercher par nom dans le dossier Downloads
                Path.home() / 'Downloads' / original_path.name,

                # Chercher par nom dans le dossier Desktop
                Path.home() / 'Desktop' / original_path.name,
            ]

            for location in search_locations:
                if location and location.exists() and location.is_file():
                    found_files.append({
                        'original': item,
                        'found_at': str(location),
                        'location': str(location)
                    })
                    logger.info(f"Fichier potentiellement trouvé: {original_path.name} -> {location}")
                    break

        return found_files