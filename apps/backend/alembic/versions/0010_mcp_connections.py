import sqlalchemy as sa

from alembic import op

revision = "0010_mcp_connections"
down_revision = "0009_session_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("transport", sa.String(32), nullable=False),
        sa.Column("url", sa.String(4096), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("timeoutSeconds", sa.Integer, nullable=False),
        sa.Column("retries", sa.Integer, nullable=False),
        sa.Column("lastCheck", sa.DateTime),
        sa.Column("lastError", sa.Text),
        sa.Column("discoveredTools", sa.JSON, nullable=False),
        sa.Column("createdAt", sa.DateTime, nullable=False),
        sa.Column("updatedAt", sa.DateTime, nullable=False),
        sa.CheckConstraint("transport IN ('sse', 'streamable_http')"),
        sa.CheckConstraint('"timeoutSeconds" BETWEEN 1 AND 300'),
        sa.CheckConstraint("retries BETWEEN 0 AND 5"),
    )
    op.create_index("ix_mcp_connections_owner", "mcp_connections", ["owner"])


def downgrade() -> None:
    op.drop_table("mcp_connections")
