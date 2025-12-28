"""SQLAlchemy exception mapper."""

from typing_extensions import override

from infrakit._internal.mapper import ExceptionMapper
from infrakit._internal.registry import StrategyRegistry
from infrakit.repository.exceptions import DatabaseError
from infrakit.repository.sqlalchemy._strategies.pagination_error import (
    SqlAlchemyPaginationErrorStrategy,
)
from infrakit.repository.sqlalchemy._strategies.unique_violation import (
    SqlAlchemyUniqueViolationStrategy,
)


class SqlAlchemyExceptionMapper(ExceptionMapper):
    """Maps SQLAlchemy exceptions to domain exceptions.

    Uses a registry of strategies to handle different types of errors.
    Each strategy is specific to a type of database constraint violation.
    """

    def __init__(self) -> None:
        self._registry = StrategyRegistry()
        self._register_strategies()

    def _register_strategies(self) -> None:
        """Register all SQLAlchemy-specific mapping strategies.

        Strategies are tried in registration order.
        """
        self._registry.register(SqlAlchemyPaginationErrorStrategy())
        self._registry.register(SqlAlchemyUniqueViolationStrategy())

    @override
    def map(
        self,
        error: Exception,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> DatabaseError:
        """Map a SQLAlchemy exception to a domain exception.

        Args:
            error: The SQLAlchemy exception
            entity_type: The entity type name (e.g., "User")
            entity_id: The entity ID that caused the error

        Returns:
            The mapped domain exception

        Raises:
            The original exception if it cannot be mapped
        """
        return self._registry.map(error, entity_type, entity_id)
