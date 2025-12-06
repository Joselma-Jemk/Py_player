"""
La plus petite unie
"""
from pathlib import Path
from typing import Optional

from sympy import false


class Video:
    """Représente un fichier vidéo avec ses métadonnées essentielles."""

    def __init__(self, file_path: Path, width: int = 0, height: int = 0, duration: int = 0):
        """
        Initialise un objet Video.

        Args:
            file_path: Chemin du fichier vidéo
            width: Largeur en pixels (0 si inconnu)
            height: Hauteur en pixels (0 si inconnu)
            duration: Durée en millisecondes
        """
        self.file_path: Path = file_path
        self.name: str = file_path.name
        self.extension: str = file_path.suffix.lower()

        # Métadonnées vidéo
        self.width: int = width
        self.height: int = height
        self.duration: int = duration

        # Propriétés calculées
        self.size: int = self._get_file_size()
        self.aspect_ratio: float = self._calculate_aspect_ratio()
        self.file_hash: Optional[str] = None  # Peut être calculé ultérieurement

    def _get_file_size(self) -> int:
        """Récupère la taille du fichier avec gestion d'erreur."""
        try:
            return self.file_path.stat().st_size
        except (FileNotFoundError, OSError):
            return 0

    def _calculate_aspect_ratio(self) -> float:
        """Calcule le ratio d'aspect (largeur/hauteur)."""
        if self.width > 0 and self.height > 0:
            return round(self.width / self.height, 2)
        return 0.0

    @property
    def is_loaded(self) -> bool:
        """Vérifie si les métadonnées vidéo sont chargées."""
        return self.duration > 0

    @property
    def resolution(self) -> str:
        """Retourne la résolution formatée (ex: '1920x1080')."""
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return "Inconnue"

    def is_same_as(self, other: 'Video') -> bool:
        """
        Compare deux vidéos pour vérifier si c'est le même fichier.

        Stratégies par ordre de fiabilité:
        1. Hash du fichier
        2. Chemin absolu
        3. Nom + taille + date de modification
        """
        if not isinstance(other, Video):
            return False

        # 1. Comparaison par hash
        if self.file_hash and other.file_hash:
            return self.file_hash == other.file_hash

        # 2. Comparaison par chemin absolu
        try:
            if self.file_path.resolve() == other.file_path.resolve():
                return True
        except OSError:
            pass

        # 3. Comparaison par métadonnées
        try:
            if not self.file_path.exists() or not other.file_path.exists():
                return False

            self_stat = self.file_path.stat()
            other_stat = other.file_path.stat()

            return (self.name == other.name and
                    self_stat.st_size == other_stat.st_size and
                    self_stat.st_mtime == other_stat.st_mtime)
        except OSError:
            return False

    def __eq__(self, other: object) -> bool:
        """Opérateur d'égalité utilisant is_same_as."""
        if not isinstance(other, Video):
            return NotImplemented
        return self.is_same_as(other)

    def __hash__(self) -> int:
        """Hash pour utilisation dans des collections."""
        # Priorité au hash de fichier
        if self.file_hash:
            return hash(self.file_hash)

        # Sinon, chemin absolu
        try:
            return hash(str(self.file_path.resolve()))
        except OSError:
            # Fallback sur l'ID d'objet
            return hash(id(self))

    def __repr__(self) -> str:
        """Représentation pour le débogage."""
        status = "chargé" if self.is_loaded else "non chargé"
        return f"<Video '{self.name}' {self.resolution} {status}>"

    def __str__(self) -> str:
        """Représentation lisible."""
        return (
            f"Vidéo: {self.name}\n"
            f"  • Taille: {self.size:,} octets\n"
            f"  • Résolution: {self.resolution}\n"
            f"  • Ratio: {self.aspect_ratio:.2f}\n"
            f"  • Durée: {self.duration} ms\n"
            f"  • État: {'Chargé' if self.is_loaded else 'Non chargé'}"
        )

    def calculate_hash(self) -> Optional[str]:
        """Calcule et stocke le hash MD5 du fichier."""
        import hashlib

        if not self.file_path.exists() or self.size == 0:
            self.file_hash = None
            return None

        try:
            hasher = hashlib.md5()
            with open(self.file_path, 'rb') as f:
                # Lire par blocs pour les gros fichiers
                for chunk in iter(lambda: f.read(65536), b''):
                    hasher.update(chunk)
            self.file_hash = hasher.hexdigest()
            return self.file_hash
        except (OSError, IOError):
            self.file_hash = None
            return None

    def update_metadata(self, width: int = 0, height: int = 0, duration: int = 0) -> None:
        """
        Met à jour les métadonnées vidéo.

        Args:
            width: Nouvelle largeur
            height: Nouvelle hauteur
            duration: Nouvelle durée
        """
        if width > 0:
            self.width = width
        if height > 0:
            self.height = height
        if duration > 0:
            self.duration = duration

        # Recalculer le ratio d'aspect si nécessaire
        if width > 0 or height > 0:
            self.aspect_ratio = self._calculate_aspect_ratio()

