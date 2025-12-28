"""Strategy for handling database pagination parameter errors."""

from typing import cast

from sqlalchemy.exc import DBAPIError
from typing_extensions import override

from infrakit._internal.mapper import MappingStrategy
from infrakit.repository.exceptions import DatabaseError, PaginationParameterError


class SqlAlchemyPaginationErrorStrategy(MappingStrategy):
    """Handle database pagination errors (negative limit/offset).

    Maps asyncpg InvalidRowCountInLimitClauseError and
    InvalidRowCountInResultOffsetClauseError to PaginationParameterError.
    """

    @override
    def can_handle(self, error: Exception) -> bool:
        """Check if error is a DBAPIError wrapping a pagination error."""
        if not isinstance(error, DBAPIError):
            return False

        # Check the original exception from the driver (asyncpg)
        orig = getattr(error, "orig", None)
        if orig is None:
            return False

        # Check if error message contains pagination keywords
        # The orig is wrapped by SQLAlchemy, so we check the string representation
        error_message = str(orig)
        return (
            "LIMIT must not be negative" in error_message
            or "OFFSET must not be negative" in error_message
        )

    @override
    def map(
        self,
        error: Exception,
        entity_type: str | None,
        entity_id: str | None,
    ) -> DatabaseError:
        """Map to PaginationParameterError with appropriate parameter name.

        Args:
            error: The DBAPIError wrapping the pagination error
            entity_type: Not used for pagination errors
            entity_id: Not used for pagination errors
        """
        # Safe cast: can_handle() already verified it's a DBAPIError
        dbapi_error = cast("DBAPIError", error)

        # Determine parameter name from the error message
        error_message = str(dbapi_error.orig)
        if "LIMIT must not be negative" in error_message:
            parameter_name = "limit"
        elif "OFFSET must not be negative" in error_message:
            parameter_name = "offset"
        else:
            # Fallback - shouldn't happen if can_handle works correctly
            parameter_name = "unknown"

        # Extract value from the error message or use -1 as placeholder
        # asyncpg doesn't provide the value directly in the exception
        value = -1
        # The actual negative value would be in the SQL parameters,
        # but we don't have easy access to it from here

        return PaginationParameterError(parameter_name, value)
