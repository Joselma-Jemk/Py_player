from pathlib import Path
from typing import Optional, Dict, Any

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

        # Métadonnées de base
        self.size = self._get_file_size()
        self.width = 0
        self.height = 0
        self.duration = 0

        # État de lecture associé
        self.state = VideoState()

    def _get_file_size(self) -> int:
        """Récupère la taille du fichier."""
        try:
            return self.file_path.stat().st_size
        except:
            return 0

    @property
    def resolution(self) -> str:
        """Retourne la résolution formatée."""
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return "Inconnue"

    @property
    def aspect_ratio(self) -> float:
        """Calcule le ratio d'aspect (largeur/hauteur)."""
        if self.width > 0 and self.height > 0:
            return round(self.width / self.height, 2)
        return 0.0

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
            self.state.duration = duration  # Met à jour aussi l'état

    def update_state(self, playing: Optional[bool] = None, position: Optional[int] = None,
                    volume: Optional[float] = None, muted: Optional[bool] = None) -> bool:
        """
        Met à jour l'état de lecture de la vidéo.

        Args:
            playing: Nouvel état de lecture
            position: Nouvelle position en ms
            volume: Nouveau volume (0.0 à 1.0)
            muted: Nouvel état muet
        """
        self.state.update_state(playing, position, volume, muted)
        return True


    def reset_state(self) -> bool:
        """Réinitialise l'état de lecture à zéro."""
        self.state.reset_state()
        # Conserve la durée de la vidéo
        self.state.duration = self.duration
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire pour sérialisation."""
        return {
            'file_path': str(self.file_path),
            'name': self.name,
            'size': self.size,
            'width': self.width,
            'height': self.height,
            'duration': self.duration,
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
        video.duration = data.get('duration', 0)

        # Restaure l'état
        if 'state' in data:
            video.state = VideoState.from_dict(data['state'])
            video.state.duration = video.duration  # S'assure que la durée est correcte

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
            f"• Volume: {vol_icon} {volume_str}"
        )

    def __repr__(self) -> str:
        """Représentation pour le débogage."""
        return f"Video('{self.name}', {self.resolution})"

class VideoState:
    """État de lecture d'une vidéo à un instant T."""

    def __init__(self):
        self.playing = False
        self.position = 0
        self.duration = 0
        self.volume = 1.0
        self.muted = False

    @property
    def progress(self) -> float:
        """Progression en pourcentage (0.0 à 1.0)."""
        if self.duration > 0:
            return self.position / self.duration
        return 0.0

    def update_state(self, playing: Optional[bool] = None, position: Optional[int] = None,
                    volume: Optional[float] = None, muted: Optional[bool] = None) -> None:
        """
        Met à jour l'état avec les nouvelles valeurs.
        """
        if playing is not None:
            self.playing = playing
        if position is not None:
            self.position = max(0, min(position, self.duration))
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
            'duration': self.duration,
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
        return f"{status} {self.position}/{self.duration}ms"
