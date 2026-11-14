from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Table

from super_ai.memory.base import Base

jobs = Table(
    "background_jobs",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("owner_user_id", String(36), nullable=False),
    Column("kind", String, nullable=False),
    Column("resource_type", String, nullable=False),
    Column("resource_id", String, nullable=False),
    Column("status", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("timeout_seconds", Integer, nullable=False),
    Column("available_at", DateTime, nullable=False),
    Column("lease_owner", String(36)),
    Column("lease_expires_at", DateTime),
    Column("cancel_requested_at", DateTime),
    Column("retry_of_job_id", String(36), ForeignKey("background_jobs.id")),
    Column("error_message", String),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    Column("started_at", DateTime),
    Column("completed_at", DateTime),
)

events = Table(
    "background_job_events",
    Base.metadata,
    Column("job_id", String(36), ForeignKey("background_jobs.id"), primary_key=True),
    Column("sequence", Integer, primary_key=True),
    Column("kind", String, nullable=False),
    Column("data", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

Index("ix_background_jobs_owner", jobs.c.owner_user_id, jobs.c.created_at)
Index("ix_background_jobs_queue", jobs.c.status, jobs.c.kind, jobs.c.available_at)
Index("ix_background_jobs_lease", jobs.c.status, jobs.c.lease_expires_at)
