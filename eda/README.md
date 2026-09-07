# 📊 PeakyMiner - Análisis Exploratorio de Datos (EDA)

Este directorio contiene el estudio exploratorio de datos (EDA) integral sobre el ecosistema emergente de **GitHub Agentic Workflows (GH-AW)**, realizado sobre los datos extraídos y modelados por **PeakyMiner** (`pkminer`) en formato relacional Apache Parquet.

* 🌐 **Dataset Oficial Publicado:** [Hugging Face Datasets: apa9s/gh-agentic-workflows](https://huggingface.co/datasets/apa9s/gh-agentic-workflows)
* 🏛️ **Formato de Persistencia:** Apache Parquet con compresión Snappy e identificadores deterministas UUIDv5.
* 📦 **Volumen Total:** 292 repositorios confirmados, 1,368 workflows y 3,475 disparadores de eventos.

---

## 📁 Estructura del Directorio `eda/`

```text
eda/
├── README.md                           # Guía técnica de reproducción, instalación y ejecución
├── data/
│   ├── raw/                            # Tablas Parquet base generadas en la extracción
│   │   ├── repositories.parquet        # (292 filas, metadatos generales del repositorio)
│   │   ├── workflows.parquet           # (1,368 filas, especificación completa del agente y prompts)
│   │   └── workflow_triggers.parquet   # (3,475 filas, eventos y reglas de activación)
│   └── processed/                      # Tablas limpias generadas por el Cuaderno 01
│       ├── repositories_clean.parquet  # Repositorios con campos auxiliares normalizados
│       ├── workflows_clean.parquet     # Workflows con listas de tools imputadas y tipos consistentes
│       └── workflow_triggers_clean.parquet # Triggers validados para consumo analítico
├── 01_descripcion_y_calidad.ipynb      # Cuaderno 1: Descripción, relaciones 3NF y auditoría de calidad
└── 02_exploracion_y_hallazgos.ipynb    # Cuaderno 2: Distribuciones, frontmatter, prompts y preguntas empíricas
```

---

## 🚀 Guía de Reproducción Paso a Paso

### 1. Requisitos Previos
* Python 3.10 o superior (el entorno del proyecto utiliza Python 3.14).
* Gestor de paquetes `uv` (recomendado) o `pip`/`venv`.

### 2. Configuración del Entorno Virtual

#### Opción A: Con `uv` (Recomendado)
```bash
# Desde la raíz del repositorio PeakyMiner:
uv sync --extra eda --extra dev
```

#### Opción B: Con `venv` y `pip` estándar
```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias del proyecto y del grupo EDA
pip install -e ".[eda,dev]"
```

### 3. Registro y Selección del Kernel de Jupyter

Para que JupyterLab reconozca el entorno virtual con todas las dependencias (`pandas`, `pyarrow`, `matplotlib`, `seaborn`, `scipy`):

```bash
# Registrar el kernel en Jupyter
uv run python -m ipykernel install --user --name peakyminer --display-name "Python (PeakyMiner)"
```

Al abrir cualquiera de los notebooks en la interfaz de JupyterLab, asegúrate de que el kernel seleccionado en la esquina superior derecha sea **Python (PeakyMiner)**.

### 4. Iniciar JupyterLab

```bash
# Iniciar el servidor interactivo de JupyterLab
uv run jupyter lab
```
O simplemente:
```bash
source .venv/bin/activate
jupyter lab
```

---

## 🔄 Protocolo de Ejecución de los Notebooks

Los cuadernos fueron diseñados con **estricto desacoplamiento de memoria** y deben ejecutarse en el siguiente orden secuencial:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. eda/01_descripcion_y_calidad.ipynb                       │
│    - Carga datos desde eda/data/raw/                        │
│    - Audita nulos, duplicados, integridad PK/FK y sintaxis   │
│    - Aplica imputaciones y estandarizaciones controladas    │
│    - Exporta tablas limpias a eda/data/processed/           │
└──────────────────────────────┬──────────────────────────────┘
                               │ Genera archivos limpios
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. eda/02_exploracion_y_hallazgos.ipynb                     │
│    - Consume exclusivamente eda/data/processed/             │
│    - Analiza distribución de workflows por repositorio      │
│    - Explora frontmatter (motores LLM, tools exploded)      │
│    - Analiza extensión léxica del body (prompts)            │
│    - Resuelve las 2 Preguntas de Investigación              │
│    - Sintetiza hallazgos y limitaciones                     │
└─────────────────────────────────────────────────────────────┘
```

> ⚠️ **Importante:** El Cuaderno 02 requiere que `eda/data/processed/` contenga las tablas procesadas generadas al ejecutar el Cuaderno 01. No intente ejecutar el Cuaderno 02 en un entorno limpio sin haber ejecutado previamente el Cuaderno 01.

### Ejecución Automatizada sin Interfaz Gráfica (CLI)
Si deseas re-ejecutar ambos cuadernos y actualizar sus salidas directamente desde la terminal:

```bash
# Ejecutar Cuaderno 1
uv run jupyter nbconvert --to notebook --execute --inplace eda/01_descripcion_y_calidad.ipynb

# Ejecutar Cuaderno 2
uv run jupyter nbconvert --to notebook --execute --inplace eda/02_exploracion_y_hallazgos.ipynb
```

---

## 💡 Síntesis de Principales Hallazgos

1. **Hipercentralización (Ley de Potencias):** El 21.9% de los agentes registrados en el ecosistema provienen de un único repositorio canónico (`github/gh-aw`), y el Top 3 de repositorios concentra el 31% del total. La adopción en el resto de la comunidad es incipiente o experimental ($\le 2$ workflows por proyecto).
2. **Invocación Bajo Demanda vs. Reactiva:** A diferencia de CI/CD tradicional centrado en `push`/`pull_request`, los agentes son activados predominantemente vía `workflow_dispatch` (28.5%) y `schedule` (21.1%), priorizando la supervisión humana (*human-in-the-loop*) y mantenimientos periódicos.
3. **Herramientas Operativas:** Las herramientas `github` (interacción con API) y `bash` (ejecución de scripts) representan más del 70% de las invocaciones, evidenciando agentes focalizados en DevOps y ciclo de vida de desarrollo de software.
4. **Relación Popularidad vs. Complejidad:** Existe una correlación positiva moderada ($\rho = 0.14$) entre las estrellas de un repositorio y la extensión del prompt del agente, observándose que los proyectos consolidados tienden a asignar conjuntos más amplios de herramientas y directivas defensivas más detalladas.
