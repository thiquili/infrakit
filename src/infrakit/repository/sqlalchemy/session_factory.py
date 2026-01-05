"""SQLAlchemy session factory with environment variable configuration."""

import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_default_session_factory(
    *,
    echo: bool = False,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create a SQLAlchemy session factory configured for the UoW pattern.

    Configuration:
        - autocommit=False
        - autoflush=False
        - expire_on_commit=False

    Environment variables (required):
        - SQL_DB_HOST: Database host
        - SQL_DB_NAME: Database name
        - SQL_DB_USER: Database user
        - SQL_DB_PASSWORD: Database password

    Environment variables (optional):
        - SQL_DB_PORT: Database port (default: 5432)
        - SQL_DB_DRIVER: Async driver (default: postgresql+asyncpg)

    Args:
        echo: Enable SQL logging if True

    Returns:
        Tuple containing (engine, session_factory)
    """
    driver = os.environ.get("SQL_DB_DRIVER", "postgresql+asyncpg")
    host = os.environ["SQL_DB_HOST"]
    port = os.environ.get("SQL_DB_PORT", "5432")
    name = os.environ["SQL_DB_NAME"]
    user = os.environ["SQL_DB_USER"]
    password = os.environ["SQL_DB_PASSWORD"]

    url = f"{driver}://{user}:{password}@{host}:{port}/{name}"

    engine = create_async_engine(url, echo=echo)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    return engine, session_factory
