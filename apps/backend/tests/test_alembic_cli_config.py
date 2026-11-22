import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from super_ai import project_config


def test_alembic_reads_merged_project_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "project.json").write_text(
        '{"database":{"url":"sqlite+aiosqlite:///unused.db"}}', encoding="utf-8"
    )
    database_path = tmp_path / "cli%test.db"
    import json

    (tmp_path / "user.project.json").write_text(
        json.dumps({"database": {"url": f"sqlite+aiosqlite:///{database_path.as_posix()}"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(project_config, "default_config_dir", lambda: tmp_path)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as db:
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='mcp_connections'"
        ).fetchone() == ("mcp_connections",)
