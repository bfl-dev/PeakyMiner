"""
Módulo orquestador de extracción (Fase 1 y Fase 2) y parseo resiliente de GitHub Agentic Workflows.
Procesa metadatos de repositorios, archivos Markdown con YAML frontmatter y disparadores.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import frontmatter
import yaml
from rich.console import Console

from src.github_client import (
    fetch_batch_deep_data,
    fetch_batch_workflow_pairs,
)
from src.models import (
    ExtractedData,
    RepositoryRecord,
    RepoTarget,
    WorkflowFilePair,
    WorkflowRecord,
    WorkflowTriggerRecord,
    generate_repo_id,
    generate_trigger_id,
    generate_workflow_id,
)

logger = logging.getLogger(__name__)
console = Console()


def extract_raw_frontmatter(raw_text: str) -> str:
    """
    Extrae el bloque textual del frontmatter contenido entre delimitadores '---'.
    Preserva el formato y comentarios originales.

    Args:
        raw_text: Texto completo del archivo.

    Returns:
        str: Texto del frontmatter sin delimitadores, o cadena vacía si no existe.
    """
    if not raw_text or not raw_text.startswith("---"):
        return ""
    parts = raw_text.split("---", 2)
    if len(parts) >= 3:
        return parts[1].strip()
    elif len(parts) == 2:
        return parts[1].strip()
    return ""


def parse_workflow_content(raw_text: str) -> tuple[dict[str, Any], str, bool]:
    """
    Analiza de forma resiliente el contenido de un workflow en Markdown.
    Extrae metadatos estructurados del frontmatter YAML y el cuerpo en Markdown.

    Si el frontmatter tiene errores de sintaxis YAML, atrapa la excepción,
    emite una advertencia con Rich, asigna has_syntax_error = True,
    preserva el cuerpo del texto y retorna metadata vacía.

    Args:
        raw_text: Contenido del archivo .md.

    Returns:
        tuple[dict, str, bool]: (metadata, body_markdown, has_syntax_error).
    """
    if not raw_text or not raw_text.strip():
        return {}, "", False

    try:
        raw_meta, body = frontmatter.parse(raw_text)
        metadata: dict[str, Any] = {}
        if isinstance(raw_meta, dict):
            for k, v in raw_meta.items():
                if k is True:
                    metadata["on"] = v
                elif k is False:
                    metadata["off"] = v
                else:
                    metadata[str(k)] = v
        return metadata, body or "", False
    except (yaml.YAMLError, Exception) as exc:
        console.print(f"[yellow]⚠️ Warning: Sintaxis YAML inválida en frontmatter: {exc}[/yellow]")
        body = ""
        if raw_text.startswith("---"):
            parts = raw_text.split("---", 2)
            if len(parts) >= 3:
                body = parts[2].lstrip("\r\n")
            else:
                body = ""
        else:
            body = raw_text
        return {}, body, True


def extract_workflow_record(
    repo_id: str,
    file_path: str,
    basename: str,
    lock_path: str,
    blob_sha: str,
    raw_text: str,
) -> tuple[WorkflowRecord, list[WorkflowTriggerRecord]]:
    """
    Construye un registro de WorkflowRecord y su lista de WorkflowTriggerRecord a partir del contenido del blob.

    Args:
        repo_id: UUIDv5 del repositorio padre.
        file_path: Ruta relativa del archivo .md (ej. '.github/workflows/agent.md').
        basename: Nombre base sin extensión (ej. 'agent').
        lock_path: Ruta relativa del archivo .lock.yml.
        blob_sha: SHA del blob de Git.
        raw_text: Contenido en texto plano del archivo .md.

    Returns:
        tuple: (WorkflowRecord, list[WorkflowTriggerRecord]).
    """
    metadata, body, has_syntax_error = parse_workflow_content(raw_text)
    raw_frontmatter = extract_raw_frontmatter(raw_text)
    workflow_id = generate_workflow_id(repo_id, file_path)

    # 1. Metadatos generales
    name = str(metadata["name"]) if metadata.get("name") is not None else None
    description = str(metadata["description"]) if metadata.get("description") is not None else None

    # Modelo / runtime de agente
    model_engine: str | None = None
    if metadata.get("model") is not None:
        model_engine = str(metadata["model"])
    elif metadata.get("engine") is not None:
        model_engine = str(metadata["engine"])
    elif metadata.get("model_engine") is not None:
        model_engine = str(metadata["model_engine"])
    elif isinstance(metadata.get("agent"), dict) and metadata["agent"].get("model") is not None:
        model_engine = str(metadata["agent"]["model"])

    # Herramientas
    tools_val = metadata.get("tools")
    tools: list[str] | None = None
    if isinstance(tools_val, list):
        tools = [str(t) if not isinstance(t, str) else t for t in tools_val]
    elif isinstance(tools_val, dict):
        tools = [str(k) for k in tools_val.keys()]
    elif isinstance(tools_val, str):
        tools = [tools_val]

    # Permisos (matriz en JSON string)
    perms_val = metadata.get("permissions")
    permissions: str | None = None
    if perms_val is not None:
        permissions = json.dumps(perms_val)

    # Métricas de texto
    body_word_count = len(body.split()) if body else 0
    body_char_count = len(body) if body else 0

    workflow_rec = WorkflowRecord(
        workflow_id=workflow_id,
        repo_id=repo_id,
        file_path=file_path,
        basename=basename,
        lock_path=lock_path,
        blob_sha=blob_sha,
        name=name,
        description=description,
        model_engine=model_engine,
        tools=tools,
        permissions=permissions,
        raw_frontmatter=raw_frontmatter,
        body_markdown=body,
        body_word_count=body_word_count,
        body_char_count=body_char_count,
        has_syntax_error=has_syntax_error,
    )

    # 2. Desnormalización de disparadores (triggers)
    triggers: list[WorkflowTriggerRecord] = []
    on_val = metadata.get("on") if "on" in metadata else metadata.get("triggers")

    if on_val is not None:
        if isinstance(on_val, str):
            event_type = on_val.strip()
            trigger_id = generate_trigger_id(workflow_id, event_type, 0)
            triggers.append(
                WorkflowTriggerRecord(
                    trigger_id=trigger_id,
                    workflow_id=workflow_id,
                    event_type=event_type,
                    trigger_config="{}",
                )
            )
        elif isinstance(on_val, list):
            for idx, item in enumerate(on_val):
                event_type = str(item).strip()
                trigger_id = generate_trigger_id(workflow_id, event_type, idx)
                triggers.append(
                    WorkflowTriggerRecord(
                        trigger_id=trigger_id,
                        workflow_id=workflow_id,
                        event_type=event_type,
                        trigger_config="{}",
                    )
                )
        elif isinstance(on_val, dict):
            for idx, (event_key, cfg) in enumerate(on_val.items()):
                event_type = str(event_key).strip()
                trigger_config = json.dumps(cfg) if cfg is not None else "{}"
                trigger_id = generate_trigger_id(workflow_id, event_type, idx)
                triggers.append(
                    WorkflowTriggerRecord(
                        trigger_id=trigger_id,
                        workflow_id=workflow_id,
                        event_type=event_type,
                        trigger_config=trigger_config,
                    )
                )

    return workflow_rec, triggers


async def extract_dataset(
    repos: list[RepoTarget],
    token: str,
    batch_size: int = 25,
    max_concurrency: int = 5,
    on_phase1_progress: Callable[[int, int], None] | None = None,
    on_phase2_progress: Callable[[int, int], None] | None = None,
) -> ExtractedData:
    """
    Orquesta la extracción completa en 2 Fases:
    - Fase 1: Identificación de pares confirmados (.md y .lock.yml).
    - Fase 2: Descarga de metadatos del repo y blobs de workflows.
    - Parseo y estructuración en el modelo ExtractedData.

    Args:
        repos: Lista de repositorios a procesar.
        token: Token de acceso de GitHub.
        batch_size: Cantidad de repositorios por lote GraphQL.
        max_concurrency: Concurrencia máxima simultánea.
        on_phase1_progress: Callback para progreso de Fase 1.
        on_phase2_progress: Callback para progreso de Fase 2.

    Returns:
        ExtractedData: Colección completa de RepositoryRecord, WorkflowRecord y WorkflowTriggerRecord.
    """
    import httpx

    # Deduplicar repositorios
    unique_repos: list[RepoTarget] = []
    seen: set[RepoTarget] = set()
    for r in repos:
        if r not in seen:
            seen.add(r)
            unique_repos.append(r)

    total_repos = len(unique_repos)
    if not unique_repos:
        return ExtractedData()

    semaphore = asyncio.Semaphore(max_concurrency)
    confirmed_pairs_map: dict[str, list[WorkflowFilePair]] = {}
    completed_phase1 = 0
    lock1 = asyncio.Lock()

    async with httpx.AsyncClient() as client:
        # --- FASE 1: Detección y localización de pares ---
        batches_phase1 = [
            unique_repos[i: i + batch_size]
            for i in range(0, len(unique_repos), batch_size)
        ]

        async def run_phase1_batch(batch_items: list[RepoTarget]) -> None:
            nonlocal completed_phase1
            async with semaphore:
                batch_res = await fetch_batch_workflow_pairs(client, batch_items, token)
                async with lock1:
                    confirmed_pairs_map.update(batch_res)
                    completed_phase1 += len(batch_items)
                    if on_phase1_progress:
                        on_phase1_progress(completed_phase1, total_repos)

        tasks_p1 = [run_phase1_batch(b) for b in batches_phase1]
        await asyncio.gather(*tasks_p1)

        # Filtrar únicamente repositorios con al menos un par confirmado
        repos_with_pairs: list[tuple[RepoTarget, list[WorkflowFilePair]]] = [
            (r, confirmed_pairs_map[r.full_name])
            for r in unique_repos
            if confirmed_pairs_map.get(r.full_name)
        ]

        total_candidates = len(repos_with_pairs)
        if on_phase2_progress:
            on_phase2_progress(0, total_candidates)

        if not repos_with_pairs:
            return ExtractedData()

        # --- FASE 2: Extracción profunda de contenidos y metadatos ---
        batch_size_p2 = min(batch_size, 10)
        batches_phase2 = [
            repos_with_pairs[i: i + batch_size_p2]
            for i in range(0, len(repos_with_pairs), batch_size_p2)
        ]

        completed_phase2 = 0
        lock2 = asyncio.Lock()
        deep_data_results: dict[str, dict[str, Any]] = {}

        async def run_phase2_batch(batch_items: list[tuple[RepoTarget, list[WorkflowFilePair]]]) -> None:
            nonlocal completed_phase2
            async with semaphore:
                batch_res = await fetch_batch_deep_data(client, batch_items, token)
                async with lock2:
                    deep_data_results.update(batch_res)
                    completed_phase2 += len(batch_items)
                    if on_phase2_progress:
                        on_phase2_progress(completed_phase2, total_candidates)

        tasks_p2 = [run_phase2_batch(b) for b in batches_phase2]
        await asyncio.gather(*tasks_p2)

    # --- Estructuración de datos en modelos ---
    scanned_at = datetime.now(UTC)
    all_repos: list[RepositoryRecord] = []
    all_workflows: list[WorkflowRecord] = []
    all_triggers: list[WorkflowTriggerRecord] = []

    for repo_target, _ in repos_with_pairs:
        repo_entry = deep_data_results.get(repo_target.full_name)
        if not repo_entry:
            continue

        meta = repo_entry.get("metadata", {})
        repo_id = generate_repo_id(repo_target.owner, repo_target.name)

        repo_rec = RepositoryRecord(
            repo_id=repo_id,
            owner=repo_target.owner,
            name=repo_target.name,
            canonical_url=repo_target.url,
            stars_count=meta.get("stars_count", 0),
            forks_count=meta.get("forks_count", 0),
            primary_language=meta.get("primary_language"),
            is_fork=meta.get("is_fork", False),
            license_spdx=meta.get("license_spdx"),
            default_branch=meta.get("default_branch", "main"),
            scanned_at=scanned_at,
        )
        all_repos.append(repo_rec)

        for wf_dict in repo_entry.get("workflows", []):
            pair: WorkflowFilePair = wf_dict["pair"]
            blob_sha = wf_dict.get("blob_sha", "")
            raw_text = wf_dict.get("raw_text", "")

            wf_rec, wf_trigs = extract_workflow_record(
                repo_id=repo_id,
                file_path=pair.md_path,
                basename=pair.basename,
                lock_path=pair.lock_path,
                blob_sha=blob_sha,
                raw_text=raw_text,
            )
            all_workflows.append(wf_rec)
            all_triggers.extend(wf_trigs)

    return ExtractedData(
        repositories=all_repos,
        workflows=all_workflows,
        triggers=all_triggers,
    )
