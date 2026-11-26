import sqlalchemy as sa

from alembic import op

revision = "0012_diagnostic_cases"
down_revision = "0011_aiops_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "metadata",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_table(
        "aiops_diagnostic_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False, unique=True),
        sa.Column("report_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("index_task_id", sa.String(36), nullable=False),
        sa.Column("alert_name", sa.String, nullable=False),
        sa.Column("service", sa.String, nullable=False),
        sa.Column("keywords", sa.JSON, nullable=False),
        sa.Column("root_cause", sa.Text, nullable=False),
        sa.Column("remediation", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("evidence_ids", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "task_id"],
            ["diagnostic_tasks.owner_user_id", "diagnostic_tasks.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "task_id", "report_id"],
            [
                "diagnostic_reports.owner_user_id",
                "diagnostic_reports.task_id",
                "diagnostic_reports.id",
            ],
        ),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
        sa.ForeignKeyConstraint(["index_task_id"], ["document_index_tasks.id"]),
    )
    op.create_index(
        "ix_diagnostic_cases_owner", "aiops_diagnostic_cases", ["owner_user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("aiops_diagnostic_cases")
    # Native DROP COLUMN preserves P11 triggers that reference knowledge_documents.
    op.drop_column("knowledge_documents", "metadata")
