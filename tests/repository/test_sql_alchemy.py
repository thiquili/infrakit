"""
Tests for SQLAlchemy repository implementation.

This module tests the SqlAlchemy implementation by:
1. Inheriting all contract tests from RepositoryContractTests
2. Implementing verification methods using plain SQL (as per TESTING_RULES.md)
3. Adding SqlAlchemy-specific tests (auto_commit behavior, transactions, etc.)

See TESTING_RULES.md for important testing principles.
"""

from collections.abc import AsyncGenerator, Callable, Generator

import pytest
import pytest_asyncio
from sqlalchemy import Column, String, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from testcontainers.postgres import PostgresContainer
from ulid import ULID

from infrakit.ports.repository.sql_alchemy import SqlAlchemy
from tests.repository.test_contract import RepositoryContractTests


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class TestSqlAlchemyRepository(RepositoryContractTests[UserModel, str]):
    """Test suite for SqlAlchemy repository implementation."""

    # ==================== Database Setup Fixtures ====================

    @pytest.fixture(scope="module", name="postgres_container")
    def init_postgres_container(self) -> Generator[PostgresContainer, None, None]:
        """ "
        Start a PostgreSQL container for tests.

        Scope: module - Le container est réutilisé pour tous les tests de la classe
        pour améliorer les performances (setup/teardown coûteux).
        """
        postgres = PostgresContainer("postgres:16")
        postgres.start()
        yield postgres
        postgres.stop()

    @pytest_asyncio.fixture(scope="function", name="engine")
    async def create_engine(
        self, postgres_container: PostgresContainer
    ) -> AsyncGenerator[AsyncEngine, None]:
        """
        Create an async SQLAlchemy engine connected to the PostgreSQL container.

        Scope: function - New engine per test to ensure isolation between test.
        """
        connection_url = postgres_container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )

        engine = create_async_engine(connection_url, echo=False)

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        # Cleanup: drop tables and close engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()

    @pytest_asyncio.fixture(scope="function", name="session")
    async def create_session(self, engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
        """Create an async SQLAlchemy session for each test."""
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create a session for the test
        async with async_session_factory() as session:
            yield session
            # Automatic rollback after each test for isolation
            await session.rollback()

    # ==================== Concrete Fixtures ====================

    @pytest.fixture
    def entity_factory(self) -> Callable[..., UserModel]:
        """Factory to create UserModel entities for testing."""

        def _create_user(entity_id: str | None = None, name: str = "Test User") -> UserModel:
            return UserModel(id=entity_id or str(ULID()), name=name)

        return _create_user

    # PyCharm warning: pytest fixtures use dependency injection - signatures may differ
    # between implementations (InMemory has no deps, SqlAlchemy needs session)
    # noinspection PyMethodOverriding
    @pytest.fixture
    def repository(self, session: AsyncSession) -> SqlAlchemy[UserModel, str]:
        """Create a SqlAlchemy repository with auto_commit enabled."""
        return SqlAlchemy(session=session, entity_model=UserModel, auto_commit=True)

    @pytest_asyncio.fixture
    async def repository_with_entities(
        self,
        repository: SqlAlchemy[UserModel, str],
        session: AsyncSession,
        entity_factory: Callable[..., UserModel],
    ) -> SqlAlchemy[UserModel, str]:
        """
        Create a repository with 10 pre-inserted entities.

        CRITICAL: Uses plain SQL for insertion (not repository.insert_one!)
        as per TESTING_RULES.md - we never test code with itself.
        """
        # Insertion with plain SQL (not via repository methods!)
        for i in range(10):
            user_id = str(ULID())
            await session.execute(
                text("INSERT INTO users (id, name) VALUES (:id, :name)"),
                {"id": user_id, "name": f"User {i}"},
            )
        await session.commit()
        return repository

    @pytest_asyncio.fixture
    async def entity_ids(
        self, repository_with_entities: SqlAlchemy[UserModel, str], session: AsyncSession
    ) -> list[str]:
        """Get list of entity IDs from the repository."""
        # Retrieval with plain SQL (not via repository.get_all!)
        result = await session.execute(text("SELECT id FROM users"))
        return [row[0] for row in result.fetchall()]

    # ==================== Verification Methods (Plain SQL) ====================

    async def _verify_entity_exists(self, repo: SqlAlchemy[UserModel, str], entity_id: str) -> bool:
        """
        Verify entity exists using plain SQL.

        As per TESTING_RULES.md: we use text() for verification, not repository methods.
        """
        result = await repo.session.execute(
            text("SELECT COUNT(*) FROM users WHERE id = :id"), {"id": entity_id}
        )
        count = result.scalar()
        return count > 0

    async def _verify_entity_count(self, repo: SqlAlchemy[UserModel, str]) -> int:
        """
        Count entities using plain SQL.

        As per TESTING_RULES.md: we use text() for verification, not repository methods.
        """
        result = await repo.session.execute(text("SELECT COUNT(*) FROM users"))
        return result.scalar()

    async def _verify_entity_data(
        self, repo: SqlAlchemy[UserModel, str], entity_id: str, expected_name: str
    ) -> bool:
        """
        Verify entity data using plain SQL.

        As per TESTING_RULES.md: we use text() for verification, not repository methods.
        """
        result = await repo.session.execute(
            text("SELECT name FROM users WHERE id = :id"), {"id": entity_id}
        )
        row = result.fetchone()
        if row is None:
            return False
        return row[0] == expected_name

    # ==================== SqlAlchemy-Specific Tests ====================

    @pytest.mark.asyncio
    async def test_auto_commit_disabled_requires_manual_commit(
        self, repository: SqlAlchemy[UserModel, str], entity_factory: Callable[..., UserModel]
    ) -> None:
        """
        When auto_commit=False, changes should not persist without manual commit.

        This tests SqlAlchemy-specific transaction behavior.
        """
        # Create repository with auto_commit disabled using the same session
        repo = SqlAlchemy(session=repository.session, entity_model=UserModel, auto_commit=False)

        # Insert entity
        user = entity_factory(name="Transaction Test")
        await repo.insert_one(user)

        # Rollback the transaction
        await repository.session.rollback()

        # Verify entity was NOT persisted (plain SQL verification)
        result = await repository.session.execute(
            text("SELECT COUNT(*) FROM users WHERE id = :id"), {"id": user.id}
        )
        count = result.scalar()
        assert count == 0, "Entity should not persist after rollback with auto_commit=False"

    @pytest.mark.asyncio
    async def test_auto_commit_enabled_persists_immediately(
        self, repository: SqlAlchemy[UserModel, str], entity_factory: Callable[..., UserModel]
    ) -> None:
        """
        When auto_commit=True, changes should persist immediately.

        This tests SqlAlchemy-specific auto-commit behavior.
        """
        # Create repository with auto_commit enabled using the same session
        repo = SqlAlchemy(session=repository.session, entity_model=UserModel, auto_commit=True)

        # Insert entity
        user = entity_factory(name="Auto Commit Test")
        await repo.insert_one(user)

        # Verify entity was persisted (plain SQL verification)
        result = await repository.session.execute(
            text("SELECT COUNT(*) FROM users WHERE id = :id"), {"id": user.id}
        )
        count = result.scalar()
        assert count == 1, "Entity should persist immediately with auto_commit=True"

        # Verify data integrity (plain SQL)
        result = await repository.session.execute(
            text("SELECT name FROM users WHERE id = :id"), {"id": user.id}
        )
        name = result.scalar()
        assert name == "Auto Commit Test"

    @pytest.mark.asyncio
    async def test_insert_many_with_auto_commit_false(
        self, repository: SqlAlchemy[UserModel, str], entity_factory: Callable[..., UserModel]
    ) -> None:
        """
        insert_many with auto_commit=False should allow rollback.

        This tests transaction control with bulk operations.
        """
        repo = SqlAlchemy(session=repository.session, entity_model=UserModel, auto_commit=False)

        # Insert multiple entities
        users = [entity_factory(name=f"Bulk User {i}") for i in range(5)]
        await repo.insert_many(users)

        # Verify entities are in session but not committed yet
        result = await repository.session.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        assert count == 5

        # Rollback
        await repository.session.rollback()

        # Verify entities were NOT persisted
        result = await repository.session.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        assert count == 0

    @pytest.mark.asyncio
    async def test_update_with_plain_sql_verification(
        self, repository: SqlAlchemy[UserModel, str], entity_factory: Callable[..., UserModel]
    ) -> None:
        """
        Demonstrate the testing pattern from TESTING_RULES.md for update.

        - Prepare: INSERT with plain SQL
        - Test: repository.update()
        - Verify: SELECT with plain SQL
        """
        # Prepare: Insert with plain SQL
        user_id = str(ULID())
        await repository.session.execute(
            text("INSERT INTO users (id, name) VALUES (:id, :name)"),
            {"id": user_id, "name": "Original Name"},
        )
        await repository.session.commit()

        # Test: Update via repository
        repo = SqlAlchemy(session=repository.session, entity_model=UserModel, auto_commit=True)
        updated_user = UserModel(id=user_id, name="Updated Name")
        await repo.update(updated_user)

        # Verify: SELECT with plain SQL
        result = await repository.session.execute(
            text("SELECT name FROM users WHERE id = :id"), {"id": user_id}
        )
        name_in_db = result.scalar()
        assert name_in_db == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_with_plain_sql_verification(
        self, repository: SqlAlchemy[UserModel, str], entity_factory: Callable[..., UserModel]
    ) -> None:
        """
        Demonstrate the testing pattern from TESTING_RULES.md for delete.

        - Prepare: INSERT with plain SQL
        - Test: repository.delete_by_id()
        - Verify: SELECT COUNT with plain SQL
        """
        # Prepare: Insert with plain SQL
        user_id = str(ULID())
        await repository.session.execute(
            text("INSERT INTO users (id, name) VALUES (:id, :name)"),
            {"id": user_id, "name": "To Delete"},
        )
        await repository.session.commit()

        # Test: Delete via repository
        repo = SqlAlchemy(session=repository.session, entity_model=UserModel, auto_commit=True)
        await repo.delete_by_id(user_id)

        # Verify: SELECT COUNT with plain SQL
        result = await repository.session.execute(
            text("SELECT COUNT(*) FROM users WHERE id = :id"), {"id": user_id}
        )
        count = result.scalar()
        assert count == 0
