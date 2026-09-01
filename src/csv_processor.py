"""
Módulo de procesamiento de archivos CSV con pandas para entrada y salida de datos.
"""

import logging
from pathlib import Path

import pandas as pd

from src.models import RepoTarget

logger = logging.getLogger(__name__)

COMMON_REPO_COLUMNS = [
    "repo",
    "repository",
    "url",
    "repo_url",
    "github_url",
    "full_name",
    "name",
    "target",
]


def detect_repo_column(df: pd.DataFrame) -> str:
    """
    Identifica automáticamente la columna que contiene los nombres o URLs de repositorios.

    Args:
        df: DataFrame de pandas a inspeccionar.

    Returns:
        str: Nombre de la columna identificada.

    Raises:
        ValueError: Si no se puede determinar la columna adecuada.
    """
    # Comparación insensible a mayúsculas/minúsculas
    col_mapping = {col.lower().strip(): col for col in df.columns}

    for candidate in COMMON_REPO_COLUMNS:
        if candidate in col_mapping:
            return col_mapping[candidate]

    # Si el CSV solo tiene una columna, asumimos que es la columna objetivo
    if len(df.columns) == 1:
        return df.columns[0]

    raise ValueError(
        f"No se pudo identificar automáticamente la columna de repositorios.\n"
        f"Columnas disponibles: {list(df.columns)}.\n"
        f"Por favor asegúrese de que el CSV incluya una columna como 'repo', 'repository', o 'url'."
    )


def load_repositories_from_csv(
    file_path: Path,
) -> tuple[pd.DataFrame, str, list[tuple[int, RepoTarget]]]:
    """
    Carga un archivo CSV, identifica la columna de repositorios y valida las filas con RepoTarget.

    Args:
        file_path: Ruta al archivo CSV de entrada.

    Returns:
        tuple: (DataFrame original, nombre de columna de repositorios, lista de tuplas (índice, RepoTarget)).

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el archivo está vacío o no contiene filas válidas.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"El archivo de entrada no existe: {file_path}")

    df = pd.read_csv(file_path)
    if df.empty:
        raise ValueError(f"El archivo CSV '{file_path}' está vacío.")

    repo_col = detect_repo_column(df)
    valid_targets: list[tuple[int, RepoTarget]] = []

    for idx, value in df[repo_col].items():
        if pd.isna(value):
            continue
        try:
            target = RepoTarget.from_raw(str(value))
            valid_targets.append((int(idx), target))
        except ValueError as e:
            logger.warning(f"Fila {idx} con valor '{value}' omitida: {e}")

    if not valid_targets:
        raise ValueError(
            f"No se encontraron repositorios válidos en la columna '{repo_col}' del archivo '{file_path}'."
        )

    return df, repo_col, valid_targets


def save_results_to_csv(
    df: pd.DataFrame,
    repo_col: str,
    results: dict[str, bool],
    output_path: Path,
    filter_positive_only: bool = False,
) -> int:
    """
    Enriquece el DataFrame con los resultados de detección de GH-AW y lo exporta a CSV.

    Args:
        df: DataFrame original cargado.
        repo_col: Nombre de la columna de repositorios.
        results: Mapeo de 'owner/name' -> bool con los resultados del análisis.
        output_path: Ruta de destino del archivo CSV.
        filter_positive_only: Si es True, solo exporta los repositorios con GH-AW detectado.

    Returns:
        int: Cantidad de registros exportados.
    """
    # Mapear cada fila al resultado booleano y de estado
    has_ghaw_list: list[bool | None] = []
    status_list: list[str] = []
    canonical_names: list[str] = []

    for _, value in df[repo_col].items():
        if pd.isna(value):
            has_ghaw_list.append(False)
            status_list.append("INVALID")
            canonical_names.append("")
            continue

        try:
            target = RepoTarget.from_raw(str(value))
            canonical_names.append(target.full_name)
            if target.full_name in results:
                is_positive = bool(results[target.full_name])
                has_ghaw_list.append(is_positive)
                status_list.append("DETECTED" if is_positive else "NOT_DETECTED")
            else:
                has_ghaw_list.append(False)
                status_list.append("PENDING")
        except ValueError:
            canonical_names.append(str(value))
            has_ghaw_list.append(False)
            status_list.append("INVALID")

    df_out = df.copy()
    df_out["ghaw_canonical_repo"] = canonical_names
    df_out["has_ghaw"] = has_ghaw_list
    df_out["ghaw_status"] = status_list

    if filter_positive_only:
        df_out = df_out[[bool(x) for x in df_out["has_ghaw"]]]

    # Crear directorios padres si no existen
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(output_path, index=False)

    return len(df_out)

