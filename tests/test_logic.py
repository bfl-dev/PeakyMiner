"""
Pruebas unitarias para la lógica de emparejamiento de patrones GH-AW (src/logic.py).
"""

import pytest

from src.logic import has_ghaw_pattern


@pytest.mark.parametrize(
    ("filenames", "expected"),
    [
        # Casos requeridos por la especificación
        (["report.md", "report.lock.yml"], True),
        (["report.md"], False),
        (["report.lock.yml"], False),
        (["report.md", "other.lock.yml"], False),
        (["a.md", "b.lock.yml", "test.md", "test.lock.yml"], True),
        ([], False),
        # Casos adicionales de robustez
        (["ci.yml", "release.yaml", "README.md"], False),
        (["daily-report.md", "daily-report.lock.yml", "other.md"], True),
        (["workflow.md", "workflow.yml", "workflow.lock.yml"], True),
        ([".md", ".lock.yml"], False),  # Nombres base vacíos
        (["agent.MD", "agent.lock.yml"], False),  # Sensibilidad a mayúsculas
        (["foo.bar.md", "foo.bar.lock.yml"], True),  # Múltiples puntos en el nombre
    ],
)
def test_has_ghaw_pattern(filenames: list[str], expected: bool) -> None:
    """Verifica que la función pura has_ghaw_pattern detecte correctamente los patrones GH-AW."""
    assert has_ghaw_pattern(filenames) is expected

