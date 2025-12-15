"""
Py player constante file
"""
import json
import sys
from pathlib import Path
from typing import Optional, Union, List
import os
import imageio_ffmpeg


def find_path(
    name: str,
    is_file: bool = True,
    parent_dir: Optional[Union[str, Path]] = r"C:\Users\Josel\PycharmProjects\JoselmaProjects\Py Player final",
    max_depth: int = -1,
    extensions: Optional[List[str]] = None,
    ignore_case: bool = False,
    first_only: bool = True,
    safe: bool = False,
    default: Optional[Union[Path, List[Path]]] = None
) -> Union[Path, List[Path], None]:
    """
    Recherche récursive d'un fichier ou dossier par son nom.
    """
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
                safe=False,
                default=default
            )
        except (ValueError, FileNotFoundError, PermissionError, OSError) as e:
            if os.getenv("DEBUG_FIND_PATH"):
                print(f"⚠️ find_path('{name}') : {e}")
            return default

    if not name:
        raise ValueError("Le nom ne peut pas être vide")

    if parent_dir is None:
        parent_dir = Path(__file__).parent.parent.parent.parent.parent
    else:
        parent_dir = Path(parent_dir)

    if not parent_dir.exists():
        raise FileNotFoundError(f"Le dossier parent n'existe pas : {parent_dir}")

    search_name = name.lower() if ignore_case else name

    if extensions:
        extensions = [ext.lower() if ignore_case else ext for ext in extensions]

    has_extension = '.' in name and is_file
    if has_extension:
        name_without_ext = name.rsplit('.', 1)[0]
        name_without_ext = name_without_ext.lower() if ignore_case else name_without_ext

    results = []

    def matches(item: Path) -> bool:
        if is_file != item.is_file():
            return False

        item_name = item.name.lower() if ignore_case else item.name

        if ignore_case:
            name_match = item_name == search_name
        else:
            name_match = item_name == name

        if is_file and has_extension and not name_match:
            item_name_no_ext = item.stem.lower() if ignore_case else item.stem
            name_match = item_name_no_ext == name_without_ext

        if not name_match:
            return False

        if extensions and is_file:
            ext = item.suffix.lower() if ignore_case else item.suffix
            return ext in extensions

        return True

    def search_recursive(current_dir: Path, current_depth: int) -> bool:
        if 0 <= max_depth < current_depth:
            return False

        try:
            for item in current_dir.iterdir():
                try:
                    if matches(item):
                        results.append(item)
                        if first_only:
                            return True

                    if item.is_dir():
                        if search_recursive(item, current_depth + 1):
                            return True
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass

        return False

    search_recursive(parent_dir, 0)

    if not results:
        return default

    if first_only:
        return results[0]
    return results


# Chargement des préférences
try:
    preferences_path = find_path("preferences.json", safe=True)
    if preferences_path and preferences_path.exists():
        with open(preferences_path, 'r', encoding='utf-8') as f:
            preferences = json.load(f)
except json.JSONDecodeError as e:
    print(f"❌ Erreur JSON dans preferences.json : {e}")
    preferences = {"icon_number": 1, "icon_name": "default_icon", "theme": "light"}


def py_player_icone(number=None) -> str:
    if number is None:
        number = preferences.get("icon_number", 1)

    icon_name = preferences.get("icon_name", "default_icon")

    icon_filenames = [
        f"{icon_name}_{number}.png",
        f"{icon_name}_{number}.ico",
        f"{icon_name}_{number}.jpg",
        f"{icon_name}_{number}.jpeg",
        f"{icon_name}_{number}.svg",
        f"{icon_name}.png",
        f"{icon_name}.ico",
    ]

    for icon_filename in icon_filenames:
        icon = find_path(
            name=icon_filename,
            is_file=True,
            ignore_case=True,
            safe=True
        )
        if icon:
            return str(icon)

    icons_dir = Path(__file__).parent.parent.parent.parent / "icons"
    if icons_dir.exists():
        for icon_filename in icon_filenames:
            icon_path = icons_dir / icon_filename
            if icon_path.exists():
                return str(icon_path)

    raise FileNotFoundError(f"Aucune icône trouvée pour '{icon_name}' (numéro: {number})")


# ============================================================================
# ICÔNES AUTOMATIQUES AVEC find_path
# ============================================================================

