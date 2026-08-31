"""
Cliente asíncrono para la API GraphQL de GitHub con soporte para lotes (batching) y concurrencia controlada.
"""

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

import httpx

from src.logic import has_ghaw_pattern
from src.models import RepoTarget

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


class GitHubAPIError(Exception):
    """Excepción base para errores relacionados con la API de GitHub."""
    pass


class GitHubAuthError(GitHubAPIError):
    """Excepción lanzada cuando el token de GitHub es inválido o no tiene permisos."""
    pass


class GitHubRateLimitError(GitHubAPIError):
    """Excepción lanzada cuando se alcanza el límite de peticiones (rate limit)."""
    pass


def build_batch_query(batch: list[RepoTarget]) -> str:
    """
    Construye una query GraphQL dinámica con alias para consultar múltiples repositorios
    en una única llamada de red.

    Consulta el objeto 'HEAD:.github/workflows' como Tree y extrae sus entradas.

    Args:
        batch: Lista de repositorios RepoTarget para incluir en la consulta.

    Returns:
        str: Consulta GraphQL lista para ejecutar.
    """
    queries: list[str] = []
    for i, repo in enumerate(batch):
        owner_json = json.dumps(repo.owner)
        name_json = json.dumps(repo.name)
        queries.append(
            f"""
  repo_{i}: repository(owner: {owner_json}, name: {name_json}) {{
    object(expression: "HEAD:.github/workflows") {{
      ... on Tree {{
        entries {{
          name
          type
        }}
      }}
    }}
  }}"""
        )

    query_body = "\n".join(queries)
    return f"query GetWorkflowsTree {{\n{query_body}\n}}"


async def fetch_batch_ghaw_status(
    client: httpx.AsyncClient,
    batch: list[RepoTarget],
    token: str,
) -> dict[str, bool]:
    """
    Ejecuta una consulta GraphQL por lote para un conjunto de repositorios y evalúa
    si cada uno cumple con el patrón de GitHub Agentic Workflows (GH-AW).

    Args:
        client: Instancia de httpx.AsyncClient.
        batch: Lista de repositorios a consultar en este lote.
        token: Token de autenticación de GitHub.

    Returns:
        dict[str, bool]: Mapeo de nombre completo ('owner/name') -> True/False.

    Raises:
        GitHubAuthError: Si el token es inválido o rechazado (401).
        GitHubRateLimitError: Si se alcanza la cuota de la API (403/429).
        GitHubAPIError: Para otros errores HTTP inesperados.
    """
    if not batch:
        return {}

    query = build_batch_query(batch)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "PeakyMiner/0.1.0",
    }

    try:
        response = await client.post(
            GITHUB_GRAPHQL_URL,
            headers=headers,
            json={"query": query},
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        logger.error(f"Error de red al consultar GraphQL: {exc}")
        raise GitHubAPIError(f"Fallo de conexión con GitHub: {exc}") from exc

    if response.status_code == 401:
        raise GitHubAuthError("El token de GitHub es inválido o no está autorizado (HTTP 401).")

    if response.status_code in (403, 429):
        # Verificar si es por límite de tasa
        body_text = response.text.lower()
        if "rate limit" in body_text or "secondary rate" in body_text:
            raise GitHubRateLimitError(
                "Límite de tasa (rate limit) de GitHub alcanzado. Por favor, espere antes de reintentar."
            )
        raise GitHubAPIError(f"Acceso denegado por GitHub (HTTP {response.status_code}): {response.text}")

    if response.status_code != 200:
        raise GitHubAPIError(f"Respuesta inesperada de GitHub (HTTP {response.status_code}): {response.text}")

    data_json = response.json()
    data: dict[str, Any] = data_json.get("data") or {}

    # Registrar errores parciales si existen en la respuesta GraphQL
    if "errors" in data_json:
        for err in data_json["errors"]:
            logger.debug(f"GraphQL partial error: {err.get('message')}")

    results: dict[str, bool] = {}

    for i, repo in enumerate(batch):
        repo_data = data.get(f"repo_{i}")
        if not repo_data:
            results[repo.full_name] = False
            continue

        tree_object = repo_data.get("object")
        if not tree_object or not isinstance(tree_object, dict):
            results[repo.full_name] = False
            continue

        entries = tree_object.get("entries")
        if not entries or not isinstance(entries, list):
            results[repo.full_name] = False
            continue

        filenames = [
            e["name"] for e in entries
            if isinstance(e, dict) and "name" in e and isinstance(e["name"], str)
        ]
        results[repo.full_name] = has_ghaw_pattern(filenames)

    return results


async def check_repositories_ghaw(
    repos: list[RepoTarget],
    token: str,
    batch_size: int = 25,
    max_concurrency: int = 5,
    on_batch_complete: Callable[[int, int], None] | None = None,
) -> dict[str, bool]:
    """
    Orquesta el análisis de múltiples repositorios distribuyéndolos en lotes concurrentes
    regulados mediante un semáforo asíncrono para evitar límites secundarios de GitHub.

    Args:
        repos: Lista completa de repositorios a analizar.
        token: Token de GitHub.
        batch_size: Cantidad de repositorios por consulta GraphQL (recomendado 20-30).
        max_concurrency: Cantidad máxima de consultas concurrentes simultáneas.
        on_batch_complete: Callback opcional llamado al completar cada lote con (completados, total).

    Returns:
        dict[str, bool]: Diccionario acumulado con el resultado de todos los repositorios.
    """
    if not repos:
        return {}

    # Deduplicar preservando orden
    unique_repos: list[RepoTarget] = []
    seen: set[RepoTarget] = set()
    for r in repos:
        if r not in seen:
            seen.add(r)
            unique_repos.append(r)

    # Dividir en lotes
    batches = [
        unique_repos[i: i + batch_size]
        for i in range(0, len(unique_repos), batch_size)
    ]

    semaphore = asyncio.Semaphore(max_concurrency)
    completed_count = 0
    total_repos = len(unique_repos)
    results: dict[str, bool] = {}
    lock = asyncio.Lock()

    async with httpx.AsyncClient() as client:
        async def process_batch(batch_repos: list[RepoTarget]) -> None:
            nonlocal completed_count
            async with semaphore:
                batch_res = await fetch_batch_ghaw_status(client, batch_repos, token)
                async with lock:
                    results.update(batch_res)
                    completed_count += len(batch_repos)
                    if on_batch_complete:
                        on_batch_complete(completed_count, total_repos)

        tasks = [process_batch(b) for b in batches]
        await asyncio.gather(*tasks)

    return results

