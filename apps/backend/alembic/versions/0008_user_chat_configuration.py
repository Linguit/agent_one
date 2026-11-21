import sqlalchemy as sa

from alembic import op

revision = "0008_user_chat_configuration"
down_revision = "0007_agent_tool_audits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, fields in (
        (
            "user_chat_prompts",
            [sa.Column("label", sa.String(100), nullable=False)],
        ),
        (
            "user_chat_skills",
            [
                sa.Column("filename", sa.String, nullable=False),
                sa.Column("name", sa.String(64), nullable=False),
                sa.Column("description", sa.String(1024), nullable=False),
                sa.Column("summary", sa.String(1024), nullable=False),
                sa.Column("metadata", sa.JSON, nullable=False),
                sa.UniqueConstraint("owner_user_id", "name"),
                sa.CheckConstraint("filename = 'SKILL.md'"),
            ],
        ),
    ):
        op.create_table(
            name,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("content", sa.Text, nullable=False),
            sa.UniqueConstraint("owner_user_id", "id"),
            *fields,
        )
    op.create_table(
        "user_chat_configurations",
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("selected_prompt_id", sa.String(36)),
        sa.Column("selected_skill_ids", sa.JSON, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "selected_prompt_id"],
            ["user_chat_prompts.owner_user_id", "user_chat_prompts.id"],
        ),
    )


def downgrade() -> None:
    op.drop_table("user_chat_configurations")
    op.drop_table("user_chat_skills")
    op.drop_table("user_chat_prompts")
