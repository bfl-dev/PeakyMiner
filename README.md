# ⛏️ PeakyMiner (`pkminer`)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![CLI](https://img.shields.io/badge/CLI-Typer-purple.svg)](https://typer.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**PeakyMiner** es una herramienta de línea de comandos (CLI) de alto rendimiento diseñada para la **detección masiva y automatizada de repositorios de GitHub que implementan GitHub Agentic Workflows (GH-AW)**.

---

## 🎯 ¿Qué es GitHub Agentic Workflows (GH-AW)?

Los **GitHub Agentic Workflows (GH-AW)** son una arquitectura moderna de automatización donde los flujos de trabajo se diseñan a partir de especificaciones semánticas en Markdown (`.md`) y posteriormente se compilan en artefactos ejecutables (`.lock.yml`).

### Criterio de Detección:
Un repositorio es clasificado como usuario de **GH-AW** si dentro del directorio `.github/workflows/` contiene al menos un archivo Markdown (`.md`) y su respectivo archivo compilado (`.lock.yml`) con el **mismo nombre base exacto**.

| Archivos en `.github/workflows/` | ¿Es GH-AW? | Razón |
| :--- | :---: | :--- |
| `daily-report.md`, `daily-report.lock.yml` | ✅ **SÍ** | Coincidencia exacta de nombre base |
| `report.md`, `ci.yml` | ❌ **NO** | Falta el lockfile correspondiente |
| `deploy.lock.yml` | ❌ **NO** | Falta la especificación Markdown |
| `a.md`, `b.lock.yml`, `agent.md`, `agent.lock.yml` | ✅ **SÍ** | Al menos un par (`agent`) coincide |

---

## 🚀 Características Principales

- **Alto Rendimiento con GraphQL Batching**: Agrupa de 20 a 30 repositorios por consulta GraphQL utilizando *aliases*, reduciendo drásticamente la latencia y optimizando el consumo de cuota de la API de GitHub.
- **Concurrencia Controlada Asíncrona**: Utiliza `httpx.AsyncClient`, `asyncio` y semáforos para realizar múltiples consultas en paralelo respetando los límites secundarios (*secondary rate limits*) de GitHub.
- **Extracción Profunda en 2 Fases**: Localiza pares de archivos confirmados (Fase 1) y extrae metadatos de repositorios y blobs Markdown (Fase 2).
- **Manejo Resiliente de YAML/Markdown**: Parsea especificaciones de agentes con captura controlada de errores de sintaxis YAML, preservando prompts y contenido textual sin detener el pipeline.
- **Modelo Relacional en 3 Tablas Apache Parquet**: Persiste `repositories`, `workflows` y `workflow_triggers` con tipado estricto PyArrow, claves deterministas UUIDv5 y compresión Snappy.
- **Publicación en Hugging Face Datasets**: Autogeneración de Dataset Card (`README.md`) y subida automatizada con `huggingface_hub`.

```text
.
├── .devcontainer/
│   └── devcontainer.json      # Configuración de entorno de desarrollo aislado
├── .env.example               # Plantilla para variables de entorno (GitHub y Hugging Face)
├── .gitignore                 # Exclusiones de control de versiones
├── docs/                      # Documentación técnica y formal
│   ├── er_diagram.md          # Diagrama Entidad-Relación nativo en Mermaid
│   ├── data_dictionary.md     # Diccionario de datos para las 3 tablas Parquet
├── pyproject.toml             # Configuración de empaquetado y dependencias
├── README.md                  # Documentación principal del proyecto
│   ├── extractor.py           # Orquestación de Fase 1/2 y parseo resiliente YAML/Markdown
│   ├── github_client.py       # Cliente GraphQL asíncrono con HTTPX y batches
│   ├── hf_publisher.py        # Generación de Dataset Card y subida a Hugging Face
│   ├── logic.py               # Lógica pura de detección de patrones GH-AW
│   ├── parquet_writer.py      # Conversión a PyArrow y exportación Parquet Snappy
│   ├── schemas.py             # Esquemas explícitos PyArrow de las 3 tablas
└── tests/
    ├── test_cli.py            # Pruebas de integración CLI con CliRunner
    ├── test_extractor.py      # Pruebas de parseo de frontmatter válido, corrupto y Markdown
    └── test_state.py          # Pruebas de checkpoints y recuperación ante fallos
```


