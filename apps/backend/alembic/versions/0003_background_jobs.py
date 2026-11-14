import sqlalchemy as sa

from alembic import op

revision = "0003_background_jobs"
down_revision = "0002_authentication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("resource_type", sa.String, nullable=False),
        sa.Column("resource_id", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("max_attempts", sa.Integer, nullable=False),
        sa.Column("timeout_seconds", sa.Integer, nullable=False),
        sa.Column("available_at", sa.DateTime, nullable=False),
        sa.Column("lease_owner", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime),
        sa.Column("cancel_requested_at", sa.DateTime),
        sa.Column("retry_of_job_id", sa.String(36), sa.ForeignKey("background_jobs.id")),
        sa.Column("error_message", sa.String),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
    )

    op.create_table(
        "background_job_events",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("background_jobs.id"), primary_key=True),
        sa.Column("sequence", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_background_jobs_owner", "background_jobs", ["owner_user_id", "created_at"])
    op.create_index(
        "ix_background_jobs_queue", "background_jobs", ["status", "kind", "available_at"]
    )
    op.create_index("ix_background_jobs_lease", "background_jobs", ["status", "lease_expires_at"])


def downgrade() -> None:
    op.drop_table("background_job_events")
    op.drop_table("background_jobs")
