import sqlalchemy as sa

from alembic import op

revision = "0007_agent_tool_audits"
down_revision = "0006_chat_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tool_call_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chat_session_id", sa.String(36)),
        sa.Column("diagnostic_task_id", sa.String(36)),
        sa.Column("tool_name", sa.String, nullable=False),
        sa.Column("arguments", sa.JSON, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("result_summary", sa.String),
        sa.Column("error_message", sa.String),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime),
        sa.Column("duration_ms", sa.Integer),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "chat_session_id"],
            ["chat_sessions.owner_user_id", "chat_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("(chat_session_id IS NULL) <> (diagnostic_task_id IS NULL)"),
        sa.CheckConstraint("""
            (status = 'started' AND completed_at IS NULL AND duration_ms IS NULL
             AND result_summary IS NULL AND error_message IS NULL)
            OR (completed_at IS NOT NULL AND duration_ms IS NOT NULL AND duration_ms >= 0 AND (
                (status = 'completed' AND result_summary IS NOT NULL AND error_message IS NULL)
                OR (status = 'failed' AND error_message IS NOT NULL AND result_summary IS NULL)
            ))
        """),
    )
    op.create_index(
        "ix_agent_tool_audits_chat",
        "agent_tool_call_audits",
        ["owner_user_id", "chat_session_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_table("agent_tool_call_audits")