## ⚙️ Instalación y Configuración
2. Haz clic en **"Reopen in Container"** cuando aparezca la notificación (o usa la paleta de comandos `Ctrl+Shift+P` / `Cmd+Shift+P` -> `Dev Containers: Rebuild and Reopen in Container`).
3. Las extensiones y dependencias con `uv` se instalarán automáticamente.

### Opción 2: Instalación Local con `uv`

Recomendamos [`uv`](https://github.com/astral-sh/uv) por su velocidad:

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/PeakyMiner.git
cd PeakyMiner

# 2. Crear y activar el entorno virtual
uv venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias en modo editable (incluyendo dev)
uv pip install -e ".[dev]"
```

### Opción 3: Instalación Tradicional con `pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 🔑 Configuración del Token de GitHub

Para consultar la API GraphQL de GitHub, se requiere un Personal Access Token (Classic o Fine-grained con permisos de lectura pública `public_repo` o `repo`).

1. Copia el archivo de ejemplo:
   ```bash
   cp .env.example .env
   ```
2. Edita `.env` y agrega tu token:
   ```env
   GITHUB_TOKEN=ghp_tuTokenDeAccesoPersonalAqui
   ```
*(También puedes pasar el token directamente en la CLI mediante la opción `--token`)*.

---

## 📖 Uso de la CLI (`pkminer` / `miner`)

PeakyMiner soporta subcomandos explícitos (`detect`, `extract`, `upload`) y preserva la invocación directa retrocompatible:

```bash
# Subcomandos explícitos
pkminer detect <input.csv> [OPCIONES]
pkminer extract <input.csv> [OPCIONES]
pkminer upload [OPCIONES]

# Invocación directa retrocompatible (enruta automáticamente a detect)
pkminer repos.csv -o resultado.csv

### Ejemplos Prácticos


# Reanudación desde checkpoint ante interrupción o rate limit
pkminer detect repos.csv -o resultado.csv --resume
```

#### 2. Extracción Profunda y Generación Parquet (`pkminer extract`)
# Extrae contenido .md, metadatos y genera las 3 tablas Parquet + README.md
pkminer extract ghaw_detectados.csv --output-dir ./dataset
pkminer upload --dataset-dir ./dataset --hf-repo usuario/gh-agentic-workflows

# Pasando el token directamente
pkminer upload -d ./dataset -r usuario/gh-agentic-workflows --token hf_123456789

> Para más detalles, consulta la [Guía Completa de Uso de la CLI](docs/cli_usage.md), el [Diagrama Entidad-Relación](docs/er_diagram.md) y el [Diccionario de Datos](docs/data_dictionary.md).
### Archivo de Entrada (`input.csv`)
El CSV de entrada puede tener cualquiera de las siguientes columnas (`repo`, `repository`, `url`, `github_url`, `name`, `target`) o ser un CSV de una sola columna:

```csv
facebook/react,frontend
octocat/Hello-World,demo
https://github.com/astral-sh/uv,tools
### Archivo de Salida Generado (`output.csv`)
Conserva las columnas originales y agrega el estado canónico de detección:

```csv
repo,category,ghaw_canonical_repo,has_ghaw,ghaw_status
https://github.com/astral-sh/uv,tools,astral-sh/uv,False,NOT_DETECTED
```

---

## 🧪 Ejecución de Pruebas


```bash
# Ejecutar todas las pruebas con pytest
pytest

# Ejecutar con reporte detallado
pytest -v

# Verificar estilo y calidad de código con Ruff
ruff check .
```

---

## 🛡️ Licencia

Distribuido bajo la Licencia MIT. Consulta `LICENSE` para más información.

