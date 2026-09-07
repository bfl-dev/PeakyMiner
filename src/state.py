"""
Módulo de gestión de estado y persistencia de checkpoints para PeakyMiner.
"""

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class StateManager:
    """
    Gestiona el almacenamiento y recuperación de checkpoints en disco para
    permitir la reanudación del análisis en caso de error o interrupción.
    """

    def __init__(
        self,
        input_file: Path,
        custom_checkpoint_path: Path | None = None,
    ) -> None:
        self.input_file = input_file
        if custom_checkpoint_path is not None:
            self.checkpoint_path = custom_checkpoint_path
        else:
            file_hash = self._calculate_file_identifier(input_file)
            self.checkpoint_path = input_file.parent / f".pkminer_checkpoint_{file_hash}.json"

    @staticmethod
    def _calculate_file_identifier(file_path: Path) -> str:
        """Calcula un identificador corto y estable a partir de la ruta del archivo."""
        resolved = str(file_path.resolve())
        return hashlib.md5(resolved.encode("utf-8")).hexdigest()[:10]

    def has_checkpoint(self) -> bool:
        """Verifica si existe un archivo de checkpoint legible y no vacío."""
        return self.checkpoint_path.is_file() and self.checkpoint_path.stat().st_size > 0

    def load_checkpoint(self) -> dict[str, bool]:
        """
        Carga los resultados parciales almacenados en el checkpoint.

        Returns:
            dict[str, bool]: Mapeo de repositorios ('owner/name') -> True/False.
        """
        if not self.has_checkpoint():
            return {}

        try:
            with open(self.checkpoint_path, encoding="utf-8") as f:
                data = json.load(f)
            results = data.get("results", {})
            if isinstance(results, dict):
                return {str(k): bool(v) for k, v in results.items()}
            return {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"No se pudo cargar el checkpoint '{self.checkpoint_path}': {e}")
            return {}

    def save_checkpoint(
        self,
        results: dict[str, bool],
        total_repos: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Guarda de forma atómica los resultados actuales en el archivo de checkpoint.

        Args:
            results: Diccionario acumulado de resultados.
            total_repos: Cantidad total de repositorios a analizar.
            metadata: Información contextual adicional opcional.
        """
        payload = {
            "input_file": str(self.input_file.resolve()),
            "total_repos": total_repos,
            "completed_count": len(results),
            "results": results,
            "metadata": metadata or {},
        }

        # Guardado atómico utilizando un archivo temporal en el mismo directorio
        parent_dir = self.checkpoint_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tempfile.NamedTemporaryFile(
                "w",
                dir=parent_dir,
                delete=False,
                encoding="utf-8",
                suffix=".tmp",
            ) as tmp_file:
                json.dump(payload, tmp_file, indent=2)
                tmp_path = Path(tmp_file.name)

            # Reemplazar atómicamente el archivo de checkpoint
            os.replace(tmp_path, self.checkpoint_path)
        except OSError as e:
            logger.error(f"Error al escribir el checkpoint atómico: {e}")

    def delete_checkpoint(self) -> None:
        """Elimina el archivo de checkpoint cuando el escaneo finaliza al 100%."""
        if self.checkpoint_path.exists():
            try:
                self.checkpoint_path.unlink()
            except OSError as e:
                logger.warning(f"No se pudo eliminar el checkpoint '{self.checkpoint_path}': {e}")

