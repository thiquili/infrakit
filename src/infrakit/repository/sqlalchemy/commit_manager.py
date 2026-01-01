"""SQLAlchemy commit manager with error handling."""

from sqlalchemy.ext.asyncio import AsyncSession

from infrakit._internal.mapper import ExceptionMapper


class SqlAlchemyCommitManager:
    """Manages commit operations with error mapping for SQLAlchemy.

    This class encapsulates the commit/rollback logic with exception mapping,
    making it reusable across Repository and UnitOfWork implementations.

    The manager always maps infrastructure exceptions to domain exceptions
    using the provided ExceptionMapper.
    """

    def __init__(self, session: AsyncSession, exception_mapper: ExceptionMapper) -> None:
        """Initialize the commit manager.

        Args:
            session: SQLAlchemy async session
            exception_mapper: Mapper for converting infrastructure exceptions to domain exceptions
        """
        self._session = session
        self._exception_mapper = exception_mapper

    async def safe_commit(self, entity_type: str, entity_id: str | None = None) -> None:
        """Execute a commit with error handling and mapping.

        Args:
            entity_type: Type of entity for error messages (e.g., "User", "Transaction")
            entity_id: Optional entity ID for error messages

        Raises:
            DatabaseError: Always raises a domain exception (specific or generic)
        """
        try:
            await self._session.commit()
        except Exception as e:
            await self._session.rollback()

            # Map infrastructure exception to domain exception
            # The mapper always returns a DatabaseError (specific or generic)
            domain_error = self._exception_mapper.map(
                error=e,
                entity_type=entity_type,
                entity_id=entity_id or "unknown",
            )
            raise domain_error from e
