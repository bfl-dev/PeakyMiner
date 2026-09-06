# 🏛️ Diagrama Entidad-Relación (ER) - PeakyMiner

Este documento describe el modelo de datos relacional para la persistencia del dataset de **GitHub Agentic Workflows (GH-AW)** en formato **Apache Parquet**.

---

## 1. Diagrama Entidad-Relación (Mermaid)

```mermaid
erDiagram
    REPOSITORIES ||--o{ WORKFLOWS : "1:N contiene"
    WORKFLOWS ||--o{ WORKFLOW_TRIGGERS : "1:N activa"

    REPOSITORIES {
        string repo_id PK "UUIDv5(NAMESPACE_URL, canonical_url)"
        string owner "Propietario u organización"
        string name "Nombre del repositorio"
        string canonical_url "URL completa de GitHub"
        int64 stars_count "Recuento de estrellas (stargazers)"
        int64 forks_count "Recuento de bifurcaciones (forks)"
        string primary_language "Lenguaje predominante (nullable)"
        bool is_fork "Si es una bifurcación de otro repo"
        string license_spdx "Identificador SPDX de licencia (nullable)"
        string default_branch "Rama predeterminada (ej: main)"
        timestamp_us scanned_at "Fecha y hora UTC del escaneo"
    }

    WORKFLOWS {
        string workflow_id PK "UUIDv5(NAMESPACE_URL, repo_id + file_path)"
        string repo_id FK "FK -> REPOSITORIES.repo_id"
        string file_path "Ruta relativa del archivo .md"
        string basename "Nombre base sin extensión"
        string lock_path "Ruta relativa del archivo .lock.yml"
        string blob_sha "Git Blob SHA (OID de 40 caracteres)"
        string name "Nombre del agente/workflow (nullable)"
        string description "Descripción del workflow (nullable)"
        string model_engine "Modelo de IA o runtime configurado (nullable)"
        list_string tools "Herramientas declaradas en el agente (nullable)"
        string permissions "Matriz de permisos de GitHub en JSON (nullable)"
        string raw_frontmatter "Bloque YAML completo original (nullable)"
        string body_markdown "Prompt e instrucciones en Markdown (nullable)"
        int64 body_word_count "Conteo de palabras en body_markdown"
        int64 body_char_count "Conteo de caracteres en body_markdown"
        bool has_syntax_error "Bandera de sintaxis YAML inválida capturada"
    }

    WORKFLOW_TRIGGERS {
        string trigger_id PK "UUIDv5(NAMESPACE_URL, workflow_id + event_type + index)"
        string workflow_id FK "FK -> WORKFLOWS.workflow_id"
        string event_type "Tipo de evento GitHub (push, schedule, etc.)"
        string trigger_config "Configuración detallada en formato JSON (nullable)"
    }
```

---

## 2. Cardinalidades y Relaciones

### Relación `REPOSITORIES` -> `WORKFLOWS` (1:N)
- **Cardinalidad:** Un repositorio puede albergar **cero, uno o múltiples** flujos de trabajo de agentes (`0..N`). Cada flujo de trabajo pertenece de forma estricta y exclusiva a un único repositorio (`1..1`).
- **Clave Foránea:** `WORKFLOWS.repo_id` referencia directamente a `REPOSITORIES.repo_id`.

### Relación `WORKFLOWS` -> `WORKFLOW_TRIGGERS` (1:N)
- **Cardinalidad:** Un workflow de agente puede activarse mediante **cero, uno o múltiples** eventos o disparadores de GitHub (`0..N`, ej. activación por `push`, `pull_request`, `schedule` con cron, o `workflow_dispatch`). Cada disparador corresponde exclusivamente a un único workflow (`1..1`).
- **Clave Foránea:** `WORKFLOW_TRIGGERS.workflow_id` referencia a `WORKFLOWS.workflow_id`.

---

## 3. Justificación de Normalización y Decisiones de Diseño

1. **Tercera Forma Normal (3NF):**
   - El modelo separa los metadatos de repositorio, las especificaciones del workflow y los eventos de disparo en entidades independientes. Se elimina la redundancia de datos (ej. replicar estrellas o lenguaje en cada workflow del mismo repo).
   - Los disparadores se desnormalizan en una tabla independiente (`WORKFLOW_TRIGGERS`) porque la especificación `on:` en GitHub Actions soporta múltiples eventos heterogéneos, listas de eventos y configuraciones anidadas (filtros de ramas, expresiones cron). Almacenarlos en una tabla dedicada facilita consultas analíticas como *"¿cuántos agentes se ejecutan con cron?"* o *"¿qué eventos son más comunes en flujos agénticos?"*.

2. **Claves Primarias Deterministas (UUIDv5):**
   - Se emplea `uuid.uuid5(uuid.NAMESPACE_URL, ...)` en lugar de auto-incrementales o UUIDv4 aleatorios.
   - **Idempotencia:** Si un repositorio o workflow es re-analizado en diferentes ejecuciones o máquinas, el `repo_id`, `workflow_id` y `trigger_id` resultantes serán idénticos.
   - **Independencia de Secuencia:** Permite la construcción concurrente de DataFrames y tablas Parquet sin necesidad de coordinar secuencias numéricas globales en memoria o base de datos.

3. **Resiliencia de Esquema ante Errores de Sintaxis:**
   - La columna `WORKFLOWS.has_syntax_error` permite identificar qué flujos de trabajo tienen YAML frontmatter corrupto sin descartar el registro ni romper el pipeline de datos. El texto original se resguarda en `raw_frontmatter` y el prompt en `body_markdown`, dejando los campos estructurados en `None`.

