"""
Módulo de lógica pura para la detección de patrones de GitHub Agentic Workflows (GH-AW).
"""

from collections.abc import Iterable


def has_ghaw_pattern(filenames: Iterable[str]) -> bool:
    """
    Determina si un conjunto de nombres de archivos en `.github/workflows/`
    cumple con el patrón característico de GitHub Agentic Workflows (GH-AW).

    Un repositorio utiliza GH-AW si contiene al menos un archivo Markdown (`.md`)
    y su correspondiente archivo compilado (`.lock.yml`) con el mismo nombre base exacto.

    Ejemplo:
        - `daily-report.md` y `daily-report.lock.yml` -> True
        - `daily-report.md` y `other.lock.yml` -> False
        - `daily-report.md` solo -> False
        - `daily-report.lock.yml` solo -> False

    Args:
        filenames: Iterable de nombres de archivo dentro del directorio `.github/workflows/`.

    Returns:
        bool: True si existe al menos una coincidencia exacta de nombre base, False en caso contrario.
    """
    md_bases = {
        name[:-3]
        for name in filenames
        if name.endswith(".md") and len(name) > 3
    }
    lock_bases = {
        name[:-9]
        for name in filenames
        if name.endswith(".lock.yml") and len(name) > 9
    }

    return bool(md_bases & lock_bases)

