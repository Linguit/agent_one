import sqlalchemy as sa

from alembic import op

revision = "0005_document_index_tasks"
down_revision = "0004_knowledge_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_index_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("failure_reason", sa.String),
        sa.Column("retry_of_task_id", sa.String(36), sa.ForeignKey("document_index_tasks.id")),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
    )
    op.create_index(
        "ix_document_index_tasks_document",
        "document_index_tasks",
        ["owner_user_id", "knowledge_base_id", "document_id", "created_at"],
    )
    op.create_index(
        "uq_document_index_tasks_active",
        "document_index_tasks",
        ["owner_user_id", "knowledge_base_id", "document_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending', 'running')"),
    )
    op.create_index(
        "uq_document_index_task_job",
        "background_jobs",
        ["owner_user_id", "resource_id"],
        unique=True,
        sqlite_where=sa.text("resource_type = 'document_index_task'"),
    )
    op.execute("""
        CREATE TRIGGER project_document_index_status
        AFTER UPDATE OF status ON background_jobs
        WHEN NEW.resource_type = 'document_index_task'
        BEGIN
            UPDATE document_index_tasks
            SET status = CASE NEW.status WHEN 'queued' THEN 'pending' ELSE NEW.status END,
                failure_reason = CASE WHEN NEW.status = 'failed' THEN NEW.error_message END,
                updated_at = NEW.updated_at,
                started_at = COALESCE(started_at, NEW.started_at),
                completed_at = NEW.completed_at
            WHERE id = NEW.resource_id AND owner_user_id = NEW.owner_user_id;

            UPDATE knowledge_documents
            SET index_status = CASE NEW.status WHEN 'queued' THEN 'pending' ELSE NEW.status END
            WHERE deleted_at IS NULL AND owner_user_id = NEW.owner_user_id
                AND (id, knowledge_base_id) = (
                    SELECT document_id, knowledge_base_id FROM document_index_tasks
                    WHERE id = NEW.resource_id AND owner_user_id = NEW.owner_user_id
                );
        END
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER project_document_index_status")
    op.drop_index("uq_document_index_task_job", table_name="background_jobs")
    op.execute("""
        DELETE FROM background_job_events
        WHERE job_id IN (
            SELECT id FROM background_jobs WHERE resource_type = 'document_index_task'
        )
    """)
    op.execute("DELETE FROM background_jobs WHERE resource_type = 'document_index_task'")
    op.execute("UPDATE knowledge_documents SET index_status = 'pending'")
    op.drop_table("document_index_tasks")
