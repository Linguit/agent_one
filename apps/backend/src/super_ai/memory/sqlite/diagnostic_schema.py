from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
)

metadata = MetaData()


def owned(name: str, *columns: Column[Any]) -> Table:
    return Table(
        name,
        metadata,
        Column("id", String, primary_key=True),
        Column("owner_user_id", String, nullable=False, index=True),
        Column("task_id", String, nullable=False, index=True),
        Column("created_at", DateTime, nullable=False),
        *columns,
        ForeignKeyConstraint(
            ["owner_user_id", "task_id"],
            ["diagnostic_tasks.owner_user_id", "diagnostic_tasks.id"],
        ),
    )


tasks = Table(
    "diagnostic_tasks",
    metadata,
    Column("id", String, primary_key=True),
    Column("owner_user_id", String, nullable=False, index=True),
    Column("safe_input", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False),
)
# Composite parent key is created in migration and used by all child tables.
steps = owned(
    "diagnostic_steps",
    Column("plan_version", Integer, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("tool_name", String, nullable=False),
    Column("arguments", JSON, nullable=False),
    Column("purpose", String, nullable=False),
    Column("status", String, nullable=False),
    Column("audit_id", String),
    Column("error_code", String),
)
evidence = owned(
    "diagnostic_evidence",
    Column("step_id", String),
    Column("kind", String, nullable=False),
    Column("source", String, nullable=False),
    Column("content", JSON, nullable=False),
)
reports = owned(
    "diagnostic_reports",
    Column("job_id", String, nullable=False),
    Column("content", String, nullable=False),
    Column("mode", String, nullable=False),
)
links = owned(
    "report_evidence_links",
    Column("report_id", String, nullable=False),
    Column("evidence_id", String, nullable=False),
    Column("claim", String, nullable=False),
)
checkpoints = owned(
    "graph_checkpoints",
    Column("job_id", String, nullable=False),
    Column("next_node", String, nullable=False),
    Column("state", JSON, nullable=False),
    Column("plan_version", Integer, nullable=False),
)
