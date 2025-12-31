from collections.abc import AsyncGenerator, Callable, Generator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import Column, String, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from testcontainers.postgres import PostgresContainer
from ulid import ULID

from infrakit.repository import SqlAlchemyUnitOfWork


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class TestSqlAlchemyUnitOfWork:
    @pytest.fixture(scope="module", name="postgres_container")
    def init_postgres_container(self) -> Generator[PostgresContainer, None, None]:
        """ "
        Start a PostgreSQL container for tests.

        Scope: module - The container is reused for all tests in the class
        to improve performance (expensive setup/teardown).
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

    @pytest_asyncio.fixture(scope="function", name="session_factory")
    async def create_session_factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        """Create an async sessionmaker factory SQLAlchemy session for each test."""
        return async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

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
    def user_entity_factory(self) -> Callable[..., User]:
        """Factory to create User entities for testing."""

        def _create_user(entity_id: str | None = None, name: str = "Test User") -> User:
            return User(id=entity_id or str(ULID()), name=name)

        return _create_user

    @pytest.fixture
    def company_entity_factory(self) -> Callable[..., Company]:
        """Factory to create Company entities for testing."""

        def _create_company(entity_id: str | None = None, name: str = "Test Company") -> Company:
            return Company(id=entity_id or str(ULID()), name=name)

        return _create_company

    @pytest.fixture
    def uow(self, session_factory: async_sessionmaker[AsyncSession | Any]) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory=session_factory, entity_models=[User, Company])

    # ==================== Test ====================

    def test_init_unit_of_work(
        self, uow: SqlAlchemyUnitOfWork, session_factory: async_sessionmaker[AsyncSession | Any]
    ) -> None:
        """Initialize the unit of work with the provided session factory and entity factory."""
        assert uow.session_factory == session_factory
        assert uow.entity_models == [User, Company]
        assert len(uow.repositories) == 0

    @pytest.mark.asyncio
    async def test_without_commit_no_persistence(
        self,
        uow: SqlAlchemyUnitOfWork,
        user_entity_factory: Callable[..., User],
        company_entity_factory: Callable[..., Company],
        session: AsyncSession,
    ) -> None:
        """
        Should test it if the user does not commit, the persistence should not happen. Commit must be explicit
        """
        async with uow as s:
            await s.repositories[User].insert_one(entity=user_entity_factory(name="User 1"))
            await s.repositories[Company].insert_one(
                entity=company_entity_factory(name="Company 1")
            )
        assert (await session.execute(text("SELECT COUNT(*) FROM users"))).scalar() == 0
        assert (await session.execute(text("SELECT COUNT(*) FROM companies"))).scalar() == 0

    @pytest.mark.asyncio
    async def test_with_commit_implies_persistance(
        self,
        uow: SqlAlchemyUnitOfWork,
        user_entity_factory: Callable[..., User],
        company_entity_factory: Callable[..., Company],
        session: AsyncSession,
    ) -> None:
        """
        Test that explicit commit persists changes to the database.
        """
        async with uow as s:
            await s.repositories[User].insert_one(entity=user_entity_factory(name="User 1"))
            await s.repositories[Company].insert_one(
                entity=company_entity_factory(name="Company 1")
            )
            await s.commit()
        assert (await session.execute(text("SELECT COUNT(*) FROM users"))).scalar() == 1
        assert (await session.execute(text("SELECT COUNT(*) FROM companies"))).scalar() == 1

    @pytest.mark.asyncio
    async def test_repositories_share_same_session(
        self,
        uow: SqlAlchemyUnitOfWork,
        user_entity_factory: Callable[..., User],
        company_entity_factory: Callable[..., Company],
    ) -> None:
        """
        Test that multiple repositories share the same database session within a UoW.
        """
        async with uow as s:
            await s.repositories[User].insert_one(entity=user_entity_factory(name="User 1"))
            await s.repositories[Company].insert_one(
                entity=company_entity_factory(name="Company 1")
            )
            assert s.repositories[User].session is s.repositories[Company].session

    @pytest.mark.asyncio
    async def test_should_rollback_if_error_happend(
        self,
        uow: SqlAlchemyUnitOfWork,
        user_entity_factory: Callable[..., User],
        company_entity_factory: Callable[..., Company],
        session: AsyncSession,
    ) -> None:
        """
        Test that the unit of work rolls back changes if an error occurs during transaction.
        """
        user_id = str(ULID())
        await session.execute(
            text("INSERT INTO users (id, name) VALUES (:id, :name)"),
            {"id": user_id, "name": "User"},
        )
        await session.commit()

        async with uow as s:
            await s.repositories[User].insert_one(
                entity=user_entity_factory(entity_id=user_id, name="User 1")
            )
            await s.repositories[Company].insert_one(
                entity=company_entity_factory(name="Company 1")
            )
            with pytest.raises(
                IntegrityError, match="duplicate key value violates unique constraint"
            ):
                await s.commit()

        assert (await session.execute(text("SELECT COUNT(*) FROM users"))).scalar() == 1
        assert (await session.execute(text("SELECT COUNT(*) FROM companies"))).scalar() == 0

    @pytest.mark.asyncio
    async def test_explicit_rollback(
        self,
        uow: SqlAlchemyUnitOfWork,
        user_entity_factory: Callable[..., User],
        session: AsyncSession,
    ) -> None:
        """Test that explicit rollback discards uncommitted changes."""
        async with uow as s:
            await s.repositories[User].insert_one(entity=user_entity_factory(name="User 1"))
            await s.rollback()  # Explicit rollback

            # Can continue to use the UoW after rollback
            await s.repositories[User].insert_one(entity=user_entity_factory(name="User 2"))
            await s.commit()

        # Only User 2 should be persisted
        assert (await session.execute(text("SELECT COUNT(*) FROM users"))).scalar() == 1
        result = await session.execute(text("SELECT name FROM users"))
        assert result.scalar() == "User 2"

    @pytest.mark.asyncio
    async def test_multiple_operations_same_repository(
        self,
        uow: SqlAlchemyUnitOfWork,
        user_entity_factory: Callable[..., User],
        session: AsyncSession,
    ) -> None:
        """Test multiple operations on the same repository within one transaction."""
        user1_id = str(ULID())
        user2_id = str(ULID())

        async with uow as s:
            # Insert
            await s.repositories[User].insert_one(
                entity=user_entity_factory(entity_id=user1_id, name="User 1")
            )
            await s.repositories[User].insert_one(
                entity=user_entity_factory(entity_id=user2_id, name="User 2")
            )

            # Update
            user1 = await s.repositories[User].get_by_id(user1_id)
            user1.name = "Updated User 1"
            await s.repositories[User].update(user1)

            # Delete
            await s.repositories[User].delete_by_id(user2_id)

            await s.commit()

        # Verify: 1 user, with modified name
        assert (await session.execute(text("SELECT COUNT(*) FROM users"))).scalar() == 1
        result = await session.execute(
            text("SELECT name FROM users WHERE id = :id"), {"id": user1_id}
        )
        assert result.scalar() == "Updated User 1"

    @pytest.mark.asyncio
    async def test_expire_on_commit_false_behavior(
        self, uow: SqlAlchemyUnitOfWork, user_entity_factory: Callable[..., User]
    ) -> None:
        """Test that entities remain accessible after commit with expire_on_commit=False."""
        user_id = str(ULID())

        async with uow as s:
            user = user_entity_factory(entity_id=user_id, name="User 1")
            await s.repositories[User].insert_one(entity=user)
            await s.commit()

            # With expire_on_commit=False, the object should remain accessible
            # without additional DB query
            assert user.name == "User 1"  # No lazy loading error
            assert user.id == user_id

    @pytest.mark.asyncio
    async def test_uow_isolation(
        self, uow: SqlAlchemyUnitOfWork, user_entity_factory: Callable[..., User]
    ) -> None:
        """Test that two UoW instances are properly isolated."""
        user_id = str(ULID())

        # UoW 1: commit
        async with uow as s1:
            await s1.repositories[User].insert_one(
                user_entity_factory(entity_id=user_id, name="User 1")
            )
            await s1.commit()

        # UoW 2: can read what has been committed
        async with uow as s2:
            users = await s2.repositories[User].get_all()
            assert len(users) == 1
            assert users[0].name == "User 1"
