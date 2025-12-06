"""
Py player constante file
"""
import json
from pathlib import Path
from typing import Optional, Union, List
import os


def find_path(
    name: str,
    is_file: bool = True,
    parent_dir: Optional[Union[str, Path]] = None,
    max_depth: int = -1,
    extensions: Optional[List[str]] = None,
    ignore_case: bool = False,
    first_only: bool = True,
    safe: bool = False,
    default: Optional[Union[Path, List[Path]]] = None
) -> Union[Path, List[Path], None]:
    """
    Recherche récursive d'un fichier ou dossier par son nom.

    Args:
        name: Nom à rechercher (peut inclure une extension)
        is_file: True pour chercher un fichier, False pour un dossier
        parent_dir: Dossier de départ pour la recherche (chemin str ou Path)
        max_depth: Profondeur maximale (-1 = illimitée, 0 = parent_dir uniquement)
        extensions: Liste d'extensions à filtrer (ex: ['.py', '.txt'])
        ignore_case: Ignorer la casse lors de la recherche
        first_only: Retourner seulement le premier résultat trouvé
        safe: Mode sécurisé (ne lève pas d'exception, utilise le default)
        default: Valeur par défaut si rien trouvé (surtout utile avec safe=True)

    Returns:
        - Path du premier élément trouvé (si first_only=True)
        - Liste de Paths si first_only=False
        - None si rien trouvé et pas de default
        - default si spécifié et rien trouvé

    Raises:
        ValueError: Si le nom est vide (uniquement si safe=False)
        FileNotFoundError: Si parent_dir n'existe pas (uniquement si safe=False)
    """

    # Mode sécurisé : wrapper pour gérer les exceptions
    if safe:
        try:
            return find_path(
                name=name,
                is_file=is_file,
                parent_dir=parent_dir,
                max_depth=max_depth,
                extensions=extensions,
                ignore_case=ignore_case,
                first_only=first_only,
                safe=False,  # Appel récursif sans safe
                default=default
            )
        except (ValueError, FileNotFoundError, PermissionError, OSError) as e:
            # Affiche un avertissement en mode debug (optionnel)
            if os.getenv("DEBUG_FIND_PATH"):
                print(f"⚠️ find_path('{name}') : {e}")
            return default

    # ========== MODE NORMAL (avec exceptions) ==========

    # Validation des arguments
    if not name:
        raise ValueError("Le nom ne peut pas être vide")

    # Déterminer le dossier de départ
    if parent_dir is None:
        # Par défaut : remonte de 5 niveaux depuis ce fichier
        parent_dir = Path(__file__).parent.parent.parent.parent.parent
    else:
        parent_dir = Path(parent_dir)

    if not parent_dir.exists():
        raise FileNotFoundError(f"Le dossier parent n'existe pas : {parent_dir}")

    # Préparer le nom pour la recherche
    search_name = name.lower() if ignore_case else name

    # Préparer les extensions
    if extensions:
        extensions = [ext.lower() if ignore_case else ext for ext in extensions]

    # Vérifier si on cherche avec extension spécifique
    has_extension = '.' in name and is_file
    if has_extension:
        name_without_ext = name.rsplit('.', 1)[0]
        name_without_ext = name_without_ext.lower() if ignore_case else name_without_ext

    results = []

    # Fonction de vérification
    def matches(item: Path) -> bool:
        """Vérifie si l'item correspond aux critères."""
        # Vérifier type (fichier/dossier)
        if is_file != item.is_file():
            return False

        # Vérifier le nom
        item_name = item.name.lower() if ignore_case else item.name

        if ignore_case:
            name_match = item_name == search_name
        else:
            name_match = item_name == name

        # Si on cherche un fichier et que le nom a une extension,
        # vérifier aussi sans extension
        if is_file and has_extension and not name_match:
            item_name_no_ext = item.stem.lower() if ignore_case else item.stem
            name_match = item_name_no_ext == name_without_ext

        if not name_match:
            return False

        # Filtrer par extension si spécifié
        if extensions and is_file:
            ext = item.suffix.lower() if ignore_case else item.suffix
            return ext in extensions

        return True

    # Recherche récursive avec contrôle de profondeur
    def search_recursive(current_dir: Path, current_depth: int) -> bool:
        """Retourne True si on doit arrêter la recherche (first_only)."""
        if max_depth >= 0 and current_depth > max_depth:
            return False

        try:
            for item in current_dir.iterdir():
                try:
                    if matches(item):
                        results.append(item)
                        if first_only:
                            return True  # Arrêter la recherche

                    # Si c'est un dossier, explorer récursivement
                    if item.is_dir():
                        if search_recursive(item, current_depth + 1):
                            return True
                except (PermissionError, OSError):
                    continue  # Ignorer les éléments sans permission
        except (PermissionError, OSError):
            pass  # Ignorer les erreurs d'accès du dossier courant

        return False

    # Démarrer la recherche
    search_recursive(parent_dir, 0)

    # Retourner les résultats
    if not results:
        return default

    if first_only:
        return results[0]
    return results


