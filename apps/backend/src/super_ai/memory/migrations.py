from pathlib import Path


def upgrade_head(database_url: str, backend_root: Path) -> None:
    from alembic.config import Config

    from alembic import command

    config = Config(str(backend_root / "alembic.ini"))
    sync_url = database_url.replace("+aiosqlite", "")
    config.set_main_option("sqlalchemy.url", sync_url.replace("%", "%%"))
    command.upgrade(config, "head")
