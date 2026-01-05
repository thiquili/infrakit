"""
Tests for create_default_session_factory function.

This module tests:
1. Environment variable handling (required/optional)
2. Integration with real PostgreSQL via testcontainers
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

from infrakit.repository.sqlalchemy import create_default_session_factory


class TestCreateDefaultSessionFactoryUnit:
    """Unit tests for environment variable handling."""

    # ==================== Required Environment Variables ====================

    @patch.dict(
        "os.environ",
        {
            "SQL_DB_NAME": "testdb",
            "SQL_DB_USER": "testuser",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
        },
        clear=True,
    )
    def test_missing_required_env_host(self) -> None:
        """Should raise KeyError when SQL_DB_HOST is missing."""
        with pytest.raises(KeyError) as exc_info:
            create_default_session_factory()
        assert "SQL_DB_HOST" in str(exc_info.value)

    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_USER": "testuser",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
        },
        clear=True,
    )
    def test_missing_required_env_name(self) -> None:
        """Should raise KeyError when SQL_DB_NAME is missing."""
        with pytest.raises(KeyError) as exc_info:
            create_default_session_factory()
        assert "SQL_DB_NAME" in str(exc_info.value)

    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_NAME": "testdb",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
        },
        clear=True,
    )
    def test_missing_required_env_user(self) -> None:
        """Should raise KeyError when SQL_DB_USER is missing."""
        with pytest.raises(KeyError) as exc_info:
            create_default_session_factory()
        assert "SQL_DB_USER" in str(exc_info.value)

    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_NAME": "testdb",
            "SQL_DB_USER": "testuser",
        },
        clear=True,
    )
    def test_missing_required_env_password(self) -> None:
        """Should raise KeyError when SQL_DB_PASSWORD is missing."""
        with pytest.raises(KeyError) as exc_info:
            create_default_session_factory()
        assert "SQL_DB_PASSWORD" in str(exc_info.value)

    # ==================== Optional Environment Variables ====================

    @patch("infrakit.repository.sqlalchemy.session_factory.async_sessionmaker")
    @patch("infrakit.repository.sqlalchemy.session_factory.create_async_engine")
    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_NAME": "testdb",
            "SQL_DB_USER": "testuser",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
        },
        clear=True,
    )
    def test_default_port_value(
        self,
        mock_create_engine: MagicMock,
        mock_sessionmaker: MagicMock,
    ) -> None:
        """Should use port 5432 by default when SQL_DB_PORT is not set."""
        create_default_session_factory()

        url = mock_create_engine.call_args[0][0]
        assert ":5432/" in url

    @patch("infrakit.repository.sqlalchemy.session_factory.async_sessionmaker")
    @patch("infrakit.repository.sqlalchemy.session_factory.create_async_engine")
    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_NAME": "testdb",
            "SQL_DB_USER": "testuser",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
        },
        clear=True,
    )
    def test_default_driver_value(
        self,
        mock_create_engine: MagicMock,
        mock_sessionmaker: MagicMock,
    ) -> None:
        """Should use postgresql+asyncpg by default when SQL_DB_DRIVER is not set."""
        create_default_session_factory()

        url = mock_create_engine.call_args[0][0]
        assert url.startswith("postgresql+asyncpg://")

    @patch("infrakit.repository.sqlalchemy.session_factory.async_sessionmaker")
    @patch("infrakit.repository.sqlalchemy.session_factory.create_async_engine")
    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_PORT": "5433",
            "SQL_DB_NAME": "testdb",
            "SQL_DB_USER": "testuser",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
        },
        clear=True,
    )
    def test_custom_port_value(
        self,
        mock_create_engine: MagicMock,
        mock_sessionmaker: MagicMock,
    ) -> None:
        """Should use custom port when SQL_DB_PORT is set."""
        create_default_session_factory()

        url = mock_create_engine.call_args[0][0]
        assert ":5433/" in url

    @patch("infrakit.repository.sqlalchemy.session_factory.async_sessionmaker")
    @patch("infrakit.repository.sqlalchemy.session_factory.create_async_engine")
    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_NAME": "testdb",
            "SQL_DB_USER": "testuser",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
            "SQL_DB_DRIVER": "postgresql+psycopg",
        },
        clear=True,
    )
    def test_custom_driver_value(
        self,
        mock_create_engine: MagicMock,
        mock_sessionmaker: MagicMock,
    ) -> None:
        """Should use custom driver when SQL_DB_DRIVER is set."""
        create_default_session_factory()

        url = mock_create_engine.call_args[0][0]
        assert url.startswith("postgresql+psycopg://")

    # ==================== Echo Parameter ====================

    @patch("infrakit.repository.sqlalchemy.session_factory.async_sessionmaker")
    @patch("infrakit.repository.sqlalchemy.session_factory.create_async_engine")
    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_NAME": "testdb",
            "SQL_DB_USER": "testuser",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
        },
        clear=True,
    )
    def test_echo_parameter_false_by_default(
        self,
        mock_create_engine: MagicMock,
        mock_sessionmaker: MagicMock,
    ) -> None:
        """Should create engine with echo=False by default."""
        create_default_session_factory()

        assert mock_create_engine.call_args[1]["echo"] is False

    @patch("infrakit.repository.sqlalchemy.session_factory.async_sessionmaker")
    @patch("infrakit.repository.sqlalchemy.session_factory.create_async_engine")
    @patch.dict(
        "os.environ",
        {
            "SQL_DB_HOST": "localhost",
            "SQL_DB_NAME": "testdb",
            "SQL_DB_USER": "testuser",
            "SQL_DB_PASSWORD": "testpass",  # pragma: allowlist secret
        },
        clear=True,
    )
    def test_echo_parameter_true(
        self,
        mock_create_engine: MagicMock,
        mock_sessionmaker: MagicMock,
    ) -> None:
        """Should create engine with echo=True when specified."""
        create_default_session_factory(echo=True)

        assert mock_create_engine.call_args[1]["echo"] is True


class TestCreateDefaultSessionFactoryIntegration:
    """Integration tests with real PostgreSQL container."""

    @pytest.fixture(scope="class")
    def postgres_container(self) -> Generator[PostgresContainer, None, None]:
        """Start a PostgreSQL container for tests."""
        postgres = PostgresContainer("postgres:16")
        postgres.start()
        yield postgres
        postgres.stop()

    @pytest.fixture
    def env_from_container(
        self, postgres_container: PostgresContainer
    ) -> Generator[dict[str, str], None, None]:
        """Set environment variables from the container."""
        env = {
            "SQL_DB_HOST": postgres_container.get_container_host_ip(),
            "SQL_DB_PORT": str(postgres_container.get_exposed_port(5432)),
            "SQL_DB_NAME": postgres_container.dbname,
            "SQL_DB_USER": postgres_container.username,
            "SQL_DB_PASSWORD": postgres_container.password,
            "SQL_DB_DRIVER": "postgresql+asyncpg",
        }
        with patch.dict("os.environ", env, clear=True):
            yield env

    @pytest_asyncio.fixture
    async def engine_and_factory(
        self, env_from_container: dict[str, str]
    ) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
        """Create engine and session factory from the container."""
        engine, session_factory = create_default_session_factory()
        yield engine, session_factory
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_engine_can_connect(
        self, engine_and_factory: tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
    ) -> None:
        """Should successfully connect to the database."""
        engine, _ = engine_and_factory
        async with engine.connect() as conn:
            assert conn is not None

    @pytest.mark.asyncio
    async def test_session_factory_creates_session(
        self, engine_and_factory: tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
    ) -> None:
        """Should create an AsyncSession instance."""
        _, session_factory = engine_and_factory
        async with session_factory() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_session_can_execute_query(
        self, engine_and_factory: tuple[AsyncEngine, async_sessionmaker[AsyncSession]]
    ) -> None:
        """Should be able to execute a simple query."""
        _, session_factory = engine_and_factory
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
