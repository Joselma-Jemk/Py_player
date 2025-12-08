import hashlib
import random
from enum import Enum
from pathlib import Path
from typing import Optional, List, Union, Tuple

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

    @classmethod
    def from_string(cls, value: str) -> Optional['PlayMode']:
        """Convertit une string en PlayMode."""
        try:
            return cls(value)
        except ValueError:
            return None


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

    # === PROPRIÉTÉ current_index ===

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
            return min(self._current_index, len(self.videos) - 1)
        else:
            # Mode shuffle : calcul depuis l'ordre shuffle
            if (not self._shuffle_order or
                    self._shuffle_position < 0 or
                    self._shuffle_position >= len(self._shuffle_order)):
                return -1
            shuffle_index = self._shuffle_order[self._shuffle_position]
            return shuffle_index

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

        # Validation
        if value < -1 or value >= len(self.videos):
            raise ValueError(f"Index {value} invalide. Doit être entre -1 et {len(self.videos) - 1}")

        if self.play_mode != PlayMode.SHUFFLE:
            # Mode normal : mettre à jour directement
            self._current_index = value
        else:
            # Mode shuffle : trouver la position dans l'ordre shuffle
            if value >= 0:
                # Chercher cet index dans l'ordre shuffle
                try:
                    self._shuffle_position = self._shuffle_order.index(value)
                except ValueError:
                    # Si l'index n'est pas dans l'ordre shuffle, ajuster
                    self._shuffle_position = 0
                    print(f"Avertissement: Index {value} non trouvé dans l'ordre shuffle")

    # === MÉTHODES MODIFIÉES POUR GARDER current_index À JOUR ===

    def get_next_video(self) -> Tuple[Optional['Video'], int]:
        """
        Retourne la prochaine vidéo selon le mode actuel.
        Met à jour self.current_index automatiquement.
        """
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

        # Mettre à jour l'index courant selon le mode
        if self.play_mode != PlayMode.SHUFFLE:
            # Pour les modes normaux, stocker le nouvel index
            self._current_index = new_idx
        else:
            # Pour shuffle, on a déjà mis à jour _shuffle_position dans _next_shuffle
            pass

        return video, new_idx

    def get_previous_video(self) -> Tuple[Optional['Video'], int]:
        """
        Retourne la vidéo précédente selon le mode actuel.
        Met à jour self.current_index automatiquement.
        """
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

        # Mettre à jour l'index courant
        if self.play_mode != PlayMode.SHUFFLE and new_idx >= 0:
            self._current_index = new_idx

        return video, new_idx

    # === MODIFICATIONS DANS LES STRATÉGIES SHUFFLE ===

    def _next_shuffle(self, current_index: int) -> Tuple[Optional['Video'], int]:
        """Mode SHUFFLE : lecture aléatoire avec ordre pré-calculé."""
        if not self.videos:
            return None, -1

        # Initialiser l'ordre shuffle si vide ou épuisé
        if not self._shuffle_order:
            self._generate_shuffle_order()

        # Avancer dans l'ordre shuffle
        self._shuffle_position += 1

        # Si fin de l'ordre shuffle, en générer un nouveau
        if self._shuffle_position >= len(self._shuffle_order):
            self._generate_shuffle_order()
            self._shuffle_position = 0

        # Récupérer l'index réel dans la playlist
        shuffle_index = self._shuffle_order[self._shuffle_position]

        # Ajouter à l'historique (pour "previous")
        if current_index >= 0:
            self._shuffle_history.append(current_index)
            # Garder seulement les N dernières entrées
            if len(self._shuffle_history) > 50:
                self._shuffle_history.pop(0)

        return self.videos[shuffle_index], shuffle_index

    def _previous_shuffle(self) -> Tuple[Optional['Video'], int]:
        """Précédent en mode SHUFFLE : utilise l'historique."""
        if not self.videos:
            return None, -1

        if not self._shuffle_history:
            # Pas d'historique, recule dans l'ordre shuffle actuel
            if self._shuffle_position > 0:
                self._shuffle_position -= 1
                shuffle_index = self._shuffle_order[self._shuffle_position]
                return self.videos[shuffle_index], shuffle_index
            else:
                return None, -1

        # Récupère la dernière vidéo de l'historique
        prev_index = self._shuffle_history.pop()

        # Ajuste la position shuffle si possible
        if self._shuffle_order and self._shuffle_position > 0:
            # Trouver où était cette vidéo dans l'ordre shuffle
            try:
                self._shuffle_position = self._shuffle_order.index(prev_index)
            except ValueError:
                self._shuffle_position = max(0, self._shuffle_position - 1)

        return self.videos[prev_index], prev_index

    # === MODIFICATION DE set_play_mode POUR GARDER LA POSITION ===

    def set_play_mode(self, mode: PlayMode) -> None:
        """Change le mode de lecture avec conservation de la position."""
        if mode == self.play_mode:
            return

        old_mode = self.play_mode
        current_video_idx = self.current_index  # Sauvegarder la position actuelle

        self.play_mode = mode

        # Réinitialisations spécifiques selon la transition
        if mode == PlayMode.SHUFFLE:
            # Génère un nouvel ordre shuffle
            self._generate_shuffle_order()

            # Si on avait une vidéo active, essayer de la garder
            if current_video_idx >= 0 and self._shuffle_order:
                try:
                    # Placer cette vidéo en premier dans le nouvel ordre
                    pos = self._shuffle_order.index(current_video_idx)
                    self._shuffle_position = pos
                except ValueError:
                    # La vidéo n'est pas dans l'ordre shuffle (normalement impossible)
                    self._shuffle_position = 0

        elif old_mode == PlayMode.SHUFFLE and mode != PlayMode.SHUFFLE:
            # Quitte le mode shuffle
            self._shuffle_order.clear()
            self._shuffle_history.clear()
            self._shuffle_position = -1

            # Conserver l'index de la vidéo actuelle si possible
            if current_video_idx >= 0:
                self._current_index = current_video_idx
            else:
                self._current_index = -1

    # === AUTRES MÉTHODES (inchangées sauf spécifié) ===

    def _load_videos_from_folder(self) -> None:
        """Parcourt le dossier récursivement et ajoute chaque vidéo valide via add_video."""
        for file_path in self.path.rglob('*'):
            self.add_video(file_path)

    @property
    def total(self) -> int:
        return len(self.videos)

    @property
    def total_duration(self) -> int:
        return sum(video.duration for video in self.videos if video.duration > 0)

    def add_video(self, file_path: Path) -> bool:
        if not file_path.exists() or file_path.is_dir():
            return False
        suffix = file_path.suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            return False
        if any(v.file_path == file_path for v in self.videos):
            return False
        self.videos.append(Video(file_path))
        return True

    def remove_video(self, identifier: Union[Video, Path, int]) -> bool:
        if isinstance(identifier, int):
            if 0 <= identifier < len(self.videos):
                # Ajuster l'index courant si on supprime la vidéo courante
                if identifier == self._current_index:
                    self._current_index = -1
                elif identifier < self._current_index:
                    self._current_index -= 1
                del self.videos[identifier]
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
                del self.videos[i]
                return True
        return False

    def move_video(self, from_index: int, to_index: int) -> bool:
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
        return True

    def swap_videos(self, idx1: int, idx2: int) -> bool:
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
        return True

    def _generate_id(self) -> str:
        if not self.path:
            return "empty_playlist"
        path_str = str(self.path.absolute())
        hash_obj = hashlib.sha256(path_str.encode('utf-8'))
        return hash_obj.hexdigest()[:8].upper()

    def _generate_shuffle_order(self) -> None:
        indices = list(range(len(self.videos)))
        random.shuffle(indices)
        if self._shuffle_order and indices[0] == self._shuffle_order[-1]:
            swap_pos = random.randint(1, len(indices) - 1)
            indices[0], indices[swap_pos] = indices[swap_pos], indices[0]
        self._shuffle_order = indices
        self._shuffle_position = -1
        self._shuffle_history.clear()

    @property
    def id(self) -> str:
        return self.unique_id