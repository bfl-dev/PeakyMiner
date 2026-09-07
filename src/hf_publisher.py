"""
Módulo para la preparación de Dataset Cards y publicación en Hugging Face Datasets.
Utiliza `huggingface_hub` para autenticación, creación de repositorios y subida de archivos Parquet.
"""

import logging
import os
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

from src.config import ConfigurationError

logger = logging.getLogger(__name__)


def create_dataset_card(
    output_dir: Path,
    stats: dict[str, Any] | None = None,
) -> Path:
    """
    Genera el archivo README.md (Dataset Card) en el directorio del dataset con metadatos
    YAML compatibles con Hugging Face y documentación de las 3 tablas relacionales.

    Args:
        output_dir: Directorio donde se guardará el README.md.
        stats: Diccionario opcional con estadísticas de recuento de registros.

    Returns:
        Path: Ruta al archivo README.md generado.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    card_path = output_dir / "README.md"

    st = stats or {}
    repos_cnt = st.get("repositories_count", 0)
    wfs_cnt = st.get("workflows_count", 0)
    trigs_cnt = st.get("triggers_count", 0)

    content = f"""---
license: mit
task_categories:
- text-generation
tags:
- github-actions
- agentic-workflows
- ai-agents
configs:
- config_name: repositories
  data_files: "repositories.parquet"
- config_name: workflows
  data_files: "workflows.parquet"
- config_name: workflow_triggers
  data_files: "workflow_triggers.parquet"
---

# ⛏️ PeakyMiner GH-AW Dataset

Dataset estructurado y normalizado de **GitHub Agentic Workflows (GH-AW)** extraído de repositorios públicos de GitHub mediante [PeakyMiner](https://github.com/PeakyMiner).

## 📊 Resumen del Dataset

Este dataset contiene la especificación, instrucciones (prompts), metadatos y disparadores de flujos de trabajo de agentes autónomos basados en Markdown compilado a GitHub Actions (`.md` y `.lock.yml`).

### Estadísticas de Extracción
- **Repositorios únicos analizados:** `{repos_cnt}`
- **Workflows de agentes extraídos:** `{wfs_cnt}`
- **Disparadores (triggers) configurados:** `{trigs_cnt}`

---

## 🏛️ Estructura Relacional (Apache Parquet)

El dataset está dividido en 3 tablas relacionales con compresión Snappy e identificadores deterministas UUIDv5:

### 1. `repositories.parquet`
Contiene metadatos a nivel de repositorio de GitHub:
- `repo_id` (string, PK): UUIDv5 determinista derivado del nombre canónico.
- `owner` (string), `name` (string), `canonical_url` (string).
- `stars_count` (int64), `forks_count` (int64), `primary_language` (string, opcional).
- `is_fork` (bool), `license_spdx` (string, opcional), `default_branch` (string).
- `scanned_at` (timestamp[us]): Fecha y hora de la extracción.

### 2. `workflows.parquet`
Contiene la especificación completa del flujo de trabajo del agente:
- `workflow_id` (string, PK): UUIDv5 determinista derivado de `repo_id` + `file_path`.
- `repo_id` (string, FK -> `repositories.repo_id`).
- `file_path` (string), `basename` (string), `lock_path` (string), `blob_sha` (string).
- `name` (string, opcional), `description` (string, opcional).
- `model_engine` (string, opcional): Motor de inferencia del agente.
- `tools` (list<string>, opcional): Lista de herramientas y funciones habilitadas.
- `permissions` (string, opcional): Matriz de permisos de GitHub en formato JSON.
- `raw_frontmatter` (string, opcional): Bloque YAML original.
- `body_markdown` (string, opcional): Prompt, instrucciones de sistema y directivas en Markdown.
- `body_word_count` (int64), `body_char_count` (int64).
- `has_syntax_error` (bool): Bandera de resiliencia ante errores de sintaxis YAML.

### 3. `workflow_triggers.parquet`
Contiene los eventos desnormalizados que activan cada workflow:
- `trigger_id` (string, PK): UUIDv5 determinista derivado de `workflow_id` + `event_type` + índice.
- `workflow_id` (string, FK -> `workflows.workflow_id`).
- `event_type` (string): Tipo de evento de GitHub (ej. `push`, `pull_request`, `schedule`, `workflow_dispatch`).
- `trigger_config` (string, opcional): Configuración en JSON (ramas, tags, cron, inputs).

---

## 💻 Uso con la librería `datasets` de Hugging Face

```python
from datasets import load_dataset

# Cargar la tabla de workflows de agentes
workflows = load_dataset("{st.get('hf_repo', 'usuario/gh-agentic-workflows')}", data_files="workflows.parquet")
print(workflows["train"][0])

# Cargar la tabla de repositorios
repos = load_dataset("{st.get('hf_repo', 'usuario/gh-agentic-workflows')}", data_files="repositories.parquet")
```

---

## 🛡️ Licencia
Distribuido bajo la Licencia [MIT](https://opensource.org/licenses/MIT).
"""
    card_path.write_text(content.strip() + "\n", encoding="utf-8")
    logger.info(f"Dataset Card generada en {card_path}")
    return card_path


def upload_to_huggingface(
    dataset_dir: Path,
    repo_id: str,
    token: str | None = None,
) -> str:
    """
    Sube el dataset exportado en formato Parquet y su Dataset Card a Hugging Face Datasets.

    Args:
        dataset_dir: Directorio local que contiene los archivos Parquet.
        repo_id: Identificador del repositorio en Hugging Face (ej. 'usuario/mi-dataset').
        token: Token de acceso de Hugging Face (o variable de entorno HF_TOKEN).

    Returns:
        str: URL pública del dataset en Hugging Face.

    Raises:
        ConfigurationError: Si no se encuentra un token de autenticación configurado.
        FileNotFoundError: Si el directorio de entrada no existe o faltan archivos requeridos.
    """
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise FileNotFoundError(f"El directorio del dataset no existe: {dataset_dir}")

    # Validar archivos requeridos
    expected_files = ["repositories.parquet", "workflows.parquet", "workflow_triggers.parquet"]
    missing = [f for f in expected_files if not (dataset_dir / f).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Faltan archivos Parquet requeridos en '{dataset_dir}': {missing}.\n"
            f"Ejecute primero 'pkminer extract' para generar las 3 tablas."
        )

    # Validar o crear README.md
    readme_path = dataset_dir / "README.md"
    if not readme_path.exists():
        create_dataset_card(dataset_dir, {"hf_repo": repo_id})

    # Resolver token
    resolved_token = token or os.getenv("HF_TOKEN")
    if not resolved_token or not resolved_token.strip():
        raise ConfigurationError(
            "No se encontró un token de autenticación para Hugging Face.\n"
            "Solución: Configure la variable de entorno 'HF_TOKEN' en .env o pase la opción '--token tu_token'."
        )

    api = HfApi(token=resolved_token.strip())

    # Crear repositorio en Hugging Face Datasets si no existe
    try:
        api.create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            exist_ok=True,
        )
    except Exception as exc:
        logger.error(f"Error al verificar o crear el repositorio en Hugging Face: {exc}")
        raise

    # Subir la carpeta completa
    api.upload_folder(
        folder_path=str(dataset_dir.resolve()),
        repo_id=repo_id,
        repo_type="dataset",
    )

    url = f"https://huggingface.co/datasets/{repo_id}"
    logger.info(f"Dataset publicado exitosamente en: {url}")
    return url