# Chargement des préférences avec find_path (mode sécurisé)
try:
    preferences_path = find_path("preferences.json", safe=True)
    if preferences_path and preferences_path.exists():
        with open(preferences_path, 'r', encoding='utf-8') as f:
            preferences = json.load(f)
    else:
        preferences = {"icon_number": 1, "icon_name": "default_icon"}
        print("⚠️ Fichier preferences.json non trouvé, utilisation des valeurs par défaut")
except json.JSONDecodeError as e:
    print(f"❌ Erreur JSON dans preferences.json : {e}")
    preferences = {"icon_number": 1, "icon_name": "default_icon"}


def py_player_icone(number=None) -> str:
    """
    Retourne le chemin de l'icône selon les préférences.

    Args:
        number: Numéro de l'icône (utilise les préférences si None)

    Returns:
        Chemin complet de l'icône

    Raises:
        FileNotFoundError: Si l'icône n'existe pas
    """
    if number is None:
        number = preferences.get("icon_number", 1)

    icon_name = preferences.get("icon_name", "default_icon")

    # Essayer plusieurs noms d'icônes possibles
    icon_filenames = [
        f"{icon_name}_{number}.png",
        f"{icon_name}_{number}.ico",
        f"{icon_name}_{number}.jpg",
        f"{icon_name}_{number}.jpeg",
        f"{icon_name}_{number}.svg",
        f"{icon_name}.png",  # Sans numéro
        f"{icon_name}.ico",
    ]

    # Chercher chaque icône possible
    for icon_filename in icon_filenames:
        icon = find_path(
            name=icon_filename,
            is_file=True,
            ignore_case=True,
            safe=True
        )
        if icon:
            return str(icon)

    # Si aucune icône spécifique trouvée, chercher dans le dossier icons
    icons_dir = Path(__file__).parent.parent.parent.parent / "icons"
    if icons_dir.exists():
        for icon_filename in icon_filenames:
            icon_path = icons_dir / icon_filename
            if icon_path.exists():
                return str(icon_path)

    raise FileNotFoundError(f"Aucune icône trouvée pour '{icon_name}' (numéro: {number})")

# Récupération des chemins avec gestion d'erreur
try:
    icon_directory = py_player_icone()
except FileNotFoundError as e:
    print(f"⚠️ {e}")
    icon_directory = ""

# Utilisation de find_path pour les autres chemins
chemin_video = find_path("samplevideo.mp4", safe=True, default=None)
chemin_video = str(chemin_video) if chemin_video else ""

font_dir = find_path("material-symbols-outlined.ttf", safe=True, default=None)
font_dir = str(font_dir) if font_dir else ""


def pyplayer_directory() -> Path:
    """
    Crée et retourne le répertoire .pyplayer dans le home utilisateur.

    Returns:
        Path du répertoire .pyplayer
    """
    pyplayer_dir = Path.home() / ".pyplayer"
    try:
        pyplayer_dir.mkdir(parents=True, exist_ok=True)
        return pyplayer_dir
    except (PermissionError, OSError) as e:
        print(f"❌ Erreur lors de la création du répertoire : {e}")
        # Fallback sur un répertoire temporaire
        return Path("/tmp/.pyplayer")


# Constantes de couleur
PRINCIPAL_COLOR = "#1c1c1e"
SECONDARY_COLOR = "#2c2c2e"
THIRD_COLOR = "#3a3a3c"
HOVER_COLOR = "#48484a"
PRESSED_COLOR = "#636366"
PRINCIPAL_TEXT_COLOR = "#f2f2f7"

# Extensions supportées (optionnel)
SUPPORTED_VIDEO_FORMATS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"}