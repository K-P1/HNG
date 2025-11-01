import os
import sys
from logging.config import fileConfig

import asyncio
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context  # type: ignore[attr-defined]
from dotenv import load_dotenv

# load .env for DATABASE_URL
load_dotenv()

# this is the Alembic Config object, which provides access to values
# within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from env
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL must be set in environment for Alembic")

# If a sync driver is present in the URL, convert common drivers to their async equivalents
if "+pymysql" in db_url:
    db_url = db_url.replace("+pymysql", "+aiomysql")
if db_url.startswith("sqlite://") and "+aiosqlite" not in db_url:
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

config.set_main_option("sqlalchemy.url", db_url)

# Ensure project root is on sys.path so 'app' is importable when executed via Alembic CLI
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from app.models.models import Base  # noqa

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    # Use an async engine for online migrations
    # Use the validated `db_url` above (assert to help type checkers).
    assert isinstance(db_url, str)
    connectable = create_async_engine(
        db_url,
        future=True,
        pool_pre_ping=True,
        # Avoid pooled connections lingering across event loop shutdown
        poolclass=NullPool,
    )

    async def _run():
        async with connectable.connect() as connection:
            # Run migrations in a sync context
            await connection.run_sync(do_run_migrations)
        # Ensure all connections/transports are closed before the loop ends
        await connectable.dispose()

    asyncio.run(_run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
