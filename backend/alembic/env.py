from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.database import Base
from app import models  # noqa: F401 — registra as tabelas no metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    # override programático (app/migrations.py e testes) tem prioridade;
    # senão, a mesma configuração da aplicação (.env / variáveis de ambiente)
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    from app.config import settings
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), target_metadata=target_metadata,
                      literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
