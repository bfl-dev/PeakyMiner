"""
Pruebas unitarias para el módulo de publicación en Hugging Face (src/hf_publisher.py).
Verifica la creación del Dataset Card (README.md) y la llamada a HfApi.
"""

from pathlib import Path

import pytest

from src.config import ConfigurationError
from src.hf_publisher import create_dataset_card, upload_to_huggingface


def test_create_dataset_card(tmp_path: Path) -> None:
    """Verifica que create_dataset_card genere un README.md con metadatos YAML válidos."""
    stats = {
        "repositories_count": 10,
        "workflows_count": 25,
        "triggers_count": 40,
        "hf_repo": "usuario/gh-agentic-workflows",
    }
    card_path = create_dataset_card(tmp_path, stats)

    assert card_path.exists()
    assert card_path.is_file()

    content = card_path.read_text(encoding="utf-8")

    # Validar frontmatter YAML de Hugging Face
    assert "license: mit" in content
    assert "task_categories:" in content
    assert "- text-generation" in content
    assert "configs:" in content
    assert "repositories.parquet" in content
    assert "workflows.parquet" in content
    assert "workflow_triggers.parquet" in content

    # Validar estadísticas incluidas en el cuerpo
    assert "10" in content
    assert "25" in content
    assert "40" in content
    assert "usuario/gh-agentic-workflows" in content


def test_upload_to_huggingface_missing_files(tmp_path: Path) -> None:
    """Verifica que se lance FileNotFoundError si faltan las tablas Parquet requeridas."""
    with pytest.raises(FileNotFoundError, match="Faltan archivos Parquet"):
        upload_to_huggingface(tmp_path, "test/repo", token="hf_fake_token")


def test_upload_to_huggingface_missing_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que se lance ConfigurationError si falta el token de Hugging Face."""
    monkeypatch.delenv("HF_TOKEN", raising=False)

    # Crear archivos simulados requeridos
    (tmp_path / "repositories.parquet").write_bytes(b"dummy")
    (tmp_path / "workflows.parquet").write_bytes(b"dummy")
    (tmp_path / "workflow_triggers.parquet").write_bytes(b"dummy")

    with pytest.raises(ConfigurationError, match="token de autenticación para Hugging Face"):
        upload_to_huggingface(tmp_path, "test/repo", token=None)


def test_upload_to_huggingface_mocked(tmp_path: Path, mocker: pytest.MockFixture) -> None:
    """Verifica el flujo de subida simulando la API de Hugging Face."""
    # Crear archivos requeridos
    (tmp_path / "repositories.parquet").write_bytes(b"dummy")
    (tmp_path / "workflows.parquet").write_bytes(b"dummy")
    (tmp_path / "workflow_triggers.parquet").write_bytes(b"dummy")

    mock_hf_api = mocker.patch("src.hf_publisher.HfApi")
    mock_instance = mock_hf_api.return_value

    url = upload_to_huggingface(
        dataset_dir=tmp_path,
        repo_id="usuario/mi-dataset",
        token="hf_mock_token_123",
    )

    assert "https://huggingface.co/datasets/usuario/mi-dataset" == url
    mock_hf_api.assert_called_once_with(token="hf_mock_token_123")
    mock_instance.create_repo.assert_called_once_with(
        repo_id="usuario/mi-dataset",
        repo_type="dataset",
        exist_ok=True,
    )
    mock_instance.upload_folder.assert_called_once_with(
        folder_path=str(tmp_path.resolve()),
        repo_id="usuario/mi-dataset",
        repo_type="dataset",
    )
    assert (tmp_path / "README.md").exists()

