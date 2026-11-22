from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from super_ai.memory import Base
from super_ai.project_config import load_project_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

# Programmatic migrations inject a temporary URL; the CLI uses the same
# merged project configuration as the application.
if not config.get_main_option("sqlalchemy.url"):
    database_config = load_project_config().get("database", {})
    if not isinstance(database_config, dict):
        raise ValueError("database 配置必须为对象")
    database_url = database_config.get("url", "sqlite+aiosqlite:///./super_ai.db")
    if not isinstance(database_url, str) or not database_url:
        raise ValueError("database.url 配置无效")
    sync_url = database_url.replace("+aiosqlite", "")
    config.set_main_option("sqlalchemy.url", sync_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
