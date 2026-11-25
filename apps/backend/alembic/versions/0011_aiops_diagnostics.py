import sqlalchemy as sa

from alembic import op

revision = "0011_aiops_diagnostics"
down_revision = "0010_mcp_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_tasks",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("owner_user_id", sa.String, nullable=False),
        sa.Column("safe_input", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("owner_user_id", "id"),
    )
    columns: dict[str, list[sa.Column[object]]] = {
        "diagnostic_steps": [
            sa.Column("plan_version", sa.Integer, nullable=False),
            sa.Column("ordinal", sa.Integer, nullable=False),
            sa.Column("tool_name", sa.String, nullable=False),
            sa.Column("arguments", sa.JSON, nullable=False),
            sa.Column("purpose", sa.String, nullable=False),
            sa.Column("status", sa.String, nullable=False),
            sa.Column("audit_id", sa.String),
            sa.Column("error_code", sa.String),
        ],
        "diagnostic_evidence": [
            sa.Column("step_id", sa.String),
            sa.Column("kind", sa.String, nullable=False),
            sa.Column("source", sa.String, nullable=False),
            sa.Column("content", sa.JSON, nullable=False),
        ],
        "diagnostic_reports": [
            sa.Column("job_id", sa.String, nullable=False),
            sa.Column("content", sa.String, nullable=False),
            sa.Column("mode", sa.String, nullable=False),
        ],
        "report_evidence_links": [
            sa.Column("report_id", sa.String, nullable=False),
            sa.Column("evidence_id", sa.String, nullable=False),
            sa.Column("claim", sa.String, nullable=False),
        ],
        "graph_checkpoints": [
            sa.Column("job_id", sa.String, nullable=False),
            sa.Column("next_node", sa.String, nullable=False),
            sa.Column("state", sa.JSON, nullable=False),
            sa.Column("plan_version", sa.Integer, nullable=False),
        ],
    }
    op.create_index("ix_diagnostic_tasks_owner", "diagnostic_tasks", ["owner_user_id"])
    for name, extra in columns.items():
        op.create_table(
            name,
            sa.Column("id", sa.String, primary_key=True),
            sa.Column("owner_user_id", sa.String, nullable=False),
            sa.Column("task_id", sa.String, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
            *extra,
            sa.UniqueConstraint("owner_user_id", "task_id", "id"),
            sa.ForeignKeyConstraint(
                ["owner_user_id", "task_id"],
                ["diagnostic_tasks.owner_user_id", "diagnostic_tasks.id"],
            ),
        )
        op.create_index(f"ix_{name}_owner_task", name, ["owner_user_id", "task_id"])
    # SQLite cannot add composite foreign keys after creation. Rebuild links in batch mode.
    with op.batch_alter_table("report_evidence_links") as batch:
        batch.create_foreign_key(
            "fk_report_link_report",
            "diagnostic_reports",
            ["owner_user_id", "task_id", "report_id"],
            ["owner_user_id", "task_id", "id"],
        )
        batch.create_foreign_key(
            "fk_report_link_evidence",
            "diagnostic_evidence",
            ["owner_user_id", "task_id", "evidence_id"],
            ["owner_user_id", "task_id", "id"],
        )
    op.create_index(
        "ix_diagnostic_tool_audits",
        "agent_tool_call_audits",
        ["owner_user_id", "diagnostic_task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_diagnostic_tool_audits", "agent_tool_call_audits")
    for name in (
        "graph_checkpoints",
        "report_evidence_links",
        "diagnostic_reports",
        "diagnostic_evidence",
        "diagnostic_steps",
        "diagnostic_tasks",
    ):
        op.drop_table(name)