def get_icon_path(icon_name: str, theme: str = None) -> str:
    """Retourne le chemin d'une icône en fonction du thème."""
    if theme is None:
        theme = preferences.get("theme", "light")

    icon_filename = f"{icon_name}.png"

    # Chercher dans le dossier du thème spécifique
    if theme == "light":
        icon = find_path(
            name=icon_filename,
            parent_dir=r"C:\Users\Josel\PycharmProjects\JoselmaProjects\Py Player final\src\main\icons\light",
            safe=True
        )
    else:  # dark
        icon = find_path(
            name=icon_filename,
            parent_dir=r"C:\Users\Josel\PycharmProjects\JoselmaProjects\Py Player final\src\main\icons\dark",
            safe=True
        )

    # Si non trouvé dans le thème spécifique, chercher dans l'autre
    if not icon:
        alt_theme = "dark" if theme == "light" else "light"
        icon = find_path(
            name=icon_filename,
            parent_dir=fr"C:\Users\Josel\PycharmProjects\JoselmaProjects\Py Player final\icons\{alt_theme}",
            safe=True
        )

    return str(icon) if icon else ""

# Icônes du thème light (définies dynamiquement)
ICON_ADD = get_icon_path("add", "light")
ICON_AUDIO_FILE = get_icon_path("audio_file", "light")
ICON_DARK_MODE = get_icon_path("dark_mode", "light")
ICON_EXIT = get_icon_path("exit", "light")
ICON_FORWARD_TEN = get_icon_path("forward_ten", "light")
ICON_FULLSCREEN = get_icon_path("fullscreen", "light")
ICON_FULLSCREEN_EXIT = get_icon_path("fullscreen_exit", "light")
ICON_HELP = get_icon_path("help", "light")
ICON_INFOS = get_icon_path("infos", "light")
ICON_KEYBOARD = get_icon_path("keyboard", "light")
ICON_LIGHT_MODE = get_icon_path("light_mode", "light")
ICON_LOOP = get_icon_path("loop", "light")
ICON_METADATA = get_icon_path("metadata", "light")
ICON_MUSIC_HISTORY = get_icon_path("music_history", "light")
ICON_MUSIC_NOTE = get_icon_path("music_note", "light")
ICON_OPEN_FILE = get_icon_path("open_file", "light")
ICON_OPEN_FOLDER = get_icon_path("open_folder", "light")
ICON_PAUSE = get_icon_path("pause", "light")
ICON_PLAY = get_icon_path("play", "light")
ICON_PLAYLIST = get_icon_path("playlist", "light")
ICON_PLAYLIST_ADD = get_icon_path("playlist_add", "light")
ICON_PLAYLIST_CHECK = get_icon_path("playlist_check", "light")
ICON_PLAYLIST_REMOVE = get_icon_path("playlist_remove", "light")
ICON_RECENT_FILES = get_icon_path("recent_files", "light")
ICON_REMOVE = get_icon_path("remove", "light")
ICON_DELETE = get_icon_path("delete", "light")
ICON_REPLAY_TEN = get_icon_path("replay_ten", "light")
ICON_SAVE = get_icon_path("save", "light")
ICON_UPLOAD = get_icon_path("upload", "light")
ICON_SHUFFLE = get_icon_path("shuffle", "light")
ICON_SKIP_NEXT = get_icon_path("skip_next", "light")
ICON_SKIP_PREVIOUS = get_icon_path("skip_previous", "light")
ICON_STOP = get_icon_path("stop", "light")
ICON_VOLUME_OFF = get_icon_path("volume_off", "light")
ICON_VOLUME_UP = get_icon_path("volume_up", "light")
ICON_MINIMIZE = get_icon_path("minimize", "light")
ICON_CLOSE = get_icon_path("close", "light")
ICON_PLAYED = get_icon_path("check_circle", "light")

