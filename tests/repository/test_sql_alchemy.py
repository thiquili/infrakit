"""
Tests for the SQLAlchemy implementation of the Repository pattern.

See TESTING_RULES.md for important testing principles and patterns.
"""

from collections.abc import AsyncGenerator, Generator

from pydantic import BaseModel
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


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


# Pydantic model for data
class User(BaseModel):
    id: str
    name: str


@pytest.fixture(scope="module", name="postgres_container")
def init_postgres_container() -> Generator[PostgresContainer, None, None]:
    """Start a PostgreSQL container for tests."""
    postgres = PostgresContainer("postgres:16")
    postgres.start()
    yield postgres
    postgres.stop()


@pytest_asyncio.fixture(scope="function", name="engine")
async def create_engine(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncEngine, None]:
    """Create an async SQLAlchemy engine connected to the PostgreSQL container."""
    connection_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )

    engine = create_async_engine(connection_url, echo=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup: drop tables and close engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function", name="session")
async def create_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
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


async def test_create_user(session: AsyncSession) -> None:
    """Test user creation with plain SQL verification."""
    # Arrange
    user_id = str(ULID())
    user = UserModel(id=user_id, name="John Doe")
    repository = SqlAlchemy(session=session, entity_model=UserModel, auto_commit=True)

    # Act
    created_user = await repository.insert_one(user)

    # Assert - Verification with plain SQL
    result = await session.execute(
        text("SELECT id, name FROM users WHERE id = :user_id"), {"user_id": user_id}
    )
    row = result.fetchone()

    assert row is not None
    assert row[0] == user_id
    assert row[1] == "John Doe"
    assert created_user.id == user_id
    assert created_user.name == "John Doe"


async def test_get_user_by_id(session: AsyncSession) -> None:
    """Test user retrieval by ID with plain SQL insertion."""
    # Arrange - Insertion with plain SQL
    user_id = str(ULID())
    await session.execute(
        text("INSERT INTO users (id, name) VALUES (:id, :name)"),
        {"id": user_id, "name": "Jane Doe"},
    )
    await session.commit()

    repository = SqlAlchemy(session=session, entity_model=UserModel, auto_commit=False)

    # Act
    retrieved_user = await repository.get_by_id(user_id)

    # Assert
    assert retrieved_user.id == user_id
    assert retrieved_user.name == "Jane Doe"


async def test_get_all_users(session: AsyncSession) -> None:
    """Test retrieval of all users with plain SQL verification."""
    # Arrange - Insertion with plain SQL
    user1_id = str(ULID())
    user2_id = str(ULID())
    await session.execute(
        text("INSERT INTO users (id, name) VALUES (:id1, :name1), (:id2, :name2)"),
        {"id1": user1_id, "name1": "Alice", "id2": user2_id, "name2": "Bob"},
    )
    await session.commit()

    repository = SqlAlchemy(session=session, entity_model=UserModel, auto_commit=False)

    # Act
    all_users = await repository.get_all()

    # Assert - Verification with plain SQL
    result = await session.execute(text("SELECT COUNT(*) FROM users"))
    count = result.scalar()

    assert len(all_users) == 2
    assert count == 2
    assert any(u.name == "Alice" for u in all_users)
    assert any(u.name == "Bob" for u in all_users)


async def test_update_user(session: AsyncSession) -> None:
    """Test user update with plain SQL verification."""
    # Arrange - Insertion with plain SQL
    user_id = str(ULID())
    await session.execute(
        text("INSERT INTO users (id, name) VALUES (:id, :name)"),
        {"id": user_id, "name": "Old Name"},
    )
    await session.commit()

    repository = SqlAlchemy(session=session, entity_model=UserModel, auto_commit=True)
    user = UserModel(id=user_id, name="New Name")

    # Act
    updated_user = await repository.update(user)

    # Assert - Verification with plain SQL
    result = await session.execute(
        text("SELECT name FROM users WHERE id = :user_id"), {"user_id": user_id}
    )
    name_in_db = result.scalar()

    assert updated_user.name == "New Name"
    assert name_in_db == "New Name"


async def test_delete_user(session: AsyncSession) -> None:
    """Test user deletion with plain SQL verification."""
    # Arrange - Insertion with plain SQL
    user_id = str(ULID())
    await session.execute(
        text("INSERT INTO users (id, name) VALUES (:id, :name)"),
        {"id": user_id, "name": "To Delete"},
    )
    await session.commit()

    repository = SqlAlchemy(session=session, entity_model=UserModel, auto_commit=True)

    # Act
    await repository.delete_by_id(user_id)

    # Assert - Verification with plain SQL
    result = await session.execute(
        text("SELECT COUNT(*) FROM users WHERE id = :user_id"), {"user_id": user_id}
    )
    count = result.scalar()

    assert count == 0
