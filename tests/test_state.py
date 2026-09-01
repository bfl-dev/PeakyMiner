"""
Pruebas unitarias para el gestor de estado y checkpoints (src/state.py).
"""

from pathlib import Path
import json

from src.state import StateManager


def test_state_manager_save_and_load(tmp_path: Path) -> None:
    """Verifica que el StateManager guarde de forma atómica y recupere el estado correctamente."""
    input_file = tmp_path / "repos.csv"
    input_file.write_text("repo\norg/repo1\norg/repo2", encoding="utf-8")

    state_mgr = StateManager(input_file=input_file)
    assert not state_mgr.has_checkpoint()
    assert state_mgr.load_checkpoint() == {}

    # Guardar resultados
    results = {"org/repo1": True, "org/repo2": False}
    state_mgr.save_checkpoint(results, total_repos=2, metadata={"status": "in_progress"})

    assert state_mgr.has_checkpoint()
    loaded = state_mgr.load_checkpoint()
    assert loaded == results

    # Verificar estructura del JSON
    with open(state_mgr.checkpoint_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_repos"] == 2
    assert data["completed_count"] == 2
    assert data["results"] == results

    # Eliminar checkpoint
    state_mgr.delete_checkpoint()
    assert not state_mgr.has_checkpoint()
    assert not state_mgr.checkpoint_path.exists()


def test_state_manager_custom_path(tmp_path: Path) -> None:
    """Verifica el uso de una ruta personalizada para el checkpoint."""
    input_file = tmp_path / "data.csv"
    input_file.write_text("repo\nfoo/bar", encoding="utf-8")
    custom_ckpt = tmp_path / "custom" / "my_state.json"

    state_mgr = StateManager(input_file=input_file, custom_checkpoint_path=custom_ckpt)
    assert state_mgr.checkpoint_path == custom_ckpt

    state_mgr.save_checkpoint({"foo/bar": True}, total_repos=1)
    assert custom_ckpt.exists()
    assert state_mgr.load_checkpoint() == {"foo/bar": True}


def test_state_manager_corrupted_file(tmp_path: Path) -> None:
    """Verifica que un archivo de checkpoint corrupto o vacío se maneje sin fallar."""
    input_file = tmp_path / "repos.csv"
    input_file.write_text("repo\nfoo/bar", encoding="utf-8")
    custom_ckpt = tmp_path / "corrupted.json"
    custom_ckpt.write_text("{ invalid json ...", encoding="utf-8")

    state_mgr = StateManager(input_file=input_file, custom_checkpoint_path=custom_ckpt)
    assert state_mgr.has_checkpoint()
    # Debe retornar diccionario vacío sin lanzar excepción
    assert state_mgr.load_checkpoint() == {}

