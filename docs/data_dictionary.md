# 📖 Diccionario de Datos - PeakyMiner Parquet Dataset

Este documento describe formalmente la especificación técnica de las 3 tablas relacionales generadas por `pkminer extract` y exportadas en formato **Apache Parquet** con compresión Snappy.

---

## Tabla 1: `repositories.parquet`

Almacena la información descriptiva y métricas generales del repositorio de GitHub donde se identificaron los flujos de trabajo de agentes.

| Columna | Tipo PyArrow | Restricción | Nulable | Descripción Semántica | Ejemplo |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `repo_id` | `pa.string()` | **PK** | ❌ No | UUIDv5 determinista generado a partir de la URL canónica en minúsculas. | `"6ba7b810-9dad-11d1-80b4-00c04fd430c8"` |
| `owner` | `pa.string()` | - | ❌ No | Propietario u organización titular del repositorio en GitHub. | `"azure"` |
| `name` | `pa.string()` | - | ❌ No | Nombre del repositorio. | `"azure-sdk-for-java"` |
| `canonical_url` | `pa.string()` | - | ❌ No | URL canónica HTTPS en GitHub. | `"https://github.com/azure/azure-sdk-for-java"` |
| `stars_count` | `pa.int64()` | - | ❌ No | Cantidad total de estrellas (`stargazerCount`). | `2566` |
| `forks_count` | `pa.int64()` | - | ❌ No | Cantidad de bifurcaciones (`forkCount`). | `2184` |
| `primary_language`| `pa.string()` | - | ✅ Sí | Lenguaje de programación principal detectado por GitHub. | `"Java"` |
| `is_fork` | `pa.bool_()` | - | ❌ No | Indica si el repositorio es un fork de otro proyecto. | `false` |
| `license_spdx` | `pa.string()` | - | ✅ Sí | Identificador SPDX de la licencia de código abierto. | `"MIT"` o `"Apache-2.0"` |
| `default_branch` | `pa.string()` | - | ❌ No | Nombre de la rama principal por defecto del repositorio. | `"main"` o `"master"` |
| `scanned_at` | `pa.timestamp("us")` | - | ❌ No | Marca temporal UTC en microsegundos de la ejecución del escaneo. | `2026-09-06 20:00:00.123456` |

---

## Tabla 2: `workflows.parquet`

Almacena la especificación detallada de cada flujo de trabajo de agente autónomo (`.md`), sus metadatos del frontmatter YAML, herramientas declaradas y contenido del prompt en Markdown.

| Columna | Tipo PyArrow | Restricción | Nulable | Descripción Semántica | Ejemplo |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `workflow_id` | `pa.string()` | **PK** | ❌ No | UUIDv5 determinista generado a partir de `repo_id` y `file_path`. | `"a1b2c3d4-e5f6-5a7b-8c9d-0e1f2a3b4c5d"` |
| `repo_id` | `pa.string()` | **FK** | ❌ No | Referencia al repositorio padre (`repositories.repo_id`). | `"6ba7b810-9dad-11d1-80b4-00c04fd430c8"` |
| `file_path` | `pa.string()` | - | ❌ No | Ruta relativa del archivo Markdown de especificación. | `".github/workflows/daily-triage.md"` |
| `basename` | `pa.string()` | - | ❌ No | Nombre base del archivo sin extensión. | `"daily-triage"` |
| `lock_path` | `pa.string()` | - | ❌ No | Ruta relativa del archivo de bloqueo compilado correspondiente. | `".github/workflows/daily-triage.lock.yml"` |
| `blob_sha` | `pa.string()` | - | ❌ No | Git Blob SHA (OID de 40 caracteres hexadecimales del objeto). | `"d62b9673de6f9f11a23214367dc951e94da4cc6c"` |
| `name` | `pa.string()` | - | ✅ Sí | Nombre formal del flujo de trabajo extraído del frontmatter. | `"Daily Issue Triage Agent"` |
| `description` | `pa.string()` | - | ✅ Sí | Descripción del objetivo o propósito del agente. | `"Triage incoming issues using LLM labels"` |
| `model_engine` | `pa.string()` | - | ✅ Sí | Motor de inferencia o modelo de lenguaje especificado. | `"gpt-4o"` o `"claude-3-5-sonnet"` |
| `tools` | `pa.list_(pa.string())` | - | ✅ Sí | Lista de herramientas y capacidades habilitadas para el agente. | `["read_issues", "add_label", "bash"]` |
| `permissions` | `pa.string()` | - | ✅ Sí | Matriz de permisos de GitHub Actions en formato JSON serializado. | `'{"issues": "write", "contents": "read"}'` |
| `raw_frontmatter`| `pa.string()` | - | ✅ Sí | Contenido textual original íntegro del bloque YAML. | `"name: Daily Triage\nmodel: gpt-4o\n..."` |
| `body_markdown` | `pa.string()` | - | ✅ Sí | Prompt, directivas operativas y reglas de comportamiento en Markdown. | `"# Instructions\nYou are an issue triage agent..."` |
| `body_word_count`| `pa.int64()` | - | ❌ No | Número total de palabras contenidas en `body_markdown`. | `342` |
| `body_char_count`| `pa.int64()` | - | ❌ No | Número total de caracteres contenidos en `body_markdown`. | `2145` |
| `has_syntax_error`| `pa.bool_()` | - | ❌ No | Indica si el frontmatter presentó errores de sintaxis YAML capturados. | `false` |

---

## Tabla 3: `workflow_triggers.parquet`

Almacena los eventos o disparadores de ejecución desnormalizados que activan cada flujo de trabajo.

| Columna | Tipo PyArrow | Restricción | Nulable | Descripción Semántica | Ejemplo |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `trigger_id` | `pa.string()` | **PK** | ❌ No | UUIDv5 determinista derivado de `workflow_id` + `event_type` + índice. | `"f5e4d3c2-b1a0-5f6e-7d8c-9b0a1f2e3d4c"` |
| `workflow_id` | `pa.string()` | **FK** | ❌ No | Referencia al workflow correspondiente (`workflows.workflow_id`). | `"a1b2c3d4-e5f6-5a7b-8c9d-0e1f2a3b4c5d"` |
| `event_type` | `pa.string()` | - | ❌ No | Nombre del evento de GitHub que dispara el workflow. | `"push"`, `"schedule"`, `"pull_request"` |
| `trigger_config` | `pa.string()` | - | ✅ Sí | Configuración detallada asociada al disparador en JSON (ramas, cron, tipos). | `'[{"cron": "0 8 * * 1-5"}]'` o `'{"branches": ["main"]}'` |

