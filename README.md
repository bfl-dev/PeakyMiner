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
- **Modelado Robusto con Pydantic**: Valida y normaliza automáticamente múltiples formatos de repositorios (`owner/repo`, URLs completas `https://github.com/...`, URLs con `.git`, SSH, etc.).
- **Procesamiento de Datos con Pandas**: Identifica automáticamente columnas relevantes en archivos CSV y exporta resultados detallados con metadatos y opciones de filtrado.
- **Interfaz CLI Moderna y Amigable**: Construida con `Typer` y `Rich`, con barras de progreso en tiempo real, tablas de resumen y feedback visual claro.
- **Entorno Dev Container Integrado**: Configurado para desarrollo instantáneo en VS Code con Python 3.12 y el gestor de paquetes ultra-rápido `uv`.

---

## 📁 Estructura del Repositorio

```text
.
├── .devcontainer/
│   └── devcontainer.json      # Configuración de entorno de desarrollo aislado
├── .env.example               # Plantilla para variables de entorno
├── .gitignore                 # Exclusiones de control de versiones
├── pyproject.toml             # Configuración de empaquetado, dependencias y herramientas
├── README.md                  # Documentación principal del proyecto
├── src/
│   ├── __init__.py            # Versión y metadatos del paquete
│   ├── cli.py                 # Punto de entrada Typer y orquestación asíncrona
│   ├── config.py              # Carga y validación de variables de entorno (Token)
│   ├── csv_processor.py       # Lectura, mapeo y exportación con pandas
│   ├── github_client.py       # Cliente GraphQL asíncrono con HTTPX y batches
│   ├── logic.py               # Lógica pura de detección de patrones GH-AW
│   └── models.py              # Modelos Pydantic y validación de URLs
└── tests/
    ├── __init__.py
    ├── test_cli.py            # Pruebas de integración CLI con CliRunner
    ├── test_github.py         # Pruebas mockeando la API GraphQL y lotes
    └── test_logic.py          # Pruebas unitarias de la lógica de emparejamiento
```

---

## ⚙️ Instalación y Configuración

### Opción 1: Con Dev Containers (Recomendado para VS Code)

1. Abre el repositorio en Visual Studio Code.
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

La herramienta se puede invocar mediante los comandos `pkminer` o `miner`:

```bash
pkminer [OPCIONES] INPUT_CSV
```

### Ejemplos Prácticos

#### 1. Análisis Básico
Analiza una lista de repositorios y guarda el resultado completo en `output.csv`:
```bash
pkminer repos.csv --output resultado.csv
```

#### 2. Filtrar Únicamente Repositorios con GH-AW
Exporta solo los repositorios donde se confirmó la presencia de GH-AW:
```bash
pkminer repos.csv -o ghaw_detectados.csv --filter-positive
```

#### 3. Ajustar Lotes y Concurrencia para Grandes Volúmenes
Para listas de miles de repositorios, ajusta el tamaño de lote y concurrencia:
```bash
pkminer lista_masiva.csv -o salida.csv --batch-size 30 --concurrency 10
```

#### 4. Pasar el Token Directamente
```bash
pkminer repos.csv -o salida.csv --token ghp_1234567890abcdef
```

---

## 📊 Formato del Archivo CSV

### Archivo de Entrada (`input.csv`)
El CSV de entrada puede tener cualquiera de las siguientes columnas (`repo`, `repository`, `url`, `github_url`, `name`, `target`) o ser un CSV de una sola columna:

```csv
repo,category
facebook/react,frontend
octocat/Hello-World,demo
https://github.com/astral-sh/uv,tools
```

### Archivo de Salida Generado (`output.csv`)
Conserva las columnas originales y agrega el estado canónico de detección:

```csv
repo,category,ghaw_canonical_repo,has_ghaw,ghaw_status
facebook/react,frontend,facebook/react,False,NOT_DETECTED
octocat/Hello-World,demo,octocat/Hello-World,False,NOT_DETECTED
https://github.com/astral-sh/uv,tools,astral-sh/uv,False,NOT_DETECTED
```

---

## 🧪 Ejecución de Pruebas

La suite de pruebas incluye tests unitarios de lógica pura, mocks de la API GraphQL de GitHub y pruebas de integración de la CLI:

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

