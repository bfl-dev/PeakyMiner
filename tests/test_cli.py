"""
Pruebas de integración para la CLI (src/cli.py), modelos y procesamiento de CSV.
"""

from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.cli import app
from src.csv_processor import detect_repo_column, load_repositories_from_csv, save_results_to_csv
from src.models import RepoTarget

runner = CliRunner()


# --- Pruebas de Modelos (RepoTarget) ---

@pytest.mark.parametrize(
    ("raw_input", "expected_owner", "expected_name"),
    [
        ("torvalds/linux", "torvalds", "linux"),
        ("https://github.com/octocat/Hello-World", "octocat", "Hello-World"),
        ("http://github.com/octocat/Hello-World.git", "octocat", "Hello-World"),
        ("git@github.com:openai/openai-python.git", "openai", "openai-python"),
        ("https://github.com/owner/repo/tree/main", "owner", "repo"),
        ("https://github.com/owner/repo/", "owner", "repo"),
    ],
)
def test_repo_target_valid_inputs(raw_input: str, expected_owner: str, expected_name: str) -> None:
    """Verifica el análisis y normalización de diversas representaciones de repositorios."""
    target = RepoTarget.from_raw(raw_input)
    assert target.owner == expected_owner
    assert target.name == expected_name
    assert target.full_name == f"{expected_owner}/{expected_name}"
    assert target.url == f"https://github.com/{expected_owner}/{expected_name}"


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        "invalid_without_slash",
        "https://otherdomain.com/owner",
        123,
    ],
)
def test_repo_target_invalid_inputs(invalid_input: object) -> None:
    """Verifica que entradas no conformes levanten ValueError."""
    with pytest.raises(ValueError):
        RepoTarget.from_raw(invalid_input)  # type: ignore[arg-type]


# --- Pruebas de CSV Processor ---

def test_detect_repo_column() -> None:
    """Verifica la detección automática de nombres comunes de columnas."""
    df1 = pd.DataFrame({"Repository": ["owner/repo"]})
    assert detect_repo_column(df1) == "Repository"

    df2 = pd.DataFrame({"url": ["https://github.com/owner/repo"], "extra": [1]})
    assert detect_repo_column(df2) == "url"

    df3 = pd.DataFrame({"single_custom_col": ["owner/repo"]})
    assert detect_repo_column(df3) == "single_custom_col"

    df4 = pd.DataFrame({"col_a": [1], "col_b": [2]})
    with pytest.raises(ValueError, match="No se pudo identificar"):
        detect_repo_column(df4)


def test_load_and_save_csv(tmp_path: Path) -> None:
    """Verifica el ciclo de lectura y guardado enriquecido con filtrado."""
    input_file = tmp_path / "input.csv"
    output_file = tmp_path / "output.csv"

    df_in = pd.DataFrame({
        "repo": ["org/repo-pos", "org/repo-neg"],
        "category": ["ai", "tool"],
    })
    df_in.to_csv(input_file, index=False)

    df_loaded, repo_col, targets = load_repositories_from_csv(input_file)
    assert repo_col == "repo"
    assert len(targets) == 2

    results = {"org/repo-pos": True, "org/repo-neg": False}

    # Guardar todos los registros
    count_all = save_results_to_csv(
        df=df_loaded,
        repo_col=repo_col,
        results=results,
        output_path=output_file,
        filter_positive_only=False,
    )
    assert count_all == 2
    df_out = pd.read_csv(output_file)
    assert "has_ghaw" in df_out.columns
    assert "ghaw_status" in df_out.columns
    assert bool(df_out.loc[df_out["repo"] == "org/repo-pos", "has_ghaw"].values[0]) is True
    assert bool(df_out.loc[df_out["repo"] == "org/repo-neg", "has_ghaw"].values[0]) is False

    # Guardar solo positivos
    filtered_output = tmp_path / "filtered.csv"
    count_pos = save_results_to_csv(
        df=df_loaded,
        repo_col=repo_col,
        results=results,
        output_path=filtered_output,
        filter_positive_only=True,
    )
    assert count_pos == 1
    df_filtered = pd.read_csv(filtered_output)
    assert len(df_filtered) == 1
    assert df_filtered["repo"].values[0] == "org/repo-pos"


# --- Pruebas de la CLI con CliRunner ---

def test_cli_help() -> None:
    """Verifica que el flag --help funcione correctamente."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "PeakyMiner" in result.stdout
    assert "--output" in result.stdout


def test_cli_version() -> None:
    """Verifica que el flag --version muestre la versión."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "PeakyMiner" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_missing_input_file(tmp_path: Path) -> None:
    """Verifica el error cuando el archivo de entrada no existe."""
    non_existent = tmp_path / "not_found.csv"
    result = runner.invoke(app, [str(non_existent), "--token", "fake_token"])
    assert result.exit_code != 0
    output_text = result.output or (result.stdout + result.stderr if hasattr(result, "stderr") else "")
    assert "not exist" in output_text.lower() or "error" in output_text.lower() or result.exit_code == 2


def test_cli_missing_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que la CLI alerte si falta el token de GitHub."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    input_file = tmp_path / "input.csv"
    pd.DataFrame({"repo": ["org/repo"]}).to_csv(input_file, index=False)

    result = runner.invoke(app, [str(input_file)])
    assert result.exit_code == 1
    assert "Configuración Requerida" in result.stdout or "token de GitHub" in result.stdout


def test_cli_execution_mocked(tmp_path: Path, mocker: pytest.MockFixture) -> None:
    """Verifica una ejecución exitosa de la CLI simulando la API de GitHub."""
    input_file = tmp_path / "test_input.csv"
    output_file = tmp_path / "test_output.csv"

    pd.DataFrame({"repository": ["octocat/agent-repo", "octocat/regular-repo"]}).to_csv(
        input_file, index=False
    )

    mock_results = {
        "octocat/agent-repo": True,
        "octocat/regular-repo": False,
    }

    # Mockear check_repositories_ghaw
    mocker.patch("src.cli.check_repositories_ghaw", return_value=mock_results)

    result = runner.invoke(
        app,
        [
            str(input_file),
            "--output",
            str(output_file),
            "--token",
            "ghp_test123456789",
            "--filter-positive",
        ],
    )

    assert result.exit_code == 0
    assert "Resumen de Ejecución PeakyMiner" in result.stdout
    assert "GH-AW Detectados" in result.stdout
    assert output_file.exists()

    df_res = pd.read_csv(output_file)
    assert len(df_res) == 1
    assert df_res["repository"].values[0] == "octocat/agent-repo"
    assert bool(df_res["has_ghaw"].values[0]) is True
