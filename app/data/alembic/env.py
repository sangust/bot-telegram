import os
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context
from app.src.domain.models import BASE

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BASE.metadata

DATABASE_URL = os.getenv("DATABASE_URL")

# Correção: O replace escapa o '%' apenas para o configparser do Alembic ler sem quebrar.
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"}
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    # O SQLAlchemy usa o DATABASE_URL original para estabelecer a conexão.
    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()