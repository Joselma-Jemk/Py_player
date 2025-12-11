from pathlib import Path
from typing import Optional, Dict, Any


class VideoState:
    """État de lecture d'une vidéo à un instant T."""

    def __init__(self):
        self.playing = False
        self.position = 0
        self._duration = 0
        self.volume = 1.0
        self.muted = False

    @property
    def duration(self) -> int:
        """Retourne la durée en ms."""
        return self._duration

    @duration.setter
    def duration(self, value: int) -> None:
        """Définit la durée en ms."""
        self._duration = max(0, value)

    @property
    def progress(self) -> float:
        """Progression en pourcentage (0.0 à 1.0)."""
        if self._duration > 0:
            return self.position / self._duration
        return 0.0

    def update_state(self, playing: Optional[bool] = None,
                     position: Optional[int] = None,
                     duration: Optional[int] = None,
                     volume: Optional[float] = None,
                     muted: Optional[bool] = None) -> None:
        """
        Met à jour l'état avec les nouvelles valeurs.
        """
        if duration is not None:
            self.duration = duration

        if playing is not None:
            self.playing = playing

        if position is not None:
            # Limite la position à la durée si elle existe
            max_pos = self._duration if self._duration > 0 else position
            self.position = max(0, min(position, max_pos))

        if volume is not None:
            self.volume = max(0.0, min(1.0, volume))

        if muted is not None:
            self.muted = muted

    def reset_state(self) -> None:
        """Réinitialise l'état de lecture (sauf la durée)."""
        self.playing = False
        self.position = 0
        self.volume = 1.0
        self.muted = False

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'état en dictionnaire pour sérialisation."""
        return {
            'playing': self.playing,
            'position': self.position,
            'duration': self._duration,
            'volume': self.volume,
            'muted': self.muted
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoState':
        """Crée un VideoState à partir d'un dictionnaire."""
        state = cls()
        state.playing = data.get('playing', False)
        state.position = data.get('position', 0)
        state.duration = data.get('duration', 0)
        state.volume = data.get('volume', 1.0)
        state.muted = data.get('muted', False)
        return state

    def __str__(self) -> str:
        """Représentation textuelle."""
        status = "▶️" if self.playing else "⏸️"
        return f"{status} {self.position}/{self._duration}ms"

class Video:
    """Représente un fichier vidéo avec ses métadonnées essentielles."""

    def __init__(self, file_path: Path):
        """
        Initialise un objet Video.

        Args:
            file_path: Chemin du fichier vidéo
        """
        self.file_path = file_path
        self.name = file_path.name
        self.parent_path = file_path.parent
        self.extension = file_path.suffix.lower()

        # État de lecture associé
        self.state = VideoState()

        # Métadonnées de base
        self.size = self._get_file_size()
        self.width = 0
        self.height = 0
        # La durée vient du state

    def _get_file_size(self) -> int:
        """Récupère la taille du fichier."""
        try:
            return self.file_path.stat().st_size
        except:
            return 0

    @property
    def progress(self):
        return self.get_progress_bar(self.state.progress)

    @property
    def resolution(self) -> str:
        """Retourne la résolution formatée."""
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return "Inconnue"

    @property
    def duration(self) -> int:
        """Retourne la durée depuis le state."""
        return self.state.duration

    @duration.setter
    def duration(self, value: int) -> None:
        """Définit la durée (met à jour le state)."""
        self.state.duration = value

    @property
    def aspect_ratio(self) -> float:
        """Calcule le ratio d'aspect (largeur/hauteur)."""
        if self.width > 0 and self.height > 0:
            return round(self.width / self.height, 2)
        return 0.0

    @property
    def is_played(self):
        return self.state.progress > 0.9 and self.state.playing

    def update_metadata(self, width: int = 0, height: int = 0, duration: int = 0) -> None:
        """
        Met à jour les métadonnées vidéo.
        """
        if width > 0:
            self.width = width
        if height > 0:
            self.height = height
        if duration > 0:
            self.duration = duration

    def update_state(self, playing: Optional[bool] = None,
                     position: Optional[int] = None,
                     duration: Optional[int] = None,
                     volume: Optional[float] = None,
                     muted: Optional[bool] = None) -> bool:
        """
        Met à jour l'état de lecture de la vidéo.

        Args:
            playing: Nouvel état de lecture
            position: Nouvelle position en ms
            duration: Nouvelle durée en ms
            volume: Nouveau volume (0.0 à 1.0)
            muted: Nouvel état muet
        """
        # Met à jour le state
        self.state.update_state(
            playing=playing,
            position=position,
            duration=duration,
            volume=volume,
            muted=muted
        )
        return True

    def get_progress_bar(self, progress: float) -> str:
        """
        Style segments modernes.
        Exemple : ▰▰▰▱▱ 60%
        """
        progress = max(0.0, min(1.0, progress))
        full_blocks = round(progress * 10)

        full = "▰"
        empty = "▱"

        bar = full * full_blocks + empty * (10 - full_blocks)

        return f"{bar}"

    def reset_state(self) -> bool:
        """Réinitialise l'état de lecture à zéro."""
        # Sauvegarde la durée actuelle
        current_duration = self.state.duration
        self.state.reset_state()
        # Restaure la durée
        self.state.duration = current_duration
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire pour sérialisation."""
        return {
            'file_path': str(self.file_path),
            'name': self.name,
            'size': self.size,
            'width': self.width,
            'height': self.height,
            'duration': self.duration,  # Récupère depuis le state
            'extension': self.extension,
            'state': self.state.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Video':
        """Crée un objet Video à partir d'un dictionnaire."""
        video = cls(Path(data['file_path']))
        video.size = data.get('size', 0)
        video.width = data.get('width', 0)
        video.height = data.get('height', 0)

        # Récupère la durée depuis les données ou depuis le state
        duration = data.get('duration', 0)

        # Restaure l'état
        if 'state' in data:
            video.state = VideoState.from_dict(data['state'])
            # S'assure que la durée est synchronisée
            if duration > 0:
                video.duration = duration
            elif video.state.duration > 0:
                # Si le state a une durée, l'utilise
                pass
        elif duration > 0:
            # Si pas de state mais une durée dans les données
            video.duration = duration

        return video

    def __str__(self) -> str:
        """Représentation lisible avec état."""
        size_mb = self.size / (1024 * 1024) if self.size > 0 else 0

        # État de lecture
        status = "▶️ Lecture" if self.state.playing else "⏸️ Pause" if self.state.position > 0 else "⏹️ Arrêt"
        progress_pct = f"{self.state.progress:.1%}" if self.state.duration > 0 else "0%"
        position_str = f"{self.state.position / 1000:.1f}s" if self.state.position > 0 else "0s"
        duration_str = f"{self.state.duration / 1000:.1f}s" if self.state.duration > 0 else "N/A"

        # Volume
        vol_icon = "🔈" if self.state.muted else "🔊"
        volume_str = f"{int(self.state.volume * 100)}%"

        return (
            f"{self.name}\n"
            f"• Taille: {size_mb:.1f} MB\n"
            f"• Résolution: {self.resolution}\n"
            f"• État: {status} ({progress_pct})\n"
            f"• Position: {position_str} / {duration_str}\n"
            f"• Volume: {vol_icon} {volume_str} \n"
            
            f"• Durée: {self.duration} \n"
            f"• Width: {self.width}\n"
            f"• Height: {self.height}\n"
        )

    def __repr__(self) -> str:
        """Représentation pour le débogage."""
        return f"Video('{self.name}', {self.resolution}, {self.duration}ms)"