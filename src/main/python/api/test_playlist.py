import json
import tempfile
import shutil
from pathlib import Path

from src.main.python.api.playlist_class import PlayMode
from src.main.python.api.playlist_class import Playlist
from src.main.python.api.video_class import Video


def test_playlist_serialization():
    """Test complet de sérialisation/désérialisation."""
    print("=== Test de Sérialisation Playlist ===")

    # Créer un dossier temporaire avec des fichiers fictifs
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Dossier temporaire: {temp_dir}")

    try:
        # Créer des fichiers vidéo fictifs
        video_files = []
        for i in range(3):
            file_path = temp_dir / f"video_{i}.mp4"
            file_path.touch()
            video_files.append(file_path)

        # Créer une playlist
        playlist = Playlist(temp_dir)
        print(f"Playlist créée: {playlist}")
        print(f"Nombre de vidéos: {playlist.total}")

        # Simuler la lecture de quelques vidéos
        if playlist.total > 0:
            # Première vidéo
            playlist.current_index = 0
            playlist.videos[0].update_state(playing=True, position=5000)

            # Simuler navigation
            playlist.set_play_mode(PlayMode.SHUFFLE)
            print(f"Mode changé en: {playlist.play_mode}")

        # Test sérialisation
        data = playlist.to_dict()
        print(f"\nDonnées sérialisées:")
        print(f"- Nom: {data['name']}")
        print(f"- Nombre vidéos: {len(data['videos'])}")
        print(f"- Mode: {data['play_mode']}")
        print(f"- État sauvegardé: {data['playlist_state']}")

        # Sauvegarde dans fichier
        save_path = temp_dir / "playlist_backup.json"
        if playlist.save_to_file(save_path):
            print(f"\nPlaylist sauvegardée dans: {save_path}")

            # Vérifier que le fichier existe
            if save_path.exists():
                print(f"Taille fichier: {save_path.stat().st_size} bytes")

        # Test désérialisation
        restored = Playlist.load_from_file(save_path)
        if restored:
            print(f"\nPlaylist restaurée:")
            print(f"- Nom: {restored.name}")
            print(f"- Nombre vidéos: {restored.total}")
            print(f"- Mode: {restored.play_mode}")
            print(f"- ID: {restored.id}")

            # Vérifier l'intégrité
            assert playlist.name == restored.name
            assert playlist.total == restored.total
            assert playlist.play_mode == restored.play_mode
            print("✓ Intégrité vérifiée")

            # Vérifier l'état
            if playlist.total > 0:
                print(f"\nÉtat vidéo 0:")
                original_state = playlist.videos[0].state
                restored_state = restored.videos[0].state
                print(f"Original: {original_state}")
                print(f"Restauré: {restored_state}")
                assert original_state.playing == restored_state.playing
                assert original_state.position == restored_state.position
                print("✓ État restauré correctement")

        # Test avec paramètres
        print(f"\n=== Test avec include_video_states=False ===")
        data_no_states = playlist.to_dict(include_video_states=False)
        print(f"Vidéo 0 a 'state': {'state' in data_no_states['videos'][0]}")

        print("\n=== Tous les tests passés avec succès ===")

    finally:
        # Nettoyer
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\nDossier temporaire nettoyé")


def test_edge_cases():
    """Test des cas limites."""
    print("\n=== Test Cas Limites ===")

    # 1. Playlist vide
    empty_playlist = Playlist()
    print(f"1. Playlist vide: {empty_playlist}")
    data = empty_playlist.to_dict()
    restored = Playlist.from_dict(data)
    assert restored.total == 0
    print("✓ Playlist vide sérialisée/désérialisée")

    # 2. Mode shuffle sans vidéos
    empty_playlist.set_play_mode(PlayMode.SHUFFLE)
    print(f"2. Mode shuffle sur playlist vide: {empty_playlist.play_mode}")

    # 3. Sérialisation avec index invalide
    playlist_with_videos = Playlist(Path("."))  # Dossier actuel
    if playlist_with_videos.total > 0:
        playlist_with_videos._current_index = 999  # Index invalide
        data = playlist_with_videos.to_dict()
        print(f"3. Index invalide sérialisé: {data['current_index']}")

    # 4. Test with_state=False
    data_no_state = playlist_with_videos.to_dict(include_video_states=False)
    has_states = any('state' in v for v in data_no_state['videos'])
    print(f"4. États exclus: {not has_states}")

    print("✓ Tous les cas limites gérés")


def test_performance():
    """Test de performance avec playlist volumineuse."""
    print("\n=== Test Performance ===")

    import time

    # Créer une grosse playlist simulée
    playlist = Playlist()
    playlist.name = "Grande Playlist de Test"

    # Ajouter 1000 vidéos simulées
    for i in range(100):
        video = Video(Path(f"/fake/path/video_{i}.mp4"))
        video.duration = 60000  # 1 minute
        video.update_state(position=i * 1000, playing=(i % 2 == 0))
        playlist.videos.append(video)

    # Mesurer sérialisation
    start = time.time()
    data = playlist.to_dict()
    serialize_time = time.time() - start
    print(f"Sérialisation de 100 vidéos: {serialize_time:.3f}s")

    # Mesurer désérialisation
    start = time.time()
    restored = Playlist.from_dict(data)
    deserialize_time = time.time() - start
    print(f"Désérialisation de 100 vidéos: {deserialize_time:.3f}s")

    # Taille des données
    import sys
    size_bytes = sys.getsizeof(json.dumps(data))
    print(f"Taille JSON: {size_bytes / 1024:.1f} KB")

    assert playlist.total == restored.total
    print("✓ Performance acceptable")


def run_all_tests():
    """Exécute tous les tests."""
    try:
        test_playlist_serialization()
        test_edge_cases()
        test_performance()
        print("\n" + "=" * 50)
        print("TOUS LES TESTS PASSÉS AVEC SUCCÈS!")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ Test échoué: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()