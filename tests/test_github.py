"""
Pruebas para el cliente GraphQL asíncrono de GitHub (src/github_client.py).
"""

import httpx
import pytest
import respx

from src.github_client import (
    GITHUB_GRAPHQL_URL,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubAPIError,
    build_batch_query,
    check_repositories_ghaw,
    fetch_batch_ghaw_status,
)
from src.models import RepoTarget


def test_build_batch_query() -> None:
    """Verifica la generación de la consulta GraphQL por lotes con alias."""
    batch = [
        RepoTarget(owner="octocat", name="Hello-World"),
        RepoTarget(owner="github", name="agentic-workflows"),
    ]
    query = build_batch_query(batch)

    assert "query GetWorkflowsTree {" in query
    assert 'repo_0: repository(owner: "octocat", name: "Hello-World")' in query
    assert 'repo_1: repository(owner: "github", name: "agentic-workflows")' in query
    assert 'object(expression: "HEAD:.github/workflows")' in query
    assert "... on Tree {" in query
    assert "entries {" in query


@pytest.mark.asyncio
async def test_fetch_batch_ghaw_status_success() -> None:
    """Verifica la detección correcta en un lote mixto (positivo, negativo, sin workflows)."""
    batch = [
        RepoTarget(owner="org1", name="positive-repo"),
        RepoTarget(owner="org2", name="negative-repo"),
        RepoTarget(owner="org3", name="no-workflows-repo"),
    ]

    mock_response = {
        "data": {
            "repo_0": {
                "object": {
                    "entries": [
                        {"name": "agent.md", "type": "blob"},
                        {"name": "agent.lock.yml", "type": "blob"},
                        {"name": "build.yml", "type": "blob"},
                    ]
                }
            },
            "repo_1": {
                "object": {
                    "entries": [
                        {"name": "ci.yml", "type": "blob"},
                        {"name": "release.yml", "type": "blob"},
                    ]
                }
            },
            "repo_2": {
                "object": None
            },
        }
    }

    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=True) as respx_mock:
            respx_mock.post(GITHUB_GRAPHQL_URL).respond(
                status_code=200,
                json=mock_response,
            )

            results = await fetch_batch_ghaw_status(client, batch, token="fake-token")

            assert results["org1/positive-repo"] is True
            assert results["org2/negative-repo"] is False
            assert results["org3/no-workflows-repo"] is False


@pytest.mark.asyncio
async def test_fetch_batch_ghaw_status_partial_graphql_errors() -> None:
    """Verifica que errores parciales de GraphQL (ej. repositorio inexistente) no rompan el lote."""
    batch = [
        RepoTarget(owner="org1", name="valid-repo"),
        RepoTarget(owner="org2", name="missing-repo"),
    ]

    mock_response = {
        "data": {
            "repo_0": {
                "object": {
                    "entries": [
                        {"name": "task.md", "type": "blob"},
                        {"name": "task.lock.yml", "type": "blob"},
                    ]
                }
            },
            "repo_1": None,
        },
        "errors": [
            {
                "type": "NOT_FOUND",
                "path": ["repo_1"],
                "message": "Could not resolve to a Repository with the name 'org2/missing-repo'.",
            }
        ],
    }

    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=True) as respx_mock:
            respx_mock.post(GITHUB_GRAPHQL_URL).respond(
                status_code=200,
                json=mock_response,
            )

            results = await fetch_batch_ghaw_status(client, batch, token="fake-token")

            assert results["org1/valid-repo"] is True
            assert results["org2/missing-repo"] is False


@pytest.mark.asyncio
async def test_fetch_batch_ghaw_status_unauthorized_401() -> None:
    """Verifica que el error HTTP 401 lance GitHubAuthError."""
    batch = [RepoTarget(owner="org", name="repo")]

    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=True) as respx_mock:
            respx_mock.post(GITHUB_GRAPHQL_URL).respond(
                status_code=401,
                text="Bad credentials",
            )

            with pytest.raises(GitHubAuthError, match="token de GitHub es inválido"):
                await fetch_batch_ghaw_status(client, batch, token="invalid-token")


@pytest.mark.asyncio
async def test_fetch_batch_ghaw_status_rate_limit_403() -> None:
    """Verifica que una respuesta de rate limit lance GitHubRateLimitError."""
    batch = [RepoTarget(owner="org", name="repo")]

    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=True) as respx_mock:
            respx_mock.post(GITHUB_GRAPHQL_URL).respond(
                status_code=403,
                text="You have exceeded a secondary rate limit.",
            )

            with pytest.raises(GitHubRateLimitError, match="Límite de tasa"):
                await fetch_batch_ghaw_status(client, batch, token="fake-token")


@pytest.mark.asyncio
async def test_fetch_batch_empty_list() -> None:
    """Verifica que un lote vacío retorne diccionario vacío sin hacer peticiones."""
    async with httpx.AsyncClient() as client:
        results = await fetch_batch_ghaw_status(client, [], token="fake-token")
        assert results == {}


@pytest.mark.asyncio
async def test_check_repositories_ghaw_orchestration() -> None:
    """Verifica la orquestación en lotes, deduplicación y callback de progreso."""
    repos = [
        RepoTarget(owner="org1", name="repo1"),
        RepoTarget(owner="org2", name="repo2"),
        RepoTarget(owner="org1", name="repo1"),  # Duplicado
    ]

    mock_response = {
        "data": {
            "repo_0": {
                "object": {
                    "entries": [
                        {"name": "a.md", "type": "blob"},
                        {"name": "a.lock.yml", "type": "blob"},
                    ]
                }
            },
            "repo_1": {"object": None},
        }
    }

    progress_calls: list[tuple[int, int]] = []

    def on_progress(completed: int, total: int) -> None:
        progress_calls.append((completed, total))

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(GITHUB_GRAPHQL_URL).respond(
            status_code=200,
            json=mock_response,
        )

        results = await check_repositories_ghaw(
            repos=repos,
            token="fake-token",
            batch_size=2,
            max_concurrency=2,
            on_batch_complete=on_progress,
        )

        assert results["org1/repo1"] is True
        assert results["org2/repo2"] is False
        assert len(results) == 2
        assert len(progress_calls) > 0

