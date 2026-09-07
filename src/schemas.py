"""
Esquemas explícitos de PyArrow para el modelado relacional de PeakyMiner en Apache Parquet.
Define tipos de datos, restricciones de nulabilidad y estructura tabular para:
- repositories.parquet
- workflows.parquet
- workflow_triggers.parquet
"""

import pyarrow as pa

REPOSITORIES_SCHEMA = pa.schema([
    pa.field("repo_id", pa.string(), nullable=False),
    pa.field("owner", pa.string(), nullable=False),
    pa.field("name", pa.string(), nullable=False),
    pa.field("canonical_url", pa.string(), nullable=False),
    pa.field("stars_count", pa.int64(), nullable=False),
    pa.field("forks_count", pa.int64(), nullable=False),
    pa.field("primary_language", pa.string(), nullable=True),
    pa.field("is_fork", pa.bool_(), nullable=False),
    pa.field("license_spdx", pa.string(), nullable=True),
    pa.field("default_branch", pa.string(), nullable=False),
    pa.field("scanned_at", pa.timestamp("us"), nullable=False),
])

WORKFLOWS_SCHEMA = pa.schema([
    pa.field("workflow_id", pa.string(), nullable=False),
    pa.field("repo_id", pa.string(), nullable=False),
    pa.field("file_path", pa.string(), nullable=False),
    pa.field("basename", pa.string(), nullable=False),
    pa.field("lock_path", pa.string(), nullable=False),
    pa.field("blob_sha", pa.string(), nullable=False),
    pa.field("name", pa.string(), nullable=True),
    pa.field("description", pa.string(), nullable=True),
    pa.field("model_engine", pa.string(), nullable=True),
    pa.field("tools", pa.list_(pa.string()), nullable=True),
    pa.field("permissions", pa.string(), nullable=True),
    pa.field("raw_frontmatter", pa.string(), nullable=True),
    pa.field("body_markdown", pa.string(), nullable=True),
    pa.field("body_word_count", pa.int64(), nullable=False),
    pa.field("body_char_count", pa.int64(), nullable=False),
    pa.field("has_syntax_error", pa.bool_(), nullable=False),
])

WORKFLOW_TRIGGERS_SCHEMA = pa.schema([
    pa.field("trigger_id", pa.string(), nullable=False),
    pa.field("workflow_id", pa.string(), nullable=False),
    pa.field("event_type", pa.string(), nullable=False),
    pa.field("trigger_config", pa.string(), nullable=True),
])

