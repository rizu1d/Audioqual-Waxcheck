"""
Tests basicos de UI.

Verifica que los componentes principales se instancian sin crash.
No requiere archivos de audio.
"""
import sys
import os


def run_tests():
    """
    Ejecuta tests basicos de UI.

    Returns:
        Lista de dicts con resultados: {id, description, status, detail, test_type}
    """
    results = []

    # Asegurar que src esta en path
    src_parent = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if src_parent not in sys.path:
        sys.path.insert(0, src_parent)

    # Test: AudioAnalyzer se instancia
    results.append(_test_analyzer_instantiation())

    # Test: AudioPlayer se instancia
    results.append(_test_player_instantiation())

    # Test: App se instancia y cierra
    results.append(_test_app_instantiation())

    return results


def _test_analyzer_instantiation():
    """Verifica que AudioAnalyzer se instancia sin error."""
    try:
        from src.core.analyzer import AudioAnalyzer
        analyzer = AudioAnalyzer()
        assert analyzer is not None
        return {
            "id": "UI_001",
            "description": "AudioAnalyzer se instancia correctamente",
            "test_type": "ui",
            "status": "PASS",
            "detail": "AudioAnalyzer() OK",
        }
    except Exception as e:
        return {
            "id": "UI_001",
            "description": "AudioAnalyzer se instancia correctamente",
            "test_type": "ui",
            "status": "FAIL",
            "detail": f"Error: {e}",
        }


def _test_player_instantiation():
    """Verifica que AudioPlayer se instancia sin error."""
    try:
        from src.gui.audio_player import AudioPlayer
        player = AudioPlayer()
        assert player is not None
        return {
            "id": "UI_002",
            "description": "AudioPlayer se instancia correctamente",
            "test_type": "ui",
            "status": "PASS",
            "detail": "AudioPlayer() OK",
        }
    except Exception as e:
        return {
            "id": "UI_002",
            "description": "AudioPlayer se instancia correctamente",
            "test_type": "ui",
            "status": "FAIL",
            "detail": f"Error: {e}",
        }


def _test_app_instantiation():
    """Verifica que AudioQualApp se instancia y cierra limpiamente."""
    try:
        from src.app import AudioQualApp
        app = AudioQualApp()

        # Verificar que los componentes principales existen
        assert hasattr(app, "main_window"), "main_window no existe"
        assert hasattr(app, "analyzer"), "analyzer no existe"
        assert hasattr(app, "audio_player"), "audio_player no existe"
        assert hasattr(app.main_window, "results_table"), "results_table no existe"

        # Cerrar limpiamente
        app.root.destroy()

        return {
            "id": "UI_003",
            "description": "AudioQualApp se instancia y cierra limpiamente",
            "test_type": "ui",
            "status": "PASS",
            "detail": "App creada, componentes verificados, cerrada OK",
        }
    except Exception as e:
        return {
            "id": "UI_003",
            "description": "AudioQualApp se instancia y cierra limpiamente",
            "test_type": "ui",
            "status": "FAIL",
            "detail": f"Error: {e}",
        }
