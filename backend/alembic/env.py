from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings, normalize_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_online() -> None:
    engine = create_engine(normalize_url(get_settings().database_url))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
