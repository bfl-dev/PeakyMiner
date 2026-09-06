"""
Pruebas unitarias para el extractor de workflows (src/extractor.py).
Verifica el parseo resiliente de frontmatter YAML, cuerpo Markdown, métricas y disparadores.
"""

from src.extractor import (
    extract_raw_frontmatter,
    extract_workflow_record,
    parse_workflow_content,
)


def test_parse_workflow_content_valid() -> None:
    """Verifica el parseo de un archivo Markdown con frontmatter YAML válido."""
    content = """---
name: Issue Triage Agent
description: Clasifica issues automáticamente con LLM
model: gpt-4o
tools:
  - search_issues
  - add_label
permissions:
  issues: write
on:
  schedule:
    - cron: "0 9 * * *"
---
# Prompt del Agente
Eres un agente de clasificación de incidencias.
Debes revisar los nuevos issues y asignar etiquetas apropiadas.
"""
    metadata, body, has_syntax_error = parse_workflow_content(content)

    assert has_syntax_error is False
    assert metadata["name"] == "Issue Triage Agent"
    assert metadata["description"] == "Clasifica issues automáticamente con LLM"
    assert metadata["model"] == "gpt-4o"
    assert metadata["tools"] == ["search_issues", "add_label"]
    assert metadata["permissions"] == {"issues": "write"}
    assert metadata["on"] == {"schedule": [{"cron": "0 9 * * *"}]}
    assert "# Prompt del Agente" in body
    assert "Eres un agente de clasificación" in body


def test_parse_workflow_content_corrupted_yaml() -> None:
    """Verifica que YAML corrupto no cause excepciones, marque has_syntax_error y preserve el body."""
    corrupted_content = """---
name: Corrupted Workflow
invalid_yaml: [unclosed list
  bad_indent: : : :::
---
# Prompt de Respaldo
Instrucciones conservadas a pesar del error de sintaxis en el YAML.
"""
    metadata, body, has_syntax_error = parse_workflow_content(corrupted_content)

    assert has_syntax_error is True
    assert metadata == {}
    assert "# Prompt de Respaldo" in body
    assert "Instrucciones conservadas" in body


def test_parse_workflow_content_pure_markdown() -> None:
    """Verifica el comportamiento con un archivo Markdown sin delimitadores de frontmatter."""
    pure_markdown = """# Workflow sin Frontmatter
Este archivo solo contiene instrucciones en Markdown plano sin metadatos YAML.
"""
    metadata, body, has_syntax_error = parse_workflow_content(pure_markdown)

    assert has_syntax_error is False
    assert metadata == {}
    assert "# Workflow sin Frontmatter" in body


def test_parse_workflow_content_empty() -> None:
    """Verifica el comportamiento con cadenas vacías o compuestas solo por espacios."""
    metadata, body, has_syntax_error = parse_workflow_content("")
    assert metadata == {}
    assert body == ""
    assert has_syntax_error is False


def test_extract_raw_frontmatter() -> None:
    """Verifica la extracción del bloque textual YAML original."""
    raw_text = """---
name: Sample
model: gpt-4
---
Body text here
"""
    extracted = extract_raw_frontmatter(raw_text)
    assert "name: Sample" in extracted
    assert "model: gpt-4" in extracted
    assert "---" not in extracted

    # Sin frontmatter
    assert extract_raw_frontmatter("Solo texto Markdown") == ""


def test_extract_workflow_record_complete() -> None:
    """Verifica la creación completa de WorkflowRecord y WorkflowTriggerRecord."""
    raw_text = """---
name: Release Agent
description: Genera notas de lanzamiento
model_engine: claude-3-5-sonnet
tools:
  - git_log
  - gh_release
permissions:
  contents: write
on:
  push:
    branches:
      - main
  workflow_dispatch: null
---
# Instrucciones de Release
Analiza los commits recientes y redacta notas de lanzamiento claras.
"""
    repo_id = "test-repo-uuid-123"
    wf_rec, triggers = extract_workflow_record(
        repo_id=repo_id,
        file_path=".github/workflows/release.md",
        basename="release",
        lock_path=".github/workflows/release.lock.yml",
        blob_sha="abc1234567890abcdef1234567890abcdef1234",
        raw_text=raw_text,
    )

    # Validar WorkflowRecord
    assert wf_rec.repo_id == repo_id
    assert wf_rec.basename == "release"
    assert wf_rec.name == "Release Agent"
    assert wf_rec.description == "Genera notas de lanzamiento"
    assert wf_rec.model_engine == "claude-3-5-sonnet"
    assert wf_rec.tools == ["git_log", "gh_release"]
    assert wf_rec.permissions == '{"contents": "write"}'
    assert wf_rec.body_word_count > 0
    assert wf_rec.body_char_count > 0
    assert wf_rec.has_syntax_error is False

    # Validar Triggers desnormalizados
    assert len(triggers) == 2
    event_types = [t.event_type for t in triggers]
    assert "push" in event_types
    assert "workflow_dispatch" in event_types

    push_trigger = next(t for t in triggers if t.event_type == "push")
    assert push_trigger.workflow_id == wf_rec.workflow_id
    assert "main" in push_trigger.trigger_config


def test_extract_workflow_record_triggers_variations() -> None:
    """Verifica el soporte para disparadores definidos como string y como lista."""
    # Disparador como string
    text_str_trigger = """---
name: Simple Agent
on: pull_request
---
Instrucciones
"""
    _, trigs_str = extract_workflow_record(
        repo_id="r1",
        file_path="f1.md",
        basename="f1",
        lock_path="f1.lock.yml",
        blob_sha="sha1",
        raw_text=text_str_trigger,
    )
    assert len(trigs_str) == 1
    assert trigs_str[0].event_type == "pull_request"

    # Disparador como lista
    text_list_trigger = """---
name: Multi Agent
on: [push, issue_comment]
---
Instrucciones
"""
    _, trigs_list = extract_workflow_record(
        repo_id="r1",
        file_path="f2.md",
        basename="f2",
        lock_path="f2.lock.yml",
        blob_sha="sha2",
        raw_text=text_list_trigger,
    )
    assert len(trigs_list) == 2
    assert [t.event_type for t in trigs_list] == ["push", "issue_comment"]

