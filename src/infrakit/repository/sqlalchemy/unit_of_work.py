from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing_extensions import override

from infrakit.repository.protocols import HasId, UnitOfWork
from infrakit.repository.sqlalchemy import SqlAlchemy


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Unit of work implementation using SQLAlchemy for database operations.

    This implementation follows the explicit commit principle: changes are not
    automatically persisted to the database. The commit() method must be called
    explicitly to persist changes or rollback() to discard them.
    """

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], entity_models: list[type[HasId]]
    ) -> None:
        """Initialize the unit of work with a session factory and entity models.

        Args:
            session_factory: SQLAlchemy async session factory for creating database sessions.
            entity_models: List of entity model classes that will have repositories created.
        """
        self.session_factory = session_factory
        self.entity_models = entity_models
        self.repositories = {}

    async def __aenter__(self) -> Self:
        """Enter the async context manager, creating a session and repositories.

        Returns:
            Self: The unit of a work instance with initialized session and repositories.
        """
        self.session = self.session_factory()
        self.repositories = {
            entity_model: SqlAlchemy(
                session=self.session, entity_model=entity_model, auto_commit=False
            )
            for entity_model in self.entity_models
        }
        return self

    @override
    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit the async context manager, handling rollback on exception and closing the session.

        Args:
            exc_type: Exception type if an exception occurred, None otherwise.
            exc_val: Exception value if an exception occurred, None otherwise.
            exc_tb: Exception traceback if an exception occurred, None otherwise.
        """
        try:
            await super().__aexit__(exc_type, exc_val, exc_tb)
        finally:
            await self.session.close()

    @override
    async def commit(self) -> None:
        """Commit the current transaction, persisting all changes to the database."""
        await self.session.commit()

    @override
    async def rollback(self) -> None:
        """Roll back the current transaction, discarding all uncommitted changes."""
        await self.session.rollback()
