# 🛠️ Guía de Uso de la CLI - PeakyMiner (`pkminer`)

Esta guía detalla la instalación, configuración y ejecución de los subcomandos de **PeakyMiner** para la detección, extracción profunda y publicación de datasets de **GitHub Agentic Workflows (GH-AW)**.

---

## 1. Requisitos e Instalación

PeakyMiner requiere **Python 3.10 o superior** y recomienda el uso del gestor de paquetes de alto rendimiento [`uv`](https://github.com/astral-sh/uv).

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/PeakyMiner.git
cd PeakyMiner

# 2. Crear entorno virtual con uv e instalar dependencias
uv venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

Alternativamente con `pip`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 2. Configuración de Variables de Entorno (`.env`)

Crea un archivo `.env` en la raíz del proyecto para definir tus credenciales:

```bash
cp .env.example .env
```

Contenido del archivo `.env`:
```env
# Token de GitHub (requerido para detect y extract)
# Permisos: 'public_repo' o fine-grained con lectura de contenidos y metadatos
GITHUB_TOKEN=ghp_tuTokenDeGitHubAqui

# Token de Hugging Face (requerido para upload)
# Permisos: 'write' para subir datasets
HF_TOKEN=hf_tuTokenDeHuggingFaceAqui
```

> [!TIP]
> También puedes suministrar los tokens directamente en cada comando mediante la opción `--token <token>`.

---

## 3. Subcomandos Disponibles

PeakyMiner organiza su funcionalidad en 3 subcomandos principales:

| Comando | Descripción |
| :--- | :--- |
| `pkminer detect` | Analiza repositorios de entrada para determinar la presencia de GH-AW (Tarea 2). |
| `pkminer extract` | Extrae metadatos, archivos `.md` y genera las 3 tablas Parquet normalizadas (Tarea 3). |
| `pkminer upload` | Sube el dataset Parquet generado y su Dataset Card a Hugging Face Datasets. |

---

## 4. Referencia de Comandos

### A. Subcomando `detect`
Identifica qué repositorios contienen flujos de trabajo GH-AW (pares coincidentes `.md` y `.lock.yml`).

```bash
pkminer detect <input.csv> [OPCIONES]
```

**Opciones principales:**
- `-o, --output <path>`: Archivo CSV de salida con resultados (por defecto `output.csv`).
- `-b, --batch-size <int>`: Cantidad de repositorios por lote GraphQL (1 a 50, por defecto 25).
- `-c, --concurrency <int>`: Concurrencia máxima asíncrona (1 a 20, por defecto 5).
- `-f, --filter-positive`: Exportar únicamente los repositorios con GH-AW detectado.
- `--resume / --no-resume`: Reanudar desde checkpoint previo ante interrupciones (activo por defecto).
- `-k, --checkpoint <path>`: Ruta personalizada para el archivo de checkpoint.
- `-t, --token <str>`: Token de GitHub (anula la variable de entorno).

**Compatibilidad Retroactiva:**
Invocar directamente `pkminer repos.csv -o salida.csv` ejecuta automáticamente el subcomando `detect` sin necesidad de escribir la palabra `detect`.

---

### B. Subcomando `extract`
Ejecuta la extracción en 2 fases: localiza los pares de archivos confirmados (Fase 1), descarga metadatos del repositorio y contenido Blob `.md` (Fase 2), parsea el frontmatter YAML y cuerpo Markdown de forma resiliente, y genera las 3 tablas Parquet.

```bash
pkminer extract <input.csv> [OPCIONES]
```

**Opciones principales:**
- `-d, --output-dir <directorio>`: Carpeta de destino donde se guardarán los archivos Parquet (por defecto `./dataset`).
- `-b, --batch-size <int>`: Cantidad de repositorios por consulta GraphQL (por defecto 25).
- `-c, --concurrency <int>`: Consultas simultáneas concurrentes (por defecto 5).
- `-t, --token <str>`: Token de acceso de GitHub.

**Archivos generados en `--output-dir`:**
1. `repositories.parquet`: Metadatos del repositorio (estrellas, forks, licencia, lenguaje).
2. `workflows.parquet`: Especificación de agentes, prompts, herramientas y permisos.
3. `workflow_triggers.parquet`: Disparadores y eventos desnormalizados.
4. `README.md`: Dataset Card con metadatos YAML compatibles con Hugging Face.

---

### C. Subcomando `upload`
Sube automáticamente el dataset generado a Hugging Face Datasets.

```bash
pkminer upload [OPCIONES]
```

**Opciones principales:**
- `-d, --dataset-dir <directorio>`: Carpeta que contiene las tablas Parquet y el README.md (por defecto `./dataset`).
- `-r, --hf-repo <usuario/dataset>`: **(Obligatorio)** Identificador del repositorio en Hugging Face (ej. `mi-usuario/gh-agentic-workflows`).
- `-t, --token <str>`: Token de Hugging Face con permisos de escritura (o variable `HF_TOKEN`).

---

## 5. Tutorial Paso a Paso: Flujo Completo de Extremo a Extremo

A continuación se ilustra un ciclo completo de minería, extracción y publicación.

### Paso 1: Detección inicial de repositorios candidatos

Supongamos un archivo `data/gh_aw_repositories.csv` con repositorios de GitHub:

```bash
pkminer detect data/gh_aw_repositories.csv -o output.csv --filter-positive
```

*Salida esperada:*
```text
ℹ️ Archivo cargado: data/gh_aw_repositories.csv (295 filas analizadas, 295 repositorios únicos)
⠋ Analizando repositorios con GraphQL... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 295/295 0:00:12

                       📊 Resumen de Ejecución PeakyMiner                       
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Métrica                        ┃                                       Valor ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Total repositorios en entrada  │                                         295 │
│ Repositorios evaluados         │                                         295 │
│ GH-AW Detectados ✅            │                                          42 │
│ GH-AW No detectados ❌         │                                         253 │
│ Registros exportados           │                                          42 │
│ Archivo de salida              │ /home/user/PeakyMiner/output.csv            │
│ Tiempo transcurrido            │                                     12.45 s │
└────────────────────────────────┴─────────────────────────────────────────────┘

✨ Proceso finalizado con éxito al 100%.
```

---

### Paso 2: Extracción profunda y generación de Parquet

Ejecutamos `pkminer extract` pasando el CSV filtrado:

```bash
pkminer extract output.csv --output-dir ./dataset
```

*Salida esperada:*
```text
ℹ️ Columna 'has_ghaw' detectada: Procesando 42 repositorios positivos.
⠋ Fase 1: Localizando pares GH-AW... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 42/42 0:00:03
⠋ Fase 2: Extracción profunda de blobs... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 42/42 0:00:05

                 📊 Resumen de Extracción PeakyMiner (Fase 1 y Fase 2)                 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Métrica                          ┃                                     Valor ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Repositorios evaluados           │                                        42 │
│ Repositorios GH-AW confirmados   │                                        42 │
│ Workflows extraídos              │                                        68 │
│ Triggers desnormalizados         │                                       112 │
│ Directorio de salida             │ /home/user/PeakyMiner/dataset             │
│ Tiempo transcurrido              │                                    8.21 s │
└──────────────────────────────────┴───────────────────────────────────────────┘

✨ Extracción completada exitosamente.
Archivos generados en /home/user/PeakyMiner/dataset:
  - repositories.parquet (42 registros)
  - workflows.parquet (68 registros)
  - workflow_triggers.parquet (112 registros)
  - README.md (Dataset Card para Hugging Face)
```

---

### Paso 3: Inspección rápida del dataset Parquet en Python

Podemos verificar la estructura con pandas o pyarrow:

```python
import pyarrow.parquet as pq

# Leer tabla de workflows
workflows = pq.read_table("dataset/workflows.parquet").to_pandas()
print(workflows[["name", "model_engine", "body_word_count"]].head())

# Leer tabla de repositorios
repos = pq.read_table("dataset/repositories.parquet").to_pandas()
print(repos[["canonical_url", "stars_count", "primary_language"]].head())
```

---

### Paso 4: Publicación en Hugging Face Datasets

Una vez verificadas las tablas, publicamos en Hugging Face:

```bash
pkminer upload --dataset-dir ./dataset --hf-repo mi-organizacion/gh-agentic-workflows-dataset
```

*Salida esperada:*
```text
╭────────────────── 🚀 Hugging Face Upload Completado ──────────────────╮
│ Dataset publicado exitosamente en Hugging Face Datasets.              │
│                                                                       │
│ 🔗 https://huggingface.co/datasets/mi-organizacion/gh-agentic-workflows-dataset │
│                                                                       │
│ Archivos publicados:                                                  │
│   - repositories.parquet                                              │
│   - workflows.parquet                                                 │
│   - workflow_triggers.parquet                                         │
│   - README.md (Dataset Card)                                          │
╰───────────────────────────────────────────────────────────────────────╯
```

