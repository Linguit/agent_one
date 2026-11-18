import sqlalchemy as sa

from alembic import op

revision = "0006_chat_sessions"
down_revision = "0005_document_index_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("has_user_message", sa.Boolean, nullable=False),
        sa.Column("last_sequence", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("owner_user_id", "id"),
    )
    op.create_index(
        "ix_chat_sessions_owner_recency",
        "chat_sessions",
        ["owner_user_id", sa.text("updated_at DESC"), sa.text("id DESC")],
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "session_id"],
            ["chat_sessions.owner_user_id", "chat_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("owner_user_id", "session_id", "sequence"),
        sa.CheckConstraint("sequence >= 1"),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')"),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
