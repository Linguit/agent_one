import sqlalchemy as sa

from alembic import op

revision = "0004_knowledge_documents"
down_revision = "0003_background_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime, nullable=False),
        sa.Column("index_status", sa.String, nullable=False),
        sa.Column("chunking", sa.JSON, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.DateTime),
    )
    op.create_index(
        "uq_knowledge_documents_active_hash",
        "knowledge_documents",
        ["owner_user_id", "knowledge_base_id", "sha256"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_documents")
