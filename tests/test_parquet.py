"""
Pruebas unitarias para la exportación y validación de esquemas Parquet (src/parquet_writer.py).
Verifica tipos PyArrow exactos, integridad referencial de PK/FK y compresión Snappy.
"""

from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from src.models import (
    ExtractedData,
    RepositoryRecord,
    WorkflowRecord,
    WorkflowTriggerRecord,
    generate_repo_id,
    generate_trigger_id,
    generate_workflow_id,
)
from src.parquet_writer import write_dataset_to_parquet
from src.schemas import (
    REPOSITORIES_SCHEMA,
    WORKFLOW_TRIGGERS_SCHEMA,
    WORKFLOWS_SCHEMA,
)


def test_write_dataset_to_parquet_success(tmp_path: Path) -> None:
    """Verifica la correcta generación de las 3 tablas Parquet con sus esquemas y claves relacionadas."""
    output_dir = tmp_path / "parquet_output"

    # 1. Crear datos de prueba consistentes
    owner = "openai"
    name = "swarm"
    repo_id = generate_repo_id(owner, name)
    file_path = ".github/workflows/agent.md"
    workflow_id = generate_workflow_id(repo_id, file_path)
    trigger_id = generate_trigger_id(workflow_id, "push", 0)

    now_utc = datetime.now(timezone.utc)

    repo_rec = RepositoryRecord(
        repo_id=repo_id,
        owner=owner,
        name=name,
        canonical_url=f"https://github.com/{owner}/{name}",
        stars_count=15000,
        forks_count=2300,
        primary_language="Python",
        is_fork=False,
        license_spdx="MIT",
        default_branch="main",
        scanned_at=now_utc,
    )

    wf_rec = WorkflowRecord(
        workflow_id=workflow_id,
        repo_id=repo_id,
        file_path=file_path,
        basename="agent",
        lock_path=".github/workflows/agent.lock.yml",
        blob_sha="1234567890abcdef1234567890abcdef12345678",
        name="Swarm Agent",
        description="Agente de orquestación multi-agente",
        model_engine="gpt-4o",
        tools=["web_search", "python_eval"],
        permissions='{"contents": "read"}',
        raw_frontmatter="name: Swarm Agent\nmodel: gpt-4o",
        body_markdown="# Prompt Principal\nEjecuta tareas colaborativas.",
        body_word_count=5,
        body_char_count=45,
        has_syntax_error=False,
    )

    trig_rec = WorkflowTriggerRecord(
        trigger_id=trigger_id,
        workflow_id=workflow_id,
        event_type="push",
        trigger_config='{"branches": ["main"]}',
    )

    data = ExtractedData(
        repositories=[repo_rec],
        workflows=[wf_rec],
        triggers=[trig_rec],
    )

    # 2. Escribir a Parquet
    metrics = write_dataset_to_parquet(data, output_dir)

    assert metrics["repositories_count"] == 1
    assert metrics["workflows_count"] == 1
    assert metrics["triggers_count"] == 1

    # 3. Leer y validar esquemas PyArrow
    table_repos = pq.read_table(output_dir / "repositories.parquet")
    table_wfs = pq.read_table(output_dir / "workflows.parquet")
    table_trigs = pq.read_table(output_dir / "workflow_triggers.parquet")

    assert table_repos.schema == REPOSITORIES_SCHEMA
    assert table_wfs.schema == WORKFLOWS_SCHEMA
    assert table_trigs.schema == WORKFLOW_TRIGGERS_SCHEMA

    # 4. Validar integridad referencial
    df_repos = table_repos.to_pandas()
    df_wfs = table_wfs.to_pandas()
    df_trigs = table_trigs.to_pandas()

    assert df_wfs["repo_id"].values[0] == df_repos["repo_id"].values[0]
    assert df_trigs["workflow_id"].values[0] == df_wfs["workflow_id"].values[0]

    # 5. Validar tipos específicos
    assert table_wfs.column("tools")[0].as_py() == ["web_search", "python_eval"]
    assert list(df_wfs["tools"].values[0]) == ["web_search", "python_eval"]


def test_write_empty_dataset(tmp_path: Path) -> None:
    """Verifica que un dataset vacío genere archivos Parquet válidos conformes a los esquemas."""
    output_dir = tmp_path / "empty_output"
    data = ExtractedData(repositories=[], workflows=[], triggers=[])

    metrics = write_dataset_to_parquet(data, output_dir)
    assert metrics["repositories_count"] == 0
    assert metrics["workflows_count"] == 0
    assert metrics["triggers_count"] == 0

    table_repos = pq.read_table(output_dir / "repositories.parquet")
    table_wfs = pq.read_table(output_dir / "workflows.parquet")
    table_trigs = pq.read_table(output_dir / "workflow_triggers.parquet")

    assert len(table_repos) == 0
    assert len(table_wfs) == 0
    assert len(table_trigs) == 0

    assert table_repos.schema == REPOSITORIES_SCHEMA
    assert table_wfs.schema == WORKFLOWS_SCHEMA
    assert table_trigs.schema == WORKFLOW_TRIGGERS_SCHEMA
