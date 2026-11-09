from pathlib import Path

import pytest
from sqlalchemy import inspect

from super_ai.memory import (
    DatabaseSettings,
    create_engine,
    database_settings,
    session_factory,
    session_scope,
)
from super_ai.memory.base import new_id, utc_now
from super_ai.memory.migrations import upgrade_head
from super_ai.memory.repository import PersistenceRecord
from super_ai.memory.sqlite import SqliteRepository


@pytest.mark.asyncio
async def test_fresh_upgrade_and_repository(tmp_path: Path) -> None:
    db = tmp_path / "memory.sqlite3"
    url = f"sqlite+aiosqlite:///{db}"
    upgrade_head(url, Path(__file__).parents[1])
    engine = create_engine(DatabaseSettings(url))
    try:
        async with engine.begin() as connection:
            tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        assert "persistence_probe" in tables
        factory = session_factory(engine)
        record = PersistenceRecord(new_id(), utc_now(), {"kind": "test"})
        async with session_scope(factory) as session:
            await SqliteRepository(session).add(record)
        async with session_scope(factory) as session:
            assert await SqliteRepository(session).get(record.id) == record
    finally:
        await engine.dispose()


def test_database_config() -> None:
    assert database_settings({"database": {"url": "sqlite+aiosqlite://"}}).url.startswith("sqlite")


def test_memory_import_has_no_engine_side_effect() -> None:
    import super_ai.memory

    assert hasattr(super_ai.memory, "Base")
