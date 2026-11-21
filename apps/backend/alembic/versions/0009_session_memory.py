"""会话记忆状态；完整消息保持不变。"""

import sqlalchemy as sa

from alembic import op

revision = "0009_session_memory"
down_revision = "0008_user_chat_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.add_column(
            sa.Column("memory_mode", sa.String, nullable=False, server_default="every_30_turns")
        )
        batch.add_column(sa.Column("memory_summary", sa.Text, nullable=False, server_default=""))
        batch.add_column(
            sa.Column("compacted_message_count", sa.Integer, nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("context_tokens", sa.Integer, nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("last_compacted_at", sa.DateTime))
        batch.create_check_constraint(
            "ck_chat_memory_mode",
            "memory_mode IN ('every_30_turns', 'context_70_percent', 'manual')",
        )
        batch.create_check_constraint(
            "ck_chat_memory_counts", "compacted_message_count >= 0 AND context_tokens >= 0"
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.drop_constraint("ck_chat_memory_mode", type_="check")
        batch.drop_constraint("ck_chat_memory_counts", type_="check")
        for name in (
            "last_compacted_at",
            "context_tokens",
            "compacted_message_count",
            "memory_summary",
            "memory_mode",
        ):
            batch.drop_column(name)
