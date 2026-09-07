"""
Módulo de exportación y persistencia relacional en formato Apache Parquet con PyArrow.
Genera las 3 tablas relacionales:
- repositories.parquet
- workflows.parquet
- workflow_triggers.parquet
Asegurando tipado estricto, compresión Snappy y validación contra esquemas explícitos.
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.models import ExtractedData
from src.schemas import (
    REPOSITORIES_SCHEMA,
    WORKFLOW_TRIGGERS_SCHEMA,
    WORKFLOWS_SCHEMA,
)

logger = logging.getLogger(__name__)


def write_dataset_to_parquet(
    data: ExtractedData,
    output_dir: Path,
) -> dict[str, Any]:
    """
    Convierte los datos extraídos a tablas PyArrow tipadas y los exporta a archivos Parquet
    con compresión Snappy en el directorio especificado.

    Args:
        data: Instancia de ExtractedData con repositories, workflows y triggers.
        output_dir: Directorio de destino donde se guardarán los archivos .parquet.

    Returns:
        dict[str, Any]: Resumen de métricas de exportación y rutas de los archivos generados.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    repo_path = output_dir / "repositories.parquet"
    workflow_path = output_dir / "workflows.parquet"
    trigger_path = output_dir / "workflow_triggers.parquet"

    # 1. Tabla repositories.parquet
    repo_records = [r.model_dump() for r in data.repositories]
    if repo_records:
        df_repos = pd.DataFrame(repo_records)
        df_repos["scanned_at"] = pd.to_datetime(df_repos["scanned_at"])
        table_repos = pa.Table.from_pandas(df_repos, schema=REPOSITORIES_SCHEMA, preserve_index=False)
    else:
        table_repos = pa.Table.from_batches([], schema=REPOSITORIES_SCHEMA)

    pq.write_table(table_repos, repo_path, compression="snappy")
    logger.info(f"Guardada tabla repositories.parquet ({len(table_repos)} registros) en {repo_path}")

    # 2. Tabla workflows.parquet
    workflow_records = [w.model_dump() for w in data.workflows]
    if workflow_records:
        df_workflows = pd.DataFrame(workflow_records)
        table_workflows = pa.Table.from_pandas(df_workflows, schema=WORKFLOWS_SCHEMA, preserve_index=False)
    else:
        table_workflows = pa.Table.from_batches([], schema=WORKFLOWS_SCHEMA)

    pq.write_table(table_workflows, workflow_path, compression="snappy")
    logger.info(f"Guardada tabla workflows.parquet ({len(table_workflows)} registros) en {workflow_path}")

    # 3. Tabla workflow_triggers.parquet
    trigger_records = [t.model_dump() for t in data.triggers]
    if trigger_records:
        df_triggers = pd.DataFrame(trigger_records)
        table_triggers = pa.Table.from_pandas(df_triggers, schema=WORKFLOW_TRIGGERS_SCHEMA, preserve_index=False)
    else:
        table_triggers = pa.Table.from_batches([], schema=WORKFLOW_TRIGGERS_SCHEMA)

    pq.write_table(table_triggers, trigger_path, compression="snappy")
    logger.info(f"Guardada tabla workflow_triggers.parquet ({len(table_triggers)} registros) en {trigger_path}")

    return {
        "output_dir": output_dir,
        "repositories_path": repo_path,
        "workflows_path": workflow_path,
        "triggers_path": trigger_path,
        "repositories_count": len(table_repos),
        "workflows_count": len(table_workflows),
        "triggers_count": len(table_triggers),
    }