# Icônes du thème dark (définies dynamiquement)
ICON_DARK_ADD = get_icon_path("add", "dark")
ICON_DARK_AUDIO_FILE = get_icon_path("audio_file", "dark")
ICON_DARK_DARK_MODE = get_icon_path("dark_mode", "dark")
ICON_DARK_EXIT = get_icon_path("exit", "dark")
ICON_DARK_FORWARD_TEN = get_icon_path("forward_ten", "dark")
ICON_DARK_FULLSCREEN = get_icon_path("fullscreen", "dark")
ICON_DARK_FULLSCREEN_EXIT = get_icon_path("fullscreen_exit", "dark")
ICON_DARK_HELP = get_icon_path("help", "dark")
ICON_DARK_INFOS = get_icon_path("infos", "dark")
ICON_DARK_KEYBOARD = get_icon_path("keyboard", "dark")
ICON_DARK_LIGHT_MODE = get_icon_path("light_mode", "dark")
ICON_DARK_LOOP = get_icon_path("loop", "dark")
ICON_DARK_METADATA = get_icon_path("metadata", "dark")
ICON_DARK_MUSIC_HISTORY = get_icon_path("music_history", "dark")
ICON_DARK_MUSIC_NOTE = get_icon_path("music_note", "dark")
ICON_DARK_OPEN_FILE = get_icon_path("open_file", "dark")
ICON_DARK_OPEN_FOLDER = get_icon_path("open_folder", "dark")
ICON_DARK_PAUSE = get_icon_path("pause", "dark")
ICON_DARK_PLAY = get_icon_path("play", "dark")
ICON_DARK_PLAYLIST = get_icon_path("playlist", "dark")
ICON_DARK_PLAYLIST_ADD = get_icon_path("playlist_add", "dark")
ICON_DARK_PLAYLIST_CHECK = get_icon_path("playlist_check", "dark")
ICON_DARK_PLAYLIST_REMOVE = get_icon_path("playlist_remove", "dark")
ICON_DARK_RECENT_FILES = get_icon_path("recent_files", "dark")
ICON_DARK_REMOVE = get_icon_path("remove", "dark")
ICON_DARK_REPLAY_TEN = get_icon_path("replay_ten", "dark")
ICON_DARK_SAVE = get_icon_path("save", "dark")
ICON_DARK_UPLOAD = get_icon_path("upload", "dark")
ICON_DARK_SHUFFLE = get_icon_path("shuffle", "dark")
ICON_DARK_SKIP_NEXT = get_icon_path("skip_next", "dark")
ICON_DARK_SKIP_PREVIOUS = get_icon_path("skip_previous", "dark")
ICON_DARK_STOP = get_icon_path("stop", "dark")
ICON_DARK_VOLUME_OFF = get_icon_path("volume_off", "dark")
ICON_DARK_VOLUME_UP = get_icon_path("volume_up", "dark")

# Icône du thème actuel (pour utilisation générale)
def get_current_theme_icon(icon_name: str) -> str:
    """Retourne l'icône pour le thème actuel."""
    theme = preferences.get("theme", "light")
    return get_icon_path(icon_name, theme)

# Récupération des chemins avec gestion d'erreur
try:
    icon_directory = py_player_icone()
except FileNotFoundError as e:
    print(f"⚠️ {e}")
    icon_directory = ""

# Chemins des ressources
chemin_video = find_path("samplevideo.mp4", safe=True, default=None)
chemin_video = str(chemin_video) if chemin_video else ""

font_dir = find_path("material-symbols-outlined.ttf", safe=True, default=None)
font_dir = str(font_dir) if font_dir else ""


def pyplayer_directory() -> Path:
    pyplayer_dir = Path.home() / ".pyplayer"
    try:
        pyplayer_dir.mkdir(parents=True, exist_ok=True)
        return pyplayer_dir
    except (PermissionError, OSError) as e:
        print(f"❌ Erreur lors de la création du répertoire : {e}")
        return Path("/tmp/.pyplayer")


# Constantes de couleur
PRINCIPAL_COLOR = "#1c1c1e"
SECONDARY_COLOR = "#2c2c2e"
THIRD_COLOR = "#3a3a3c"
HOVER_COLOR = "#48484a"
PRESSED_COLOR = "#636366"
PRINCIPAL_TEXT_COLOR = "#f2f2f7"
OK_ONE_COLOR = "#2196F3"
ACCENT_COLOR = "#ff3b30"


# Extensions supportées

VIDEO_EXTENSIONS = {
        '.mp4', '.avi', '.mkv', '.mov', '.webm',
        '.wmv', '.flv', '.mpeg', '.mpg', '.m4v'
    }
SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}

SEPARATOR_ICON = "⮞"  # Icône entre nom et progression (modifiable)
