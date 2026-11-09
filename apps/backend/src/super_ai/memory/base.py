from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, MetaData, String, Table
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> UUID:
    return uuid4()


def json_value(value: Any) -> Any:
    return value


persistence_probe = Table(
    "persistence_probe",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False, default=dict),
)
